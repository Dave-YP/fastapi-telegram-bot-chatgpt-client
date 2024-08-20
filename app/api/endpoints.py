import logging
import secrets
from datetime import datetime, timedelta
from typing import List

import aioredis

from fastapi import APIRouter, HTTPException, Depends, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates

from pydantic import BaseModel, Field

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.status_codes import StatusMessages
from app.db.init_db import get_db
from app.db.models import Message, Tab, TelegramMessage, User
from app.schemas.token import Token
from app.schemas.user import RegisterUser
from app.services.auth import AuthService
from app.services.message_limit import MessageLimitService
from app.services.openai_service import OpenAIService, OpenAIServiceTelegramBot
from app.services.token_service import TokenService


router = APIRouter()

templates = Jinja2Templates(directory="app/templates")
redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
daily_message_limit = settings.DAILY_MESSAGE_LIMIT
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MessageContext(BaseModel):
    role: str
    content: str
    created_at: datetime = None


class Question(BaseModel):
    user_id: int
    question: str
    context: List[MessageContext]
    source: str


class RenameTabRequest(BaseModel):
    new_name: str = Field(..., min_length=1, max_length=50)


def generate_bot_token(user_id: int) -> str:
    return secrets.token_urlsafe(32)


@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        current_user = await AuthService.get_current_user(request, db)
        context = {
            "request": request,
            "current_user": current_user,
            "telegram_bot_url": settings.TELEGRAM_BOT_URL,
            "tokens_remaining": current_user.tokens
        }

        if current_user:
            bot_token = generate_bot_token(current_user.id)
            await redis_client.setex(
                f"bot_token:{bot_token}", 3600, str(current_user.id)
            )
            context["bot_token"] = bot_token

        return templates.TemplateResponse("index.html", context)
    except HTTPException:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "current_user": None,
                "telegram_bot_url": settings.TELEGRAM_BOT_URL
            }
        )


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        current_user = await AuthService.get_current_user(request, db)

        tabs_query = await db.execute(
            select(Tab).filter(Tab.user_id == current_user.id)
        )
        tabs = tabs_query.scalars().all()

        if not tabs:
            new_tab = Tab(user_id=current_user.id, name="New Tab")
            db.add(new_tab)
            await db.commit()
            tabs = [new_tab]

        tab_data = [
            {
                "id": tab.id,
                "name": tab.name,
                "created_at": tab.created_at.isoformat(),
                "updated_at": tab.updated_at.isoformat() if tab.updated_at else None
            }
            for tab in tabs
        ]

        first_tab_id = tab_data[0]['id'] if tab_data else None

        return templates.TemplateResponse(
            "chat.html",
            {
                "request": request,
                "current_user": current_user,
                "tokens_remaining": current_user.tokens,
                "tabs": tab_data,
                "first_tab_id": first_tab_id
            }
        )
    except HTTPException:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/chat")
async def chat(
    message: dict,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    try:
        current_user = await AuthService.get_current_user(request, db)
    except HTTPException:
        raise HTTPException(
            status_code=401,
            detail=StatusMessages.UNAUTHORIZED
        )

    user_id = current_user.id

    tab_id = message.get("tab_id")
    if not tab_id:
        raise HTTPException(
            status_code=400,
            detail="Tab identifier is not specified."
        )

    tab_query = await db.execute(
        select(Tab).filter(
            Tab.id == tab_id,
            Tab.user_id == user_id
        )
    )
    tab = tab_query.scalar_one_or_none()

    if not tab:
        raise HTTPException(status_code=404, detail="Tab not found.")

    if len(message['message']) > 1000:
        return {
            "response": "The maximum message length is 1000 characters.",
            "error": True
        }
    try:
        await MessageLimitService.check_and_increment_question_count(
            redis_client,
            user_id
        )
    except HTTPException:
        limit_message = StatusMessages.get_message_limit_text(
            daily_message_limit
        )
        return {"response": limit_message, "error": True}

    tokens_needed = TokenService.count_tokens(message['message'])
    if not await TokenService.deduct_tokens(user_id, tokens_needed, db):
        return {"response": "Insufficient tokens.", "error": True}

    context_query = await db.execute(
        select(Message)
        .filter(Message.tab_id == tab_id)
        .order_by(Message.created_at.asc())
        .limit(settings.MAX_CONTEXT_MESSAGES)
    )
    context = [
        {"role": msg.content["role"],
         "content": msg.content["content"]} for msg in context_query.scalars().all()
    ]

    try:
        response_text, updated_context = await OpenAIService.ask_question(
            message['message'], context
        )
        tokens_used = TokenService.count_tokens(response_text)
        if not await TokenService.deduct_tokens(user_id, tokens_used, db):
            return {
                "response": "Not enough tokens to get a response.",
                "error": True
            }

        new_message = Message(
            tab_id=tab.id,
            content={"role": "user",
                     "content": message['message']}
        )
        db.add(new_message)
        await db.commit()

        assistant_message = Message(
            tab_id=tab.id,
            content={"role": "assistant",
                     "content": response_text}
        )
        db.add(assistant_message)
        await db.commit()

        current_user.tokens -= (tokens_needed + tokens_used)
        await db.commit()

        tab_data = {
            "id": tab.id,
            "name": tab.name,
            "created_at": tab.created_at.isoformat(),
            "updated_at": tab.updated_at.isoformat() if tab.updated_at else None
        }

        return {
            "response": response_text,
            "tokens_remaining": current_user.tokens,
            "tab": tab_data
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=StatusMessages.SERVER_ERROR
        )


def get_message_limit_text(limit):
    if limit % 10 == 1 and limit % 100 != 11:
        return f"Error 451: Daily limit of {limit} question reached."
    elif limit % 10 in [2, 3, 4] and not (limit % 100 in [12, 13, 14]):
        return f"Error 451: Daily limit of {limit} questions reached."
    else:
        return f"Error 451: Daily limit of {limit} questions reached."


@router.post("/ask_telegram")
async def ask_telegram(
    question: Question,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"Received request on /ask_telegram: {question.question}")

    try:
        current_user = await AuthService.get_current_user(request, db)
        logger.info(f"User authenticated: {current_user.email}")
    except HTTPException:
        raise HTTPException(
            status_code=401,
            detail=StatusMessages.UNAUTHORIZED
        )

    user_id = current_user.id

    if len(question.question) > 1000:
        return {
            "response": "The maximum length of the question "
            "is 1000 characters.",
            "error": True
        }

    try:
        await MessageLimitService.check_and_increment_question_count(
            redis_client, user_id
        )
    except HTTPException:
        limit_message = StatusMessages.get_message_limit_text(
            daily_message_limit
        )
        return {"response": limit_message, "error": True}

    tokens_needed = TokenService.count_tokens(question.question)
    if not await TokenService.deduct_tokens(user_id, tokens_needed, db):
        return {
            "response": "Not enough tokens to send the question.",
            "error": True
        }

    context_query = await db.execute(
        select(TelegramMessage)
        .filter(TelegramMessage.user_id == user_id)
        .order_by(TelegramMessage.created_at.asc())
        .limit(settings.MAX_CONTEXT_MESSAGES)
    )
    context = [
        {"role": msg.message["role"], "content": msg.message["content"]}
        for msg in context_query.scalars().all()
    ]

    try:
        response_text, updated_context = await OpenAIServiceTelegramBot.ask_question(question.question, context)
        tokens_used = TokenService.count_tokens(response_text)
        if not await TokenService.deduct_tokens(user_id, tokens_used, db):
            return {
                "response": "Not enough tokens to receive the answer.",
                "error": True
            }

        return {
            "response": response_text,
            "tokens_used": tokens_needed + tokens_used,
            "tokens_remaining": current_user.tokens
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=StatusMessages.SERVER_ERROR
        )


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    registered = request.query_params.get("registered", "false") == "true"
    return templates.TemplateResponse(
        "login.html", {"request": request, "registered": registered}
    )


@router.post("/login")
async def login(
    request: Request, email: str = Form(...), password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    user = await AuthService.authenticate_user(db, email, password)
    if not user:
        return JSONResponse(
            content={"error": "Incorrect email or password"}, status_code=400
        )

    access_token_expires = timedelta(
        minutes=AuthService.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    access_token = AuthService.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    response = JSONResponse(content={"success": True, "redirect": "/"})
    response.set_cookie(key="access_token", value=access_token, httponly=True)
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register/form")
async def register_user_form(
    request: Request, email: str = Form(...), password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).filter(User.email == email))
    db_user = result.scalar_one_or_none()
    if db_user:
        return JSONResponse(
            content={"error": "Email is already registered"}, status_code=400
        )

    hashed_password = AuthService.pwd_context.hash(password)
    new_user = User(email=email, hashed_password=hashed_password)
    db.add(new_user)
    try:
        await db.commit()
        await db.refresh(new_user)
        return JSONResponse(
            content={"success": True, "redirect": "/login?registered=true"}
        )
    except IntegrityError:
        await db.rollback()
        return JSONResponse(
            content={"error": "An error occurred during registration. "
                              "Please try again."},
            status_code=400
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error during user registration: {str(e)}")
        return JSONResponse(
            content={"error": "An internal server error occurred. "
                              "Please try again later."},
            status_code=500
        )


@router.post("/register", response_model=RegisterUser)
async def register_user(
    register_user: RegisterUser, db: AsyncSession = Depends(get_db)
):
    try:
        result = await db.execute(
            select(User).filter(User.email == register_user.email)
        )
        db_user = result.scalar_one_or_none()
        if db_user:
            raise HTTPException(
                status_code=400,
                detail="Email is already registered"
            )

        hashed_password = AuthService.pwd_context.hash(register_user.password)
        new_user = User(
            email=register_user.email,
            hashed_password=hashed_password,
            tokens=2000
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return {
            "email": register_user.email,
            "password": "********",
            "message": "User successfully registered"
        }
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Email already exists"
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error during registration: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@router.post("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="access_token")
    return response


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy", "database": "disconnected", "error": str(e)
        }


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    user = await AuthService.authenticate_user(
        db, form_data.username, form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(
        minutes=AuthService.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    access_token = AuthService.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh_token", response_model=Token)
async def refresh_token(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        current_user = await AuthService.get_current_user(request, db)
    except HTTPException:
        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(
        minutes=AuthService.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    access_token = AuthService.create_access_token(
        data={"sub": current_user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/verify_token")
async def verify_token(token_data: dict, db: AsyncSession = Depends(get_db)):
    token = token_data.get("token")
    if not token:
        raise HTTPException(
            status_code=400,
            detail="Token not provided"
        )

    user_id = await redis_client.get(f"bot_token:{token}")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    user = await db.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    access_token_expires = timedelta(
        minutes=AuthService.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    access_token = AuthService.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "email": user.email,
        "user_id": user.id
    }


@router.get("/tokenbalance")
async def get_token_balance(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    try:
        current_user = await AuthService.get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return {"tokens_remaining": current_user.tokens}


@router.get("/get_tab_messages/{tab_id}")
async def get_tab_messages(tab_id: int, db: AsyncSession = Depends(get_db)):
    try:
        tab_id = int(tab_id)

        messages_query = await db.execute(
            select(Message).filter(Message.tab_id == tab_id).order_by(Message.created_at.asc())
        )
        messages = messages_query.scalars().all()

        return [
            {"sender": "user" if msg.content["role"] == "user" else "assistant",
             "text": msg.content["content"]} for msg in messages
        ]

    except Exception as e:
        logger.error(f"Error loading tab messages: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Server error while loading messages."
        )


@router.post("/create_tab")
async def create_tab(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        current_user = await AuthService.get_current_user(request, db)
        logger.info(
            f"Creating a new tab for user: {current_user.email}"
        )

        new_tab = Tab(user_id=current_user.id, name="New Tab")
        db.add(new_tab)
        await db.commit()
        await db.refresh(new_tab)

        logger.info(f"New tab: {new_tab.id} with name: {new_tab.name}")
        return {
            "tab_id": new_tab.id,
            "name": new_tab.name
        }
    except Exception as e:
        logger.error(f"Error creating new tab: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Server error while creating tab."
        )


@router.put("/rename_tab/{tab_id}")
async def rename_tab(
    tab_id: int,
    rename_request: RenameTabRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    try:
        current_user = await AuthService.get_current_user(request, db)

        tab_query = await db.execute(
            select(Tab).filter(Tab.id == tab_id, Tab.user_id == current_user.id)
        )
        tab = tab_query.scalar_one_or_none()

        if tab is None:
            raise HTTPException(status_code=404, detail="Tab not found")

        tab.name = rename_request.new_name
        await db.commit()

        return {"tab_id": tab.id, "new_name": tab.name}

    except Exception as e:
        logger.error(f"Error renaming tab: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Server error while renaming tab."
        )


@router.delete("/delete_tab/{tab_id}")
async def delete_tab(
    tab_id: int, request: Request,
    db: AsyncSession = Depends(get_db)
):
    try:
        current_user = await AuthService.get_current_user(request, db)

        tab_query = await db.execute(
            select(Tab).filter(
                Tab.id == tab_id,
                Tab.user_id == current_user.id)
        )
        tab = tab_query.scalar_one_or_none()

        if not tab:
            raise HTTPException(status_code=404, detail="Tab not found.")

        await db.execute(delete(Message).filter(Message.tab_id == tab_id))
        await db.execute(delete(Tab).filter(Tab.id == tab_id))
        await db.commit()

        return {"detail": "Tab deleted."}
    except Exception as e:
        logger.error(f"Error deleting tab: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Server error while deleting tab."
        )


@router.delete("/clear_context/{tab_id}")
async def clear_context(
    tab_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    try:
        current_user = await AuthService.get_current_user(request, db)

        tab_query = await db.execute(
            select(Tab).filter(
                Tab.id == tab_id,
                Tab.user_id == current_user.id)
        )
        tab = tab_query.scalar_one_or_none()

        if not tab:
            raise HTTPException(status_code=404, detail="Tab not found.")

        await db.execute(delete(Message).filter(Message.tab_id == tab_id))
        await db.commit()

        return {"detail": "Context cleared."}
    except Exception as e:
        logger.error(f"Error clearing context: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Server error while clearing context."
        )


@router.delete("/clear_telegram_context/{user_id}")
async def clear_telegram_context(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    try:
        logger.info(f"Starting context deletion for user_id: {user_id}")

        delete_query = delete(TelegramMessage).where(TelegramMessage.user_id == user_id)
        logger.info(f"SQL delete query: {delete_query}")

        result = await db.execute(delete_query)
        await db.commit()

        if result.rowcount == 0:
            logger.info(f"Context not found for user_id: {user_id}")
            return {"message": "Conversation context not found."}

        logger.info(
            f"Deleted records: {result.rowcount} for user_id: {user_id}"
        )

        remaining_messages = await db.execute(
            select(TelegramMessage).where(TelegramMessage.user_id == user_id)
        )
        remaining_count = len(remaining_messages.scalars().all())
        logger.info(
            f"Remaining messages: {remaining_count} for user_id: {user_id}"
        )

        return {
            "message": "Conversation context deleted.",
            "deleted_records": result.rowcount,
            "remaining_records": remaining_count
        }

    except Exception as e:
        logger.error(
            f"Error deleting context for user_id {user_id}: {e}"
        )
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Error deleting context."
        )

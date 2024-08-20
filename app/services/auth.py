import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models import User
from app.db.init_db import get_db


class AuthService:
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 120

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

    @classmethod
    def create_access_token(
        cls, data: dict,
        expires_delta: Optional[timedelta] = None
    ):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode,
            cls.SECRET_KEY,
            algorithm=cls.ALGORITHM
        )
        return encoded_jwt

    @classmethod
    async def authenticate_user(
        cls,
        db: AsyncSession,
        email: str,
        password: str
    ):
        result = await db.execute(select(User).filter(User.email == email))
        user = result.scalar_one_or_none()
        if not user or not cls.pwd_context.verify(
            password,
            user.hashed_password
        ):
            return False
        return user

    @classmethod
    async def get_current_user(cls, request: Request, db: AsyncSession):
        credentials_exception = HTTPException(
            status_code=401,
            detail="Failed to authenticate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

        token = (
            request.cookies.get("access_token") or
            request.headers.get("Authorization")
        )
        if not token:
            raise credentials_exception

        try:
            token = (
                token.split()[1]
                if token.lower().startswith("bearer ")
                else token
            )
            payload = jwt.decode(
                token,
                cls.SECRET_KEY,
                algorithms=[cls.ALGORITHM]
            )
            email: str = payload.get("sub")
            if email is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception

        result = await db.execute(select(User).filter(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            raise credentials_exception
        return user

    @classmethod
    async def get_current_user_for_chat(
        cls, token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db)
    ):
        credentials_exception = HTTPException(
            status_code=401,
            detail="Failed to authenticate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(
                token,
                cls.SECRET_KEY,
                algorithms=[cls.ALGORITHM]
            )
            email: str = payload.get("sub")
            if email is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception

        result = await db.execute(select(User).filter(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            raise credentials_exception
        return user

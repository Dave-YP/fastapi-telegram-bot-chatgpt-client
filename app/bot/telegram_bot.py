import asyncio
import logging

from aiohttp import ClientTimeout, ClientResponseError, ClientConnectionError
from aiohttp import ClientSession, ClientError


from telegram import Update
from telegram import KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler
from telegram.ext import CallbackContext, filters
from telegram.constants import ChatAction
from telegram.error import NetworkError

from app.core.status_codes import StatusMessages
from app.core.config import settings
from app.db.models import TelegramMessage
from sqlalchemy.future import select
from app.db.init_db import AsyncSessionLocal
import re

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
telegram_token = settings.TELEGRAM_TOKEN
api_url = settings.API_URL
daily_message_limit = settings.DAILY_MESSAGE_LIMIT

if not telegram_token:
    raise ValueError("TELEGRAM_TOKEN must be provided")
if not api_url:
    raise ValueError("API_URL must be provided")

user_sessions = {}


def get_main_menu_keyboard():
    keyboard = [
        [KeyboardButton("💰 Balance")],
        [KeyboardButton("🗑 Clear Context")],
        [KeyboardButton("📋 Main Menu")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def handle_auth_token(update: Update, context: CallbackContext) -> None:
    auth_token = context.args[0] if context.args else None
    if not auth_token:
        await update.message.reply_text(
            "Please use the link from the website "
            "for automatic authorization."
        )
        return

    async with ClientSession() as session:
        try:
            async with session.post(
                f"{api_url}/verify_token",
                json={"token": auth_token},
                timeout=ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()

                    if 'user_id' not in data:
                        await update.message.reply_text(
                            "Authorization error: 'user_id' "
                            "is missing in the server response."
                        )
                        return

                    user_sessions[update.message.chat_id] = {
                        "token": data["access_token"],
                        "email": data["email"],
                        "user_id": data["user_id"],
                        "message_count": 0
                    }
                    await update.message.reply_text(
                        "You have successfully authorized. "
                        "Now you can ask questions.",
                        reply_markup=get_main_menu_keyboard()
                    )
                else:
                    error_data = await response.text()
                    await update.message.reply_text(
                        f"Authorization error. Status: {response.status}. "
                        f"Response: {error_data}"
                    )
        except ClientResponseError as e:
            await update.message.reply_text(
                f"API response error: {e.status} - {e.message}"
            )
        except ClientConnectionError:
            await update.message.reply_text(
                "Server connection error. Please try again later."
            )
        except asyncio.TimeoutError:
            await update.message.reply_text(
                "Server response timeout. Please try again later."
            )
        except ClientError as e:
            await update.message.reply_text(f"Client error: {str(e)}")
        except NetworkError as e:
            await update.message.reply_text(
                f"Telegram network error: {str(e)}"
            )
        except Exception as e:
            await handle_api_error(update, str(e))


async def start(update: Update, context: CallbackContext) -> None:
    message_text = update.message.text

    if message_text.startswith("/start") or message_text == "📋 Main Menu":
        if context.args:
            await handle_auth_token(update, context)
        else:
            await update.message.reply_text(
                "Hello! I am Chat GPT bot for answering your questions. "
                "Use the command "
                "/tokenbalance to check your token balance. "
                "/clear_context to clear the current dialogue context.",
                reply_markup=get_main_menu_keyboard()
            )


async def handle_api_error(update: Update, error_message: str):
    logger.error(f"API Error: {error_message}")
    await update.message.reply_text(f"An error occurred: {error_message}")


async def answer_question(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id

    if chat_id not in user_sessions:
        await update.message.reply_text(
            "Please use the link from the website "
            "for automatic authorization.",
            reply_markup=get_main_menu_keyboard()
        )
        return

    if 'user_id' not in user_sessions[chat_id]:
        await update.message.reply_text(
            "Error: Failed to retrieve user ID. Please use the link "
            "from the website for automatic authorization.",
            reply_markup=get_main_menu_keyboard()
        )
        return

    user_id = user_sessions[chat_id]['user_id']
    question_text = update.message.text

    if len(question_text) > 2000:
        await update.message.reply_text(
            "The maximum message length is 2000 characters."
        )
        return

    logger.info(f"Received question from user_id {user_id}: {question_text}")

    await context.bot.send_chat_action(
        chat_id=chat_id,
        action=ChatAction.TYPING
    )

    async with AsyncSessionLocal() as db_session:
        async with db_session.begin():
            db_context = await db_session.execute(
                select(TelegramMessage)
                .filter(TelegramMessage.user_id == user_id)
                .order_by(TelegramMessage.created_at.asc())
                .limit(settings.MAX_CONTEXT_MESSAGES)
            )
            db_context = db_context.scalars().all()

            full_context = [
                {
                    "role": msg.message["role"],
                    "content": msg.message["content"]
                }
                for msg in db_context
            ]
            full_context.append({"role": "user", "content": question_text})

            new_message = TelegramMessage(
                user_id=user_id,
                message={"role": "user", "content": question_text}
            )
            db_session.add(new_message)
            await db_session.commit()

    async with ClientSession() as session:
        try:
            headers = {
                "Authorization": f"Bearer {user_sessions[chat_id]['token']}"
            }
            logger.info(
                "Sending request to /ask_telegram with data: %s",
                {
                    "user_id": user_id,
                    "question": question_text,
                    "context": full_context,
                    "source": "telegram"
                }
            )
            async with session.post(
                f"{api_url}/ask_telegram",
                headers=headers,
                json={
                    "user_id": user_id,
                    "question": question_text,
                    "context": full_context,
                    "source": "telegram"
                },
                timeout=ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    reply_message = data.get(
                        'response',
                        'No response from the server.'
                    )

                    # Checking and formatting the response
                    if "```" in reply_message:
                        reply_message = re.sub(
                            r'```([a-zA-Z]*)\n',
                            r'```python\n', reply_message
                        )

                    reply_message += (
                        f"\n\nTokens used: {data.get('tokens_used', 0)}\n"
                        f"Tokens remaining: {data.get('tokens_remaining', 0)}"
                    )
                    await update.message.reply_text(
                        reply_message, parse_mode='Markdown'
                    )

                    assistant_message = TelegramMessage(
                        user_id=user_id,
                        message={"role": "assistant",
                                 "content": data.get(
                                     'response',
                                     'No response from the server.'
                                    )}
                    )
                    async with AsyncSessionLocal() as db_session:
                        async with db_session.begin():
                            db_session.add(assistant_message)
                            await db_session.commit()

                elif response.status == 400:
                    error_data = await response.json()
                    await update.message.reply_text(
                        error_data.get("detail", "Not enough tokens.")
                    )

                elif response.status == 401:
                    await update.message.reply_text(
                        StatusMessages.SESSION_EXPIRED,
                        reply_markup=get_main_menu_keyboard()
                    )
                    user_sessions.pop(chat_id, None)
                elif response.status == 422:
                    error_data = await response.json()
                    logger.error(f"Validation error: {error_data}")
                    await update.message.reply_text(
                        StatusMessages.VALIDATION_ERROR
                    )
                elif response.status == 451:
                    error_message = StatusMessages.get_message_limit_text(
                        daily_message_limit
                    )
                    await update.message.reply_text(error_message)
                elif response.status == 403:
                    await update.message.reply_text(StatusMessages.FORBIDDEN)
                elif response.status == 500:
                    await update.message.reply_text(
                        StatusMessages.SERVER_ERROR
                    )
                else:
                    await update.message.reply_text(
                        StatusMessages.UNEXPECTED_ERROR.format(
                            status=response.status
                        )
                    )

        except ClientResponseError as e:
            logger.error(f"API response error: {e.status} - {e.message}")
            await update.message.reply_text(f"API response error: {e.message}")
        except ClientConnectionError as e:
            logger.error(f"Connection error: {str(e)}")
            await update.message.reply_text(
                "Server connection error. Please try again later."
            )
        except asyncio.TimeoutError as e:
            logger.error(f"Timeout error: {str(e)}")
            await update.message.reply_text("Server response timeout.")
        except ClientError as e:
            logger.error(f"General aiohttp client error: {str(e)}")
            await update.message.reply_text(
                "An error occurred while interacting with the server. "
                "Please try again later."
            )
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            await update.message.reply_text(
                "An unexpected error occurred. Please try again later."
            )


async def get_token_balance(update: Update, context: CallbackContext) -> None:
    message_text = update.message.text
    if (
        message_text.startswith("/tokenbalance") or
        message_text.startswith("💰 Balance")
    ):
        chat_id = update.message.chat_id
        if (
            chat_id not in user_sessions or
            "token" not in user_sessions[chat_id]
        ):
            await update.message.reply_text(
                StatusMessages.LOGIN_REQUIRED,
                reply_markup=get_main_menu_keyboard()
            )
            return

    async with ClientSession() as session:
        try:
            headers = {
                "Authorization": f"Bearer {user_sessions[chat_id]['token']}"
            }
            async with session.get(
                f"{api_url}/tokenbalance",
                headers=headers,
                timeout=10
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    tokens_remaining = data.get("tokens_remaining")
                    await update.message.reply_text(
                        f"Token balance: {tokens_remaining}",
                        reply_markup=get_main_menu_keyboard()
                    )
                elif response.status == 401:
                    await update.message.reply_text(
                        StatusMessages.SESSION_EXPIRED,
                        reply_markup=get_main_menu_keyboard()
                    )
                    user_sessions.pop(chat_id, None)
                else:
                    await update.message.reply_text(
                        f"Unexpected error: HTTP {response.status}",
                        reply_markup=get_main_menu_keyboard()
                    )

        except ClientResponseError as e:
            logger.error(f"API response error: {e.status} - {e.message}")
            await update.message.reply_text(
                f"API response error: {e.message}",
                reply_markup=get_main_menu_keyboard()
            )

        except ClientConnectionError as e:
            logger.error(f"Connection error: {str(e)}")
            await update.message.reply_text(
                "Connection error with the server. Please try again later.",
                reply_markup=get_main_menu_keyboard()
            )

        except asyncio.TimeoutError as e:
            logger.error(f"Timeout error: {str(e)}")
            await update.message.reply_text(
                "Server response timeout.",
                reply_markup=get_main_menu_keyboard()
            )

        except ClientError as e:
            logger.error(f"General aiohttp client error: {str(e)}")
            await update.message.reply_text(
                "An error occurred while interacting with the server. "
                "Please try again later.",
                reply_markup=get_main_menu_keyboard()
            )

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            await update.message.reply_text(
                "An unexpected error occurred. Please try again later.",
                reply_markup=get_main_menu_keyboard()
            )


async def clear_context(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id

    if chat_id not in user_sessions:
        await update.message.reply_text(
            "Error: You are not authorized. Please "
            "log in through the website for authorization.",
            reply_markup=get_main_menu_keyboard()
        )
        return

    user_id = user_sessions[chat_id]['user_id']

    async with ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {user_sessions[chat_id]['token']}"
        }
        async with session.delete(
            f"{api_url}/clear_telegram_context/{user_id}",
            headers=headers
        ) as response:
            if response.status == 200:
                user_sessions[chat_id]['context'] = []

                await update.message.reply_text(
                    "Chat context successfully cleared.",
                    reply_markup=get_main_menu_keyboard()
                )
            else:
                await update.message.reply_text(
                    "Failed to clear chat context.",
                    reply_markup=get_main_menu_keyboard()
                )


def main() -> None:
    application = ApplicationBuilder().token(telegram_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("tokenbalance", get_token_balance))
    application.add_handler(CommandHandler("clear_context", clear_context))

    application.add_handler(
        MessageHandler(filters.Regex("^📋 Main Menu$"), start)
    )
    application.add_handler(
        MessageHandler(filters.Regex("^💰 Balance$"), get_token_balance)
    )
    application.add_handler(
        MessageHandler(filters.Regex("^🗑 Clear Context$"), clear_context)
    )

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, answer_question)
    )

    application.run_polling()


if __name__ == '__main__':
    main()

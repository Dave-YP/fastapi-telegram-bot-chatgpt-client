import os
import logging

from openai import AsyncOpenAI, APIConnectionError, RateLimitError
from openai import APIStatusError
from fastapi import HTTPException

from app.core.config import settings


class OpenAIService:
    api_key = settings.OPENAI_API_KEY or os.getenv('OPENAI_API_KEY')

    @classmethod
    async def ask_question(cls, question: str, context: list = None):
        try:
            client = AsyncOpenAI(api_key=cls.api_key)
            if context is None:
                context = []

            context = [
                {"role": msg["role"], "content": msg["content"]}
                for msg in context
                if msg.get("role") is not None and msg.get("content") is not None
            ]

            context = context[-settings.MAX_CONTEXT_MESSAGES:]

            context.append({"role": "user", "content": question})

            chat_completion = await client.chat.completions.create(
                messages=[{"role": msg["role"], "content": msg["content"]} for msg in context],
                model="gpt-4o",
            )
            response = chat_completion.choices[0].message.content

            context.append({"role": "assistant", "content": response})

            return response, context
        except APIConnectionError as e:
            logging.error(f"API connection error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Unable to connect to the OpenAI API."
            )
        except RateLimitError as e:
            logging.warning(f"Rate limit exceeded: {str(e)}")
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded."
            )
        except APIStatusError as e:
            logging.error(
                f"API returned an error: {e.status_code} - {e.response}"
            )
            raise HTTPException(
                status_code=500,
                detail="Error occurred when calling OpenAI API."
            )
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Unexpected error: {str(e)}"
            )


class OpenAIServiceTelegramBot:
    api_key = settings.OPENAI_API_KEY or os.getenv('OPENAI_API_KEY')

    @classmethod
    async def ask_question(cls, question: str, context: list = None):
        try:
            client = AsyncOpenAI(api_key=cls.api_key)
            if context is None:
                context = []

            context = [
                {"role": msg["role"], "content": msg["content"]}
                for msg in context
                if msg.get("role") is not None and msg.get("content") is not None
            ]

            context = context[-settings.MAX_CONTEXT_MESSAGES:]

            context.append({"role": "user", "content": question})

            chat_completion = await client.chat.completions.create(
                messages=[{"role": msg["role"], "content": msg["content"]} for msg in context],
                model="gpt-4o",
            )
            response = chat_completion.choices[0].message.content

            context.append({"role": "assistant", "content": response})

            return response, context
        except APIConnectionError as e:
            logging.error(f"API connection error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Unable to connect to the OpenAI API."
            )
        except RateLimitError as e:
            logging.warning(f"Rate limit exceeded: {str(e)}")
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded."
            )
        except APIStatusError as e:
            logging.error(
                f"API returned an error: {e.status_code} - {e.response}"
            )
            raise HTTPException(
                status_code=500,
                detail="Error occurred when calling OpenAI API."
            )
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Unexpected error: {str(e)}"
            )

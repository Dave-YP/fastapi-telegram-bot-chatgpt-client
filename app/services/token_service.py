from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


class TokenService:
    @staticmethod
    def count_tokens(message: str) -> int:
        words = message.split()
        num_words = len(words)
        num_chars = len(message)
        tokens = num_words + int(num_chars * 0.1)
        return tokens

    @staticmethod
    async def deduct_tokens(
        user_id: int,
        tokens: int, db: AsyncSession
    ) -> bool:
        user = await db.get(User, user_id)
        if user and user.tokens >= tokens:
            user.tokens -= tokens
            await db.commit()
            return True
        return False

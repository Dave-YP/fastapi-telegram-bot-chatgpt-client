from datetime import datetime, timezone

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship


Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    tokens = Column(Integer, default=2000)

    tabs = relationship("Tab", back_populates="user")


class Tab(Base):
    __tablename__ = "tabs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.now)
    user = relationship("User", back_populates="tabs")
    messages = relationship("Message", back_populates="tab")


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    tab_id = Column(Integer, ForeignKey("tabs.id"), nullable=False)
    content = Column(JSON)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    tab = relationship("Tab", back_populates="messages")


class TelegramMessage(Base):
    __tablename__ = 'telegram_messages'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    message = Column(JSON)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

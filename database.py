"""
Database layer — MySQL (via SQLAlchemy async ORM, driver: aiomysql).
Replaces the previous MongoDB (motor) layer.
"""
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Text, DateTime, JSON, Integer, Index, UniqueConstraint,
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "within_the_blur")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

DATABASE_URL = (
    f"mysql+aiomysql://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

Base = declarative_base()


def new_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=new_uuid)
    email = Column(String(255), nullable=False, unique=True, index=True)
    name = Column(String(60), nullable=False, default="")
    password_hash = Column(String(255), nullable=False)
    profile_color = Column(String(20), nullable=False, default="terracotta")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id = Column(String(36), primary_key=True, default=new_uuid)
    identifier = Column(String(320), nullable=False, unique=True, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_attempt = Column(DateTime(timezone=True), nullable=True)
    locked_until = Column(DateTime(timezone=True), nullable=True)


class JournalEntry(Base):
    __tablename__ = "journal"

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), nullable=False, index=True)
    title = Column(String(120), nullable=False, default="Tanpa Judul")
    body = Column(Text, nullable=False)
    mood = Column(String(40), nullable=False, default="tenang")
    unlock_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("ix_journal_user_created", "user_id", "created_at"),
    )


class KuisResult(Base):
    __tablename__ = "kuis_results"

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), nullable=False, index=True)
    dominant = Column(String(20), nullable=False)
    counts = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("ix_kuis_user_created", "user_id", "created_at"),
    )


class CekDiriEntry(Base):
    __tablename__ = "cekdiri"

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), nullable=False, index=True)
    feeling = Column(String(40), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("ix_cekdiri_user_created", "user_id", "created_at"),
    )


async def init_db() -> None:
    """Create tables if they don't exist yet (idempotent)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

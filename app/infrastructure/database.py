import os
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from typing import AsyncGenerator

from app.models.base import Base
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL não definida no ambiente.")

# ==========================
# Engine Async
# ==========================
engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # coloque False em produção
    future=True,
)

# ==========================
# Session Factory
# ==========================
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

# ==========================
# Dependency FastAPI
# ==========================
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
# ==========================
# Inicialização do Banco (apenas para DEV)
# ==========================

import app.models.lead
import app.models.conversation
import app.models.message
import app.models.classification
import app.models.action

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

from dotenv import load_dotenv

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
# Inicialização do Banco
# ==========================
# NÃO usamos mais create_all().
# O schema agora é controlado exclusivamente pelo Alembic.
async def init_db():
    pass
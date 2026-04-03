import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/multi_agents")

# A engine é o centro da conexão SQL. Usamos pool_pre_ping=True para segurança
# e evitar conexões "zumbis" ou caídas com o Banco de dados
try:
    engine = create_engine(
        DATABASE_URL, 
        pool_pre_ping=True, 
        pool_recycle=3600
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info("Database engine criada com sucesso.")
except Exception as e:
    logger.error("Erro crítico ao criar Engine do Banco de Dados", extra={"error": str(e)})

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

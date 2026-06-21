from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
import logging
from .config import settings

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rural_tech_db")

# Base para los modelos declarativos de SQLAlchemy
Base = declarative_base()

# ==========================================
# INICIALIZACIÓN DE LA BASE DE DATOS
# ==========================================
logger.info(f"Conectando a base de datos: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG if hasattr(settings, 'DEBUG') else False,
    future=True,
    pool_pre_ping=True,
    connect_args={"statement_cache_size": 0}
)

async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Dependencia para obtener la sesión de base de datos en los routers de FastAPI
async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
            logger.debug("Transacción COMMITTED exitosamente")
        except Exception as e:
            logger.error(f"Error en transacción, haciendo ROLLBACK: {str(e)}")
            await session.rollback()
            raise
        finally:
            await session.close()

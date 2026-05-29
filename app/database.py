from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DATABASE_URL

# Configuración de base de datos
# pool_size y max_overflow optimizados para el límite de conexiones de un db.t4g.micro
engine = create_engine(DATABASE_URL, pool_size=5, max_overflow=10, pool_recycle=1800, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    Dependencia de FastAPI para obtener una conexión limpia de base de datos.
    Garantiza que la sesión se cierre correctamente al concluir la petición HTTP.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

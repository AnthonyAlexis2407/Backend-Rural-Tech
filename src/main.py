from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os
from fastapi.middleware.cors import CORSMiddleware
from .components.controllers import (
    cursos_router, inscripciones_router, certificados_router, 
    notificaciones_router, sync_router, auth_router, archivos_descargados_router,
    logros_router, faqs_router, uploads_router
)
from .database import async_session
from .config import settings
from sqlalchemy import text
from datetime import datetime, timezone

app = FastAPI(
    title="Rural-Tech API",
    description="Backend de la plataforma Rural-Tech con soporte de sincronización offline y conexión a Supabase.",
    version="1.0.0"
)

# Configuración de CORS para permitir peticiones desde el frontend de Angular
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "/tmp/uploads" if os.environ.get("VERCEL") else "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Registrar Routers
app.include_router(cursos_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(inscripciones_router, prefix="/api")
app.include_router(certificados_router, prefix="/api")
app.include_router(notificaciones_router, prefix="/api")
app.include_router(sync_router, prefix="/api")
app.include_router(archivos_descargados_router, prefix="/api")
app.include_router(logros_router, prefix="/api")
app.include_router(faqs_router, prefix="/api")
app.include_router(uploads_router, prefix="/api")

@app.get("/")
async def root():
    return {
        "app": "Rural-Tech API",
        "status": "online",
        "documentation": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint para monitoreo y load balancers."""
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@app.get("/health/live")
async def liveness_check():
    """Liveness check - indica si el proceso está vivo (no verifica DB)."""
    return {"status": "alive"}


@app.get("/api/db-diagnostico")
async def db_diagnostico():
    import socket
    import urllib.parse
    
    # Extraer host y puerto del DATABASE_URL de configuración
    db_host = "Desconocido"
    db_port = "5432"
    try:
        # postgresql+asyncpg://user:pass@host:port/db
        parsed_url = settings.DATABASE_URL
        if "@" in parsed_url:
            host_port_part = parsed_url.split("@")[-1].split("/")[0]
            if ":" in host_port_part:
                db_host, db_port = host_port_part.split(":")
            else:
                db_host = host_port_part
    except Exception:
        pass

    dns_status = "ok"
    dns_error = None
    try:
        socket.getaddrinfo(db_host, int(db_port) if db_port.isdigit() else 5432)
    except Exception as e:
        dns_status = "error"
        dns_error = str(e)
        
    db_status = "unknown"
    db_error = None
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception as e:
        db_status = "disconnected"
        db_error = str(e)
        
    return {
        "status": "online" if db_status == "connected" else "error",
        "database": {
            "status": db_status,
            "error": db_error,
            "connection_url_masked": settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else settings.DATABASE_URL
        },
        "dns": {
            "host": db_host,
            "port": db_port,
            "status": dns_status,
            "error": dns_error
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)


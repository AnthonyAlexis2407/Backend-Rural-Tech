from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .components.controllers import cursos_router, inscripciones_router, certificados_router, notificaciones_router, sync_router, auth_router

app = FastAPI(
    title="Rural-Tech API",
    description="Backend de la plataforma Rural-Tech con soporte de sincronización offline y conexión a Supabase.",
    version="1.0.0"
)

# Configuración de CORS para permitir peticiones desde el frontend de Angular (localhost:4200 u otros hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, restringir a dominios específicos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar Routers
app.include_router(cursos_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(inscripciones_router, prefix="/api")
app.include_router(certificados_router, prefix="/api")
app.include_router(notificaciones_router, prefix="/api")
app.include_router(sync_router, prefix="/api")

@app.get("/")
async def root():
    return {
        "app": "Rural-Tech API",
        "status": "online",
        "documentation": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)

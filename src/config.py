import os
from dotenv import load_dotenv

# Cargar archivo .env si existe
load_dotenv()

class Settings:
    # URL de conexión de la base de datos de Supabase (usando asyncpg para llamadas asíncronas)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
    )
    
    # Secreto JWT para descodificar tokens emitidos por Supabase Auth
    # En producción, esto se obtiene de Supabase -> Settings -> API -> JWT Settings -> JWT Secret
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "super-secret-supabase-jwt-token")
    SUPABASE_JWT_ALGORITHM: str = "HS256"

    # Clave secreta para autorizar el registro de administradores
    ADMIN_REGISTRATION_SECRET: str = os.getenv("ADMIN_REGISTRATION_SECRET", "RuralTechAdmin2026!")

    # Credenciales de Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "https://nzilzfmicdorkadgudfi.supabase.co")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im56aWx6Zm1pY2RvcmthZGd1ZGZpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEyNzk2NzUsImV4cCI6MjA5Njg1NTY3NX0.o2nLLak2QNL8tC8SSYLS9PAQbu-r1et7v3XBrSrp0Bw")

settings = Settings()


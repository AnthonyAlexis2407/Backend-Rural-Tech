from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import base64
from ..config import settings
from ..database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

security = HTTPBearer()
_jwks_client = None

def get_jwks_client():
    global _jwks_client
    if _jwks_client is None:
        from jwt import PyJWKClient
        jwks_url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url)
    return _jwks_client

async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> str:
    """
    Dependency to validate Supabase Auth JWT token from Header and extract the user UUID.
    Also synchronizes the user profile in the local database.
    """
    token = credentials.credentials
    try:
        # Detectar el algoritmo utilizado en el token
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")
        
        if alg == "ES256":
            try:
                jwks_client = get_jwks_client()
                signing_key = jwks_client.get_signing_key_from_jwt(token)
                payload = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["ES256"],
                    audience="authenticated",
                    leeway=60
                )
            except Exception as e:
                # No fallback sin verificación: si falla JWKS, rechazar el token
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"No se pudo validar la firma del token (JWKS no disponible): {str(e)}",
                )
        else:
            secret = settings.SUPABASE_JWT_SECRET
            try:
                padded_secret = secret + "=" * (4 - len(secret) % 4)
                key = base64.b64decode(padded_secret)
            except Exception:
                key = secret
                
            payload = jwt.decode(
                token,
                key,
                algorithms=[alg],
                audience="authenticated",
                leeway=60
            )
        
        # El sub claim del token es el UUID del usuario
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token no contiene identificador de usuario (sub)",
            )

        # Sincronización automática del perfil en la base de datos local
        from ..repositories.repositories import PerfilRepository, RowObject
        from uuid import UUID
        
        repo = PerfilRepository(db)
        user_uuid = UUID(user_id)
        perfil = await repo.get_perfil_by_id(user_uuid)
        if not perfil:
            user_metadata = payload.get("user_metadata", {})
            email = payload.get("email") or ""
            nombre = user_metadata.get("nombre") or user_metadata.get("full_name") or email.split("@")[0] or "Usuario"
            rol = user_metadata.get("rol") or "estudiante"
            ubicacion = user_metadata.get("location") or user_metadata.get("ubicacion")
            
            perfil_data = RowObject({
                "id": user_uuid,
                "nombre": nombre,
                "email": email,
                "rol": rol,
                "ubicacion": ubicacion,
                "idioma_preferido": "es"
            })
            await repo.create_perfil(perfil_data)
            
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido: {str(e)}",
        )

async def get_current_admin_id(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
) -> str:
    """
    Dependency to ensure the current authenticated user has the 'administrador' role.
    """
    from ..repositories.repositories import PerfilRepository
    from uuid import UUID
    
    repo = PerfilRepository(db)
    perfil = await repo.get_perfil_by_id(UUID(user_id))
    if not perfil or perfil.rol != 'administrador':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operación permitida únicamente a administradores"
        )
    return user_id


from fastapi import APIRouter, Depends, HTTPException, status, Response, Query, Request, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..auth.dependencies import get_current_user_id, get_current_admin_id
from ..repositories.repositories import (
    CursoRepository, CertificadoRepository, NotificacionRepository, 
    InscripcionRepository, ArchivoDescargadoRepository, RowObject
)
from ..services.services import CursoService, SyncService
from ..schemas.schemas import (
    CursoResponse, CursoDetailResponse, InscripcionResponse, InscripcionCreate, 
    ProgresoLeccionUpdate, CertificadoResponse, NotificacionResponse, SincronizacionRequest, 
    SyncResult, UsuarioRegister, AdminRegister, CursoCreate, CursoUpdate, ModuloCreate, 
    ModuloUpdate, ModuloResponse, InscripcionDetailResponse, CursoMiniResponse,
    ArchivoDescargadoCreate, ArchivoDescargadoResponse
)
from uuid import UUID
from typing import List, Optional
import uuid
import jwt
import time
import json
from datetime import datetime, timezone
import aiofiles
import os
from ..config import settings
import httpx
from collections import defaultdict
from threading import Lock

# Simple in-memory rate limiter
class RateLimiter:
    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()
    
    def is_allowed(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            # Limpiar requests antiguos
            self._requests[key] = [t for t in self._requests[key] if now - t < self.window_seconds]
            if len(self._requests[key]) >= self.max_requests:
                return False
            self._requests[key].append(now)
            return True

# Rate limiter para endpoints de auth (5 requests por minuto por IP)
auth_rate_limiter = RateLimiter(max_requests=5, window_seconds=60)

async def check_rate_limit(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if not auth_rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas peticiones. Intente de nuevo en un minuto."
        )

# Routers
cursos_router = APIRouter(prefix="/cursos", tags=["Cursos"])
auth_router = APIRouter(prefix="/auth", tags=["Autenticación"])
archivos_descargados_router = APIRouter(prefix="/archivos-descargados", tags=["Archivos Descargados"])
uploads_router = APIRouter(prefix="/uploads", tags=["Subida de Archivos"])

@uploads_router.post("/")
async def upload_file(
    file: UploadFile = File(...),
    admin_id: str = Depends(get_current_admin_id)
):
    UPLOAD_DIR = "/tmp/uploads" if os.environ.get("VERCEL") else "uploads"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
        
    return {"status": "success", "url": f"/uploads/{unique_filename}"}

async def _create_supabase_user(
    email: str,
    password: str,
    nombre: str,
    location: str,
    rol: str,
) -> dict:
    """Crea un usuario en Supabase Auth usando la Admin API con httpx async."""
    secret = settings.SUPABASE_JWT_SECRET
    now = int(time.time())
    
    project_ref = settings.SUPABASE_URL.split("//")[-1].split(".")[0]
    
    jwt_claims = {
        "role": "service_role",
        "iss": "supabase",
        "ref": project_ref,
        "iat": now,
        "exp": now + 3600
    }
    service_role_token = jwt.encode(jwt_claims, secret, algorithm="HS256")

    url = f"{settings.SUPABASE_URL}/auth/v1/admin/users"
    
    headers = {
        "apikey": settings.SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {service_role_token}",
        "Content-Type": "application/json"
    }

    user_data = {
        "email": email,
        "password": password,
        "email_confirm": True,
        "user_metadata": {
            "nombre": nombre,
            "location": location,
            "rol": rol
        }
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, json=user_data, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            try:
                error_json = e.response.json()
                msg = error_json.get("msg") or error_json.get("message") or "Error en la creación de usuario"
            except Exception:
                msg = e.response.text
            raise HTTPException(
                status_code=e.response.status_code,
                detail=msg
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error de conexión con Supabase: {str(e)}"
            )


@auth_router.post("/register")
async def register_user(request: Request, payload: UsuarioRegister, _: None = Depends(check_rate_limit)):
    res = await _create_supabase_user(
        email=payload.email,
        password=payload.password,
        nombre=payload.nombre,
        location=payload.location,
        rol=payload.rol
    )
    return {"status": "success", "user_id": res.get("id")}


@auth_router.post("/register-admin")
async def register_admin(request: Request, payload: AdminRegister, _: None = Depends(check_rate_limit)):
    if payload.secreto != settings.ADMIN_REGISTRATION_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Código secreto de administración incorrecto"
        )

    res = await _create_supabase_user(
        email=payload.email,
        password=payload.password,
        nombre=payload.nombre,
        location=payload.location,
        rol="administrador"
    )
    return {"status": "success", "user_id": res.get("id")}


inscripciones_router = APIRouter(prefix="/inscripciones", tags=["Inscripciones"])
certificados_router = APIRouter(prefix="/certificados", tags=["Certificados"])
notificaciones_router = APIRouter(prefix="/notificaciones", tags=["Notificaciones"])
sync_router = APIRouter(prefix="/sincronizacion", tags=["Sincronización"])

# ==========================================
# CURSOS ROUTER
# ==========================================
@cursos_router.get("/", response_model=List[CursoResponse])
async def get_cursos(
    all: Optional[bool] = Query(False, description="Si es True, devuelve todos los cursos incluidos los no disponibles (solo admin)"),
    db: AsyncSession = Depends(get_db)
):
    repo = CursoRepository(db)
    disponible_only = not all
    return await repo.get_all_cursos(disponible_only=disponible_only)

@cursos_router.get("/{curso_id}", response_model=CursoDetailResponse)
async def get_curso_detail(curso_id: str, db: AsyncSession = Depends(get_db)):
    repo = CursoRepository(db)
    curso = await repo.get_curso_by_id(curso_id)
    if not curso:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    
    modulos = await repo.get_modulos_by_curso(curso_id)
    curso.modulo_list = modulos
    return curso

@cursos_router.post("/", response_model=CursoResponse)
async def create_curso(
    payload: CursoCreate,
    admin_id: str = Depends(get_current_admin_id),
    db: AsyncSession = Depends(get_db)
):
    service = CursoService(db)
    existing = await service.curso_repo.get_curso_by_id(payload.id)
    if existing:
        raise HTTPException(status_code=400, detail="El ID del curso ya está registrado")
    
    return await service.crear_curso(payload)

@cursos_router.put("/{curso_id}", response_model=CursoResponse)
async def update_curso(
    curso_id: str,
    payload: CursoUpdate,
    admin_id: str = Depends(get_current_admin_id),
    db: AsyncSession = Depends(get_db)
):
    service = CursoService(db)
    curso = await service.actualizar_curso(curso_id, payload)
    if not curso:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    return curso

@cursos_router.delete("/{curso_id}")
async def delete_curso(
    curso_id: str,
    admin_id: str = Depends(get_current_admin_id),
    db: AsyncSession = Depends(get_db)
):
    service = CursoService(db)
    success = await service.eliminar_curso(curso_id)
    if not success:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    return {"status": "success", "message": "Curso eliminado correctamente"}

@cursos_router.post("/{curso_id}/modulos", response_model=ModuloResponse)
async def create_modulo(
    curso_id: str,
    payload: ModuloCreate,
    admin_id: str = Depends(get_current_admin_id),
    db: AsyncSession = Depends(get_db)
):
    service = CursoService(db)
    curso = await service.curso_repo.get_curso_by_id(curso_id)
    if not curso:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    return await service.crear_modulo(curso_id, payload)

@cursos_router.put("/{curso_id}/modulos/{modulo_id}", response_model=ModuloResponse)
async def update_modulo(
    curso_id: str,
    modulo_id: UUID,
    payload: ModuloUpdate,
    admin_id: str = Depends(get_current_admin_id),
    db: AsyncSession = Depends(get_db)
):
    service = CursoService(db)
    modulo = await service.actualizar_modulo(modulo_id, payload)
    if not modulo:
        raise HTTPException(status_code=404, detail="Módulo no encontrado")
    return modulo

@cursos_router.delete("/{curso_id}/modulos/{modulo_id}")
async def delete_modulo(
    curso_id: str,
    modulo_id: UUID,
    admin_id: str = Depends(get_current_admin_id),
    db: AsyncSession = Depends(get_db)
):
    service = CursoService(db)
    success = await service.eliminar_modulo(modulo_id)
    if not success:
        raise HTTPException(status_code=404, detail="Módulo no encontrado")
    return {"status": "success", "message": "Módulo eliminado correctamente"}


# ==========================================
# INSCRIPCIONES ROUTER
# ==========================================
@inscripciones_router.post("/inscribir", response_model=InscripcionResponse)
async def inscribir_curso(
    payload: InscripcionCreate, 
    usuario_id: str = Depends(get_current_user_id), 
    db: AsyncSession = Depends(get_db)
):
    service = CursoService(db)
    try:
        usuario_uuid = UUID(usuario_id)
        insc = await service.inscribir_usuario(usuario_uuid, payload.curso_id, payload.tema_ui)
        return insc
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@inscripciones_router.delete("/desinscribir/{curso_id}")
async def desinscribir_curso(
    curso_id: str,
    usuario_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    service = CursoService(db)
    usuario_uuid = UUID(usuario_id)
    success = await service.desinscribir_usuario(usuario_uuid, curso_id)
    if not success:
        raise HTTPException(status_code=404, detail="Inscripción no encontrada")
    return {"status": "success", "message": "Desinscripción completada"}

@inscripciones_router.get("/mis-cursos", response_model=List[InscripcionResponse])
async def get_mis_cursos(
    usuario_id: str = Depends(get_current_user_id), 
    db: AsyncSession = Depends(get_db)
):
    repo = InscripcionRepository(db)
    usuario_uuid = UUID(usuario_id)
    return await repo.get_inscripciones_by_usuario(usuario_uuid)

@inscripciones_router.get("/mis-cursos/detalle", response_model=List[InscripcionDetailResponse])
async def get_mis_cursos_detalle(
    usuario_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Devuelve las inscripciones del usuario con los datos del curso incluidos"""
    repo = InscripcionRepository(db)
    usuario_uuid = UUID(usuario_id)
    inscripciones = await repo.get_inscripciones_with_curso(usuario_uuid)
    
    result = []
    for insc in inscripciones:
        insc_data = InscripcionDetailResponse(
            id=insc.id,
            usuario_id=insc.usuario_id,
            curso_id=insc.curso_id,
            progreso=insc.progreso,
            descargado=insc.descargado,
            modulo_actual_id=insc.modulo_actual_id,
            tema_ui=insc.tema_ui,
            inscrito_en=insc.inscrito_en,
            completado_en=insc.completado_en,
            actualizado_en=insc.actualizado_en,
            curso=CursoMiniResponse(
                id=insc.curso.id,
                titulo=insc.curso.titulo,
                descripcion=insc.curso.descripcion,
                categoria=insc.curso.categoria,
                duracion=insc.curso.duracion,
                modulos=insc.curso.modulos,
                nivel=insc.curso.nivel,
                instructor=insc.curso.instructor,
                imagen=insc.curso.imagen,
                color=insc.curso.color,
                disponible=insc.curso.disponible
            ) if insc.curso else None
        )
        result.append(insc_data)
    
    return result

@inscripciones_router.get("/progreso-lecciones")
async def get_progreso_lecciones(
    usuario_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    repo = InscripcionRepository(db)
    usuario_uuid = UUID(usuario_id)
    res = await repo.get_all_progreso_lecciones_by_usuario(usuario_uuid)
    return [
        {
            "id": str(r.id),
            "inscripcionId": str(r.inscripcion_id),
            "moduleId": str(r.modulo_id),
            "completed": r.completado,
            "score": r.puntaje_evaluacion,
            "completedAt": r.completado_en.isoformat() if r.completado_en else None,
            "courseId": r.curso_id
        }
        for r in res
    ]

@inscripciones_router.post("/progreso-leccion")
async def update_progreso(
    curso_id: str,
    payload: ProgresoLeccionUpdate,
    usuario_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    service = CursoService(db)
    usuario_uuid = UUID(usuario_id)
    res = await service.registrar_progreso_modulo(
        usuario_id=usuario_uuid,
        curso_id=curso_id,
        modulo_id=payload.modulo_id,
        completado=payload.completado,
        score=payload.puntaje_evaluacion
    )
    return res

# ==========================================
# CERTIFICADOS ROUTER
# ==========================================
@certificados_router.get("/", response_model=List[CertificadoResponse])
async def get_certificados(
    usuario_id: str = Depends(get_current_user_id), 
    db: AsyncSession = Depends(get_db)
):
    repo = CertificadoRepository(db)
    usuario_uuid = UUID(usuario_id)
    return await repo.get_certificados_by_usuario(usuario_uuid)

@certificados_router.get("/descargar/{codigo_certificado}")
async def descargar_certificado(
    codigo_certificado: str,
    usuario_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    repo = CertificadoRepository(db)
    usuario_uuid = UUID(usuario_id)
    
    # Encontrar por código y validar pertenencia
    certificados = await repo.get_certificados_by_usuario(usuario_uuid)
    cert = next((c for c in certificados if c.codigo_certificado == codigo_certificado), None)
    
    if not cert:
        raise HTTPException(status_code=404, detail="Certificado no encontrado o no pertenece al usuario")

    # Generar un contenido de certificado descargable dinámicamente como HTML premium
    from ..repositories.repositories import PerfilRepository
    perfil_repo = PerfilRepository(db)
    perfil = await perfil_repo.get_perfil_by_id(usuario_uuid)
    nombre_estudiante = perfil.nombre if perfil else "Estudiante Rural-Tech"

    curso_repo = CursoRepository(db)
    curso = await curso_repo.get_curso_by_id(cert.curso_id)
    titulo_curso = curso.titulo if curso else cert.curso_id.upper()
    instructor_curso = curso.instructor if curso else "Instructor Rural-Tech"
    
    fecha_emision = cert.emitido_en.strftime('%d/%m/%Y')

    contenido = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Certificado de Aprobación - Rural-Tech</title>
  <style>
    body {{
      font-family: 'Georgia', serif;
      background-color: #f7f9fc;
      margin: 0;
      padding: 0;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      -webkit-print-color-adjust: exact;
    }}
    .certificate-container {{
      width: 850px;
      height: 600px;
      padding: 30px;
      border: 12px double #1e3a5f;
      background-color: #ffffff;
      box-shadow: 0 4px 25px rgba(0, 0, 0, 0.1);
      position: relative;
      box-sizing: border-box;
      background-image: radial-gradient(circle, #ffffff 60%, #f4f7fa 100%);
    }}
    .inner-border {{
      border: 2px solid #c9a054;
      height: 100%;
      padding: 35px;
      box-sizing: border-box;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: space-between;
      text-align: center;
    }}
    .ribbon {{
      font-size: 50px;
      margin-bottom: 5px;
      color: #c9a054;
    }}
    .header {{
      font-size: 32px;
      color: #1e3a5f;
      letter-spacing: 3px;
      font-weight: bold;
      text-transform: uppercase;
      margin: 0;
    }}
    .sub-header {{
      font-size: 14px;
      color: #5c6b73;
      margin-top: 5px;
      margin-bottom: 15px;
      text-transform: uppercase;
      letter-spacing: 5px;
      font-weight: bold;
    }}
    .certifies {{
      font-style: italic;
      font-size: 18px;
      color: #4a4a4a;
      margin: 5px 0;
    }}
    .student-name {{
      font-size: 40px;
      color: #c9a054;
      border-bottom: 2px solid #c9a054;
      padding-bottom: 8px;
      margin: 10px 0;
      font-weight: bold;
      font-family: 'Times New Roman', Times, serif;
      min-width: 450px;
    }}
    .course-text {{
      font-size: 16px;
      color: #4a4a4a;
      margin: 5px 0;
    }}
    .course-title {{
      font-size: 26px;
      color: #1e3a5f;
      margin: 8px 0;
      font-weight: bold;
      text-transform: uppercase;
      letter-spacing: 1px;
    }}
    .footer-section {{
      display: flex;
      justify-content: space-between;
      width: 100%;
      margin-top: 25px;
      padding-top: 15px;
      border-top: 1px solid #e2e8f0;
    }}
    .meta-box {{
      text-align: left;
      font-size: 12px;
      color: #64748b;
      line-height: 1.6;
    }}
    .signature-box {{
      display: flex;
      flex-direction: column;
      align-items: center;
      font-size: 13px;
      color: #334155;
    }}
    .signature-line {{
      width: 180px;
      border-top: 1px dashed #94a3b8;
      margin-bottom: 5px;
    }}
    .badge-seal {{
      position: absolute;
      bottom: 100px;
      right: 80px;
      width: 80px;
      height: 80px;
      border: 3px double #c9a054;
      border-radius: 50%;
      display: flex;
      justify-content: center;
      align-items: center;
      font-size: 11px;
      color: #c9a054;
      font-weight: bold;
      text-transform: uppercase;
      transform: rotate(-15deg);
      background: #fff;
    }}
    @media print {{
      body {{
        background: none;
      }}
      .certificate-container {{
        box-shadow: none;
        margin: 0;
        page-break-inside: avoid;
      }}
    }}
  </style>
</head>
<body>
  <div class="certificate-container">
    <div class="inner-border">
      <div class="ribbon">🎓</div>
      <div class="header">Rural-Tech Educa</div>
      <div class="sub-header">Certificado de Aprobación</div>
      
      <div class="certifies">Otorgado a:</div>
      <div class="student-name">{nombre_estudiante}</div>
      
      <div class="course-text">Por completar satisfactoriamente y aprobar todas las evaluaciones del curso técnico:</div>
      <div class="course-title">"{titulo_curso}"</div>
      
      <div class="footer-section">
        <div class="meta-box">
          <strong>Código de Validación:</strong> {cert.codigo_certificado}<br>
          <strong>Fecha de Emisión:</strong> {fecha_emision}<br>
          <strong>Verificación:</strong> ruraltech.org/certs/{cert.codigo_certificado}
        </div>
        <div class="signature-box">
          <div class="signature-line"></div>
          <strong>{instructor_curso}</strong>
          <span>Docente Principal</span>
        </div>
      </div>
    </div>
    <div class="badge-seal">Oficial<br>Rural-Tech</div>
  </div>
</body>
</html>
"""
    
    headers = {
        "Content-Disposition": f"attachment; filename=Certificado_{cert.curso_id}_{codigo_certificado}.html"
    }
    return Response(content=contenido, media_type="text/html", headers=headers)

# ==========================================
# NOTIFICACIONES ROUTER
# ==========================================
@notificaciones_router.get("/", response_model=List[NotificacionResponse])
async def get_notificaciones(
    usuario_id: str = Depends(get_current_user_id), 
    db: AsyncSession = Depends(get_db)
):
    repo = NotificacionRepository(db)
    usuario_uuid = UUID(usuario_id)
    return await repo.get_notificaciones_by_usuario(usuario_uuid)

@notificaciones_router.put("/{notif_id}/leer")
async def mark_read(
    notif_id: UUID,
    usuario_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    repo = NotificacionRepository(db)
    notif = await repo.get_notificacion_by_id(notif_id)
    if not notif or str(notif.usuario_id) != usuario_id:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    
    notif.leido = True
    await repo.save_notificacion(notif)
    return {"status": "ok"}

@notificaciones_router.delete("/{notif_id}")
async def delete_notif(
    notif_id: UUID,
    usuario_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    repo = NotificacionRepository(db)
    notif = await repo.get_notificacion_by_id(notif_id)
    if not notif or str(notif.usuario_id) != usuario_id:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    
    await repo.delete_notificacion(notif)
    return {"status": "deleted"}

# ==========================================
# SINCRONIZACIÓN ROUTER
# ==========================================
@sync_router.post("/sync", response_model=SyncResult)
async def sync_offline_actions(
    payload: SincronizacionRequest,
    usuario_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    service = SyncService(db)
    usuario_uuid = UUID(usuario_id)
    acciones_dict = [a.model_dump() for a in payload.acciones]
    res = await service.procesar_cola_sincronizacion(
        usuario_id=usuario_uuid,
        acciones=acciones_dict,
        nodo_id=payload.nodo_id,
        almacenamiento_usado_gb=payload.almacenamiento_usado_gb,
        almacenamiento_max_gb=payload.almacenamiento_max_gb,
        version_app=payload.version_app
    )
    return res


# ==========================================
# LOGROS Y FAQS ROUTERS
# ==========================================
logros_router = APIRouter(prefix="/logros", tags=["Logros"])
faqs_router = APIRouter(prefix="/faqs", tags=["Preguntas Frecuentes"])

from ..repositories.repositories import LogroRepository, PreguntasFrecuentesRepository
from ..schemas.schemas import LogroResponse, PreguntaFrecuenteResponse

@logros_router.get("/mis-logros", response_model=List[LogroResponse])
async def get_mis_logros(
    usuario_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    repo = LogroRepository(db)
    usuario_uuid = UUID(usuario_id)
    return await repo.get_logros_by_usuario(usuario_uuid)

@faqs_router.get("/", response_model=List[PreguntaFrecuenteResponse])
async def get_faqs(
    usuario_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    repo = PreguntasFrecuentesRepository(db)
    return await repo.get_active_faqs()

# ==========================================
# INSCRIPCION DOWNLOAD ROUTE
# ==========================================
@inscripciones_router.put("/descargado/{curso_id}")
async def update_inscripcion_descargado(
    curso_id: str,
    descargado: bool = True,
    usuario_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    repo = InscripcionRepository(db)
    usuario_uuid = UUID(usuario_id)
    success = await repo.update_inscripcion_descargado(usuario_uuid, curso_id, descargado)
    if not success:
        raise HTTPException(status_code=404, detail="Inscripción no encontrada")
    return {"status": "success", "message": "Estado de descarga actualizado"}

# ==========================================
# ARCHIVOS DESCARGADOS ROUTER
# ==========================================
@archivos_descargados_router.get("/", response_model=List[ArchivoDescargadoResponse])
async def get_archivos_descargados(
    usuario_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    repo = ArchivoDescargadoRepository(db)
    usuario_uuid = UUID(usuario_id)
    return await repo.get_archivos_by_usuario(usuario_uuid)

@archivos_descargados_router.post("/", response_model=ArchivoDescargadoResponse)
async def create_archivo_descargado(
    payload: ArchivoDescargadoCreate,
    usuario_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    repo = ArchivoDescargadoRepository(db)
    usuario_uuid = UUID(usuario_id)
    
    archivo = RowObject({
        "id": uuid.uuid4(),
        "usuario_id": usuario_uuid,
        "curso_id": payload.curso_id,
        "nombre_archivo": payload.nombre_archivo,
        "tamano": payload.tamano,
        "tipo": payload.tipo,
        "url_local": payload.url_local,
        "descargado_en": datetime.now(timezone.utc),
        "eliminado_en": None
    })
    
    await repo.save_archivo_descargado(archivo)
    return archivo

@archivos_descargados_router.delete("/{nombre_archivo:path}")
async def delete_archivo_descargado(
    nombre_archivo: str,
    usuario_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    repo = ArchivoDescargadoRepository(db)
    usuario_uuid = UUID(usuario_id)
    success = await repo.delete_archivo_descargado_by_name(usuario_uuid, nombre_archivo)
    if not success:
        raise HTTPException(status_code=404, detail="Archivo descargado no encontrado")
    return {"status": "success", "message": "Archivo marcado como eliminado correctamente"}

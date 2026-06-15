from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..auth.dependencies import get_current_user_id, get_current_admin_id
from ..repositories.repositories import CursoRepository, CertificadoRepository, NotificacionRepository, InscripcionRepository
from ..services.services import CursoService, SyncService
from ..schemas.schemas import (
    CursoResponse, CursoDetailResponse, InscripcionResponse, InscripcionCreate, 
    ProgresoLeccionUpdate, CertificadoResponse, NotificacionResponse, SincronizacionRequest, 
    SyncResult, UsuarioRegister, AdminRegister, CursoCreate, CursoUpdate, ModuloCreate, 
    ModuloUpdate, ModuloResponse, InscripcionDetailResponse, CursoMiniResponse
)
from uuid import UUID
from typing import List, Optional
import uuid
import jwt
import time
import urllib.request
import json
from ..config import settings

# Routers
cursos_router = APIRouter(prefix="/cursos", tags=["Cursos"])
auth_router = APIRouter(prefix="/auth", tags=["Autenticación"])

@auth_router.post("/register")
async def register_user(payload: UsuarioRegister):
    secret = settings.SUPABASE_JWT_SECRET
    now = int(time.time())
    
    # Extraer el project ref de la URL de Supabase para los claims del JWT
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
        "email": payload.email,
        "password": payload.password,
        "email_confirm": True,
        "user_metadata": {
            "nombre": payload.nombre,
            "location": payload.location,
            "rol": payload.rol
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(user_data).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        def do_request():
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode("utf-8"))
        
        res = await loop.run_in_executor(None, do_request)
        return {"status": "success", "user_id": res.get("id")}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        try:
            error_json = json.loads(error_body)
            msg = error_json.get("msg") or error_json.get("message") or "Error en la creación de usuario"
        except Exception:
            msg = error_body
        raise HTTPException(
            status_code=e.code,
            detail=msg
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno: {str(e)}"
        )

@auth_router.post("/register-admin")
async def register_admin(payload: AdminRegister):
    if payload.secreto != settings.ADMIN_REGISTRATION_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Código secreto de administración incorrecto"
        )

    secret = settings.SUPABASE_JWT_SECRET
    now = int(time.time())
    
    # Extraer el project ref de la URL de Supabase para los claims del JWT
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
        "email": payload.email,
        "password": payload.password,
        "email_confirm": True,
        "user_metadata": {
            "nombre": payload.nombre,
            "location": payload.location,
            "rol": "administrador"
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(user_data).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        def do_request():
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode("utf-8"))
        
        res = await loop.run_in_executor(None, do_request)
        return {"status": "success", "user_id": res.get("id")}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        try:
            error_json = json.loads(error_body)
            msg = error_json.get("msg") or error_json.get("message") or "Error en la creación del administrador"
        except Exception:
            msg = error_body
        raise HTTPException(
            status_code=e.code,
            detail=msg
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno: {str(e)}"
        )


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

    # Generar un contenido de certificado descargable dinámicamente como texto plano
    contenido = f"""
    RURAL-TECH EDUCA
    ======================================
    CERTIFICADO DE APROBACIÓN
    
    Se certifica que el usuario con ID: {usuario_uuid}
    ha aprobado satisfactoriamente todas las evaluaciones del curso: {cert.curso_id.upper()}
    
    Código de Certificación: {cert.codigo_certificado}
    Fecha de Emisión: {cert.emitido_en.strftime('%Y-%m-%d %H:%M:%S')}
    
    ======================================
    Verificación disponible en: https://ruraltech.org/certs/{cert.codigo_certificado}
    """
    
    headers = {
        "Content-Disposition": f"attachment; filename=Certificado_{cert.curso_id}_{codigo_certificado}.txt"
    }
    return Response(content=contenido, media_type="text/plain", headers=headers)

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
    await db.flush()
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
    res = await service.procesar_cola_sincronizacion(usuario_uuid, acciones_dict)
    return res

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from uuid import UUID
from typing import List, Optional, Any

class RowObject(dict):
    def __init__(self, mapping):
        super().__init__(mapping or {})

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'RowObject' object has no attribute '{name}'")

    def __setattr__(self, name, value):
        self[name] = value

    def model_dump(self, **kwargs):
        return self


def to_dict(obj: Any) -> dict:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return dict(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return {}


class CursoRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_cursos(self, disponible_only: bool = True) -> List[RowObject]:
        res = await self.db.execute(text("SELECT * FROM fn_get_cursos(:disponible)"), {"disponible": disponible_only})
        return [RowObject(r) for r in res.mappings().all()]

    async def get_curso_by_id(self, curso_id: str) -> Optional[RowObject]:
        res = await self.db.execute(
            text("SELECT * FROM fn_get_curso_by_id(:id)"),
            {"id": curso_id}
        )
        row = res.mappings().one_or_none()
        return RowObject(row) if row else None

    async def get_modulos_by_curso(self, curso_id: str) -> List[RowObject]:
        res = await self.db.execute(
            text("SELECT * FROM fn_get_modulos_by_curso(:curso_id)"),
            {"curso_id": curso_id}
        )
        return [RowObject(r) for r in res.mappings().all()]

    async def get_modulo_by_id(self, modulo_id: UUID) -> Optional[RowObject]:
        res = await self.db.execute(
            text("SELECT * FROM fn_get_modulo_by_id(:id)"),
            {"id": modulo_id}
        )
        row = res.mappings().one_or_none()
        return RowObject(row) if row else None

    async def create_curso(self, curso: Any) -> Any:
        params = to_dict(curso)
        await self.db.execute(
            text("SELECT fn_create_curso(:id, :titulo, :descripcion, :categoria, :duracion, :modulos, :nivel, :instructor, :imagen, :color, :disponible)"),
            params
        )
        return curso

    async def update_curso(self, curso: Any = None) -> None:
        if curso is not None:
            params = to_dict(curso)
            await self.db.execute(
                text("SELECT fn_update_curso(:id, :titulo, :descripcion, :categoria, :duracion, :modulos, :nivel, :instructor, :imagen, :color, :disponible)"),
                params
            )

    async def delete_curso(self, curso: Any) -> None:
        curso_id = curso.id if hasattr(curso, "id") else (curso["id"] if isinstance(curso, dict) else curso)
        await self.db.execute(
            text("SELECT fn_delete_curso(:id)"),
            {"id": curso_id}
        )

    async def create_modulo(self, modulo: Any) -> Any:
        params = to_dict(modulo)
        await self.db.execute(
            text("SELECT fn_create_modulo(:id, :curso_id, :titulo, :descripcion, :orden, :tipo_contenido, :contenido_url, :duracion_minutos)"),
            params
        )
        return modulo

    async def update_modulo(self, modulo: Any = None) -> None:
        if modulo is not None:
            params = to_dict(modulo)
            await self.db.execute(
                text("SELECT fn_update_modulo(:id, :titulo, :descripcion, :orden, :tipo_contenido, :contenido_url, :duracion_minutos)"),
                params
            )

    async def delete_modulo(self, modulo: Any) -> None:
        modulo_id = modulo.id if hasattr(modulo, "id") else (modulo["id"] if isinstance(modulo, dict) else modulo)
        await self.db.execute(
            text("SELECT fn_delete_modulo(:id)"),
            {"id": modulo_id}
        )


class PerfilRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_perfil_by_id(self, perfil_id: UUID) -> Optional[RowObject]:
        res = await self.db.execute(
            text("SELECT * FROM fn_get_perfil_by_id(:id)"),
            {"id": perfil_id}
        )
        row = res.mappings().one_or_none()
        return RowObject(row) if row else None

    async def create_perfil(self, perfil: Any) -> Any:
        params = to_dict(perfil)
        await self.db.execute(
            text("SELECT fn_upsert_perfil(:id, :nombre, :email, :rol, :ubicacion, :idioma_preferido)"),
            {
                "id": params.get("id"),
                "nombre": params.get("nombre"),
                "email": params.get("email"),
                "rol": params.get("rol"),
                "ubicacion": params.get("ubicacion"),
                "idioma_preferido": params.get("idioma_preferido") or "es"
            }
        )
        return perfil


class InscripcionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_inscripcion(self, usuario_id: UUID, curso_id: str) -> Optional[RowObject]:
        res = await self.db.execute(
            text("SELECT * FROM fn_get_inscripcion(:usuario_id, :curso_id)"),
            {"usuario_id": usuario_id, "curso_id": curso_id}
        )
        row = res.mappings().one_or_none()
        return RowObject(row) if row else None

    async def get_inscripciones_by_usuario(self, usuario_id: UUID) -> List[RowObject]:
        res = await self.db.execute(
            text("SELECT * FROM fn_get_inscripciones_by_usuario(:usuario_id)"),
            {"usuario_id": usuario_id}
        )
        return [RowObject(r) for r in res.mappings().all()]

    async def get_inscripciones_with_curso(self, usuario_id: UUID) -> List[RowObject]:
        res = await self.db.execute(
            text("SELECT * FROM fn_get_inscripciones_with_curso(:usuario_id)"),
            {"usuario_id": usuario_id}
        )
        results = []
        for r in res.mappings().all():
            course_data = {
                "id": r["curso_id"],
                "titulo": r["curso_titulo"],
                "descripcion": r["curso_descripcion"],
                "categoria": r["curso_categoria"],
                "duracion": r["curso_duracion"],
                "modulos": r["curso_modulos"],
                "nivel": r["curso_nivel"],
                "instructor": r["curso_instructor"],
                "imagen": r["curso_imagen"],
                "color": r["curso_color"],
                "disponible": r["curso_disponible"]
            }
            insc_dict = {
                "id": r["insc_id"],
                "usuario_id": r["usuario_id"],
                "curso_id": r["curso_id"],
                "progreso": r["progreso"],
                "descargado": r["descargado"],
                "modulo_actual_id": r["modulo_actual_id"],
                "tema_ui": r["tema_ui"],
                "inscrito_en": r["inscrito_en"],
                "completado_en": r["completado_en"],
                "actualizado_en": r["actualizado_en"],
                "curso": RowObject(course_data)
            }
            results.append(RowObject(insc_dict))
        return results

    async def get_progreso_lecciones(self, inscripcion_id: UUID) -> List[RowObject]:
        res = await self.db.execute(
            text("SELECT * FROM fn_get_progreso_lecciones(:inscripcion_id)"),
            {"inscripcion_id": inscripcion_id}
        )
        return [RowObject(r) for r in res.mappings().all()]

    async def get_progreso_modulo(self, inscripcion_id: UUID, modulo_id: UUID) -> Optional[RowObject]:
        res = await self.db.execute(
            text("SELECT * FROM fn_get_progreso_modulo(:inscripcion_id, :modulo_id)"),
            {"inscripcion_id": inscripcion_id, "modulo_id": modulo_id}
        )
        row = res.mappings().one_or_none()
        return RowObject(row) if row else None

    async def get_all_progreso_lecciones_by_usuario(self, usuario_id: UUID) -> List[RowObject]:
        res = await self.db.execute(
            text("SELECT * FROM fn_get_all_progreso_lecciones_by_usuario(:usuario_id)"),
            {"usuario_id": usuario_id}
        )
        return [RowObject(r) for r in res.mappings().all()]

    async def save_inscripcion(self, inscripcion: Any) -> Any:
        params = to_dict(inscripcion)
        res = await self.db.execute(
            text("SELECT * FROM fn_save_inscripcion(:id, :usuario_id, :curso_id, :progreso, :descargado, :modulo_actual_id, :tema_ui, :completado_en)"),
            params
        )
        row = res.mappings().one()
        if hasattr(inscripcion, "__setitem__") or isinstance(inscripcion, dict):
            inscripcion["inscrito_en"] = row["inscrito_en"]
            inscripcion["actualizado_en"] = row["actualizado_en"]
        else:
            inscripcion.inscrito_en = row["inscrito_en"]
            inscripcion.actualizado_en = row["actualizado_en"]
        return inscripcion

    async def save_progreso_leccion(self, progreso: Any) -> Any:
        import logging
        logger = logging.getLogger(__name__)
        params = to_dict(progreso)
        logger.debug(f"Guardando progreso de lección con params: {params}")
        try:
            result = await self.db.execute(
                text("SELECT fn_save_progreso_leccion(:id, :inscripcion_id, :modulo_id, :completado, :puntaje_evaluacion, :completado_en)"),
                params
            )
            logger.info(f"Progreso de lección guardado exitosamente: id={params.get('id')}, inscripcion_id={params.get('inscripcion_id')}, modulo_id={params.get('modulo_id')}, completado={params.get('completado')}")
        except Exception as e:
            logger.error(f"Error al guardar progreso de lección: {str(e)}", exc_info=True)
            raise
        return progreso

    async def delete_inscripcion(self, inscripcion: Any) -> None:
        insc_id = inscripcion.id if hasattr(inscripcion, "id") else (inscripcion["id"] if isinstance(inscripcion, dict) else inscripcion)
        await self.db.execute(
            text("SELECT fn_delete_inscripcion(:id)"),
            {"id": insc_id}
        )

    async def update_inscripcion_descargado(self, usuario_id: UUID, curso_id: str, descargado: bool) -> bool:
        res = await self.db.execute(
            text("SELECT fn_update_inscripcion_descargado(:usuario_id, :curso_id, :descargado) as updated"),
            {"usuario_id": usuario_id, "curso_id": curso_id, "descargado": descargado}
        )
        row = res.mappings().one()
        return row["updated"]


class CertificadoRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_certificados_by_usuario(self, usuario_id: UUID) -> List[RowObject]:
        res = await self.db.execute(
            text("SELECT * FROM fn_get_certificados_by_usuario(:usuario_id)"),
            {"usuario_id": usuario_id}
        )
        return [RowObject(r) for r in res.mappings().all()]

    async def get_certificado(self, usuario_id: UUID, curso_id: str) -> Optional[RowObject]:
        res = await self.db.execute(
            text("SELECT * FROM fn_get_certificado(:usuario_id, :curso_id)"),
            {"usuario_id": usuario_id, "curso_id": curso_id}
        )
        row = res.mappings().one_or_none()
        return RowObject(row) if row else None

    async def save_certificado(self, certificado: Any) -> Any:
        params = to_dict(certificado)
        await self.db.execute(
            text("SELECT fn_save_certificado(:id, :usuario_id, :curso_id, :codigo_certificado, :url_certificado)"),
            params
        )
        return certificado


class NotificacionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_notificaciones_by_usuario(self, usuario_id: UUID) -> List[RowObject]:
        res = await self.db.execute(
            text("SELECT * FROM fn_get_notificaciones_by_usuario(:usuario_id)"),
            {"usuario_id": usuario_id}
        )
        return [RowObject(r) for r in res.mappings().all()]

    async def get_notificacion_by_id(self, notif_id: UUID) -> Optional[RowObject]:
        res = await self.db.execute(
            text("SELECT * FROM fn_get_notificacion_by_id(:id)"),
            {"id": notif_id}
        )
        row = res.mappings().one_or_none()
        return RowObject(row) if row else None

    async def save_notificacion(self, notif: Any) -> Any:
        params = to_dict(notif)
        await self.db.execute(
            text("SELECT fn_save_notificacion(:id, :usuario_id, :tipo, :titulo, :mensaje, :leido, :ruta_accion)"),
            params
        )
        return notif

    async def delete_notificacion(self, notif: Any) -> None:
        notif_id = notif.id if hasattr(notif, "id") else (notif["id"] if isinstance(notif, dict) else notif)
        await self.db.execute(
            text("SELECT fn_delete_notificacion(:id)"),
            {"id": notif_id}
        )

    async def notify_all_users_new_course(self, curso_id: str, curso_titulo: str) -> None:
        await self.db.execute(
            text("SELECT fn_notify_all_users_new_course(:curso_id, :curso_titulo)"),
            {"curso_id": curso_id, "curso_titulo": curso_titulo}
        )


class ArchivoDescargadoRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_archivos_by_usuario(self, usuario_id: UUID) -> List[RowObject]:
        res = await self.db.execute(
            text("SELECT * FROM fn_get_archivos_by_usuario(:usuario_id)"),
            {"usuario_id": usuario_id}
        )
        return [RowObject(r) for r in res.mappings().all()]

    async def save_archivo_descargado(self, archivo: Any) -> Any:
        params = to_dict(archivo)
        await self.db.execute(
            text("SELECT fn_save_archivo_descargado(:id, :usuario_id, :curso_id, :nombre_archivo, :tamano, :tipo, :url_local)"),
            params
        )
        return archivo

    async def delete_archivo_descargado_by_name(self, usuario_id: UUID, nombre_archivo: str) -> bool:
        res = await self.db.execute(
            text("SELECT fn_delete_archivo_descargado_by_name(:usuario_id, :nombre_archivo) as updated"),
            {"usuario_id": usuario_id, "nombre_archivo": nombre_archivo}
        )
        row = res.mappings().one()
        return row["updated"]


class NodoRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert_nodo(
        self, 
        nodo_id: str, 
        usuario_id: UUID, 
        almacenamiento_usado_gb: float, 
        almacenamiento_max_gb: float, 
        version_app: str
    ) -> None:
        await self.db.execute(
            text("SELECT fn_upsert_nodo(:id, :usuario_id, :usado, :max, :version)"),
            {
                "id": nodo_id,
                "usuario_id": usuario_id,
                "usado": almacenamiento_usado_gb,
                "max": almacenamiento_max_gb,
                "version": version_app
            }
        )


class ColaSincronizacionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_sync_log(
        self, 
        usuario_id: UUID, 
        nodo_id: Optional[str], 
        accion: str, 
        payload: dict, 
        estado: str, 
        error_msg: Optional[str] = None
    ) -> None:
        import json
        try:
            await self.db.execute(
                text("SELECT fn_save_sync_log(:usuario_id, :nodo_id, :accion, :payload, :estado, :error_msg)"),
                {
                    "usuario_id": usuario_id,
                    "nodo_id": nodo_id,
                    "accion": accion,
                    "payload": json.dumps(payload),
                    "estado": estado,
                    "error_msg": error_msg
                }
            )
        except Exception as e:
            print(f"Error registrando log de sincronización en DB: {e}")


class PreguntasFrecuentesRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_faqs(self) -> List[RowObject]:
        res = await self.db.execute(
            text("SELECT * FROM fn_get_active_faqs()")
        )
        return [RowObject(r) for r in res.mappings().all()]


class LogroRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_logros(self) -> List[RowObject]:
        res = await self.db.execute(
            text("SELECT * FROM fn_get_all_logros()")
        )
        return [RowObject(r) for r in res.mappings().all()]

    async def get_logros_by_usuario(self, usuario_id: UUID) -> List[RowObject]:
        res = await self.db.execute(
            text("SELECT * FROM fn_get_logros_by_usuario(:usuario_id)"),
            {"usuario_id": usuario_id}
        )
        return [RowObject(r) for r in res.mappings().all()]

    async def unlock_logro(self, usuario_id: UUID, logro_id: str) -> None:
        await self.db.execute(
            text("SELECT fn_unlock_logro(:usuario_id, :logro_id)"),
            {"usuario_id": usuario_id, "logro_id": logro_id}
        )

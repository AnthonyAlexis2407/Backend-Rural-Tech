from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from uuid import UUID
from typing import List, Optional, Any

class RowObject:
    def __init__(self, mapping):
        self.__dict__.update(mapping)

    def __getattr__(self, name):
        try:
            return self.__dict__[name]
        except KeyError:
            raise AttributeError(f"'RowObject' object has no attribute '{name}'")

    def __setattr__(self, name, value):
        self.__dict__[name] = value

    def __getitem__(self, key):
        return self.__dict__[key]

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def get(self, key, default=None):
        return self.__dict__.get(key, default)

    def model_dump(self, **kwargs):
        return self.__dict__

class CursoRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_cursos(self, disponible_only: bool = True) -> List[RowObject]:
        sql = "SELECT id, titulo, descripcion, categoria, duracion, modulos, nivel, instructor, imagen, color, disponible, creado_en, actualizado_en FROM cursos"
        if disponible_only:
            sql += " WHERE disponible = TRUE"
        res = await self.db.execute(text(sql))
        return [RowObject(r) for r in res.mappings().all()]

    async def get_curso_by_id(self, curso_id: str) -> Optional[RowObject]:
        res = await self.db.execute(
            text("SELECT id, titulo, descripcion, categoria, duracion, modulos, nivel, instructor, imagen, color, disponible, creado_en, actualizado_en FROM cursos WHERE id = :id"),
            {"id": curso_id}
        )
        row = res.mappings().one_or_none()
        return RowObject(row) if row else None

    async def get_modulos_by_curso(self, curso_id: str) -> List[RowObject]:
        res = await self.db.execute(
            text("SELECT id, curso_id, titulo, descripcion, orden, tipo_contenido, contenido_url, duracion_minutos FROM modulos WHERE curso_id = :curso_id ORDER BY orden"),
            {"curso_id": curso_id}
        )
        return [RowObject(r) for r in res.mappings().all()]

    async def get_modulo_by_id(self, modulo_id: UUID) -> Optional[RowObject]:
        res = await self.db.execute(
            text("SELECT id, curso_id, titulo, descripcion, orden, tipo_contenido, contenido_url, duracion_minutos FROM modulos WHERE id = :id"),
            {"id": modulo_id}
        )
        row = res.mappings().one_or_none()
        return RowObject(row) if row else None

    async def create_curso(self, curso: Any) -> Any:
        params = curso.__dict__ if hasattr(curso, "__dict__") else curso
        await self.db.execute(
            text("""
                INSERT INTO cursos (id, titulo, descripcion, categoria, duracion, modulos, nivel, instructor, imagen, color, disponible)
                VALUES (:id, :titulo, :descripcion, CAST(:categoria AS categoria_curso), :duracion, :modulos, CAST(:nivel AS nivel_curso), :instructor, :imagen, :color, :disponible)
            """),
            params
        )
        return curso

    async def update_curso(self, curso: Any = None) -> None:
        if curso is not None:
            params = curso.__dict__ if hasattr(curso, "__dict__") else curso
            await self.db.execute(
                text("""
                    UPDATE cursos 
                    SET titulo = :titulo, descripcion = :descripcion, categoria = CAST(:categoria AS categoria_curso), 
                        duracion = :duracion, modulos = :modulos, nivel = CAST(:nivel AS nivel_curso), 
                        instructor = :instructor, imagen = :imagen, color = :color, disponible = :disponible
                    WHERE id = :id
                """),
                params
            )

    async def delete_curso(self, curso: Any) -> None:
        curso_id = curso.id if hasattr(curso, "id") else (curso["id"] if isinstance(curso, dict) else curso)
        await self.db.execute(
            text("DELETE FROM cursos WHERE id = :id"),
            {"id": curso_id}
        )

    async def create_modulo(self, modulo: Any) -> Any:
        params = modulo.__dict__ if hasattr(modulo, "__dict__") else modulo
        await self.db.execute(
            text("""
                INSERT INTO modulos (id, curso_id, titulo, descripcion, orden, tipo_contenido, contenido_url, duracion_minutos)
                VALUES (:id, :curso_id, :titulo, :descripcion, :orden, CAST(:tipo_contenido AS tipo_contenido), :contenido_url, :duracion_minutos)
            """),
            params
        )
        return modulo

    async def update_modulo(self, modulo: Any = None) -> None:
        if modulo is not None:
            params = modulo.__dict__ if hasattr(modulo, "__dict__") else modulo
            await self.db.execute(
                text("""
                    UPDATE modulos
                    SET titulo = :titulo, descripcion = :descripcion, orden = :orden,
                        tipo_contenido = CAST(:tipo_contenido AS tipo_contenido), contenido_url = :contenido_url,
                        duracion_minutos = :duracion_minutos
                    WHERE id = :id
                """),
                params
            )

    async def delete_modulo(self, modulo: Any) -> None:
        modulo_id = modulo.id if hasattr(modulo, "id") else (modulo["id"] if isinstance(modulo, dict) else modulo)
        await self.db.execute(
            text("DELETE FROM modulos WHERE id = :id"),
            {"id": modulo_id}
        )


class PerfilRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_perfil_by_id(self, perfil_id: UUID) -> Optional[RowObject]:
        res = await self.db.execute(
            text("SELECT id, nombre, email, ubicacion, rol, idioma_preferido, avatar_url, creado_en, actualizado_en FROM perfiles WHERE id = :id"),
            {"id": perfil_id}
        )
        row = res.mappings().one_or_none()
        return RowObject(row) if row else None

    async def create_perfil(self, perfil: Any) -> Any:
        params = perfil.__dict__ if hasattr(perfil, "__dict__") else perfil
        await self.db.execute(
            text("""
                INSERT INTO perfiles (id, nombre, email, rol, ubicacion, idioma_preferido)
                VALUES (:id, :nombre, :email, :rol, :ubicacion, :idioma_preferido)
                ON CONFLICT (id) DO UPDATE SET
                    nombre = EXCLUDED.nombre,
                    email = EXCLUDED.email,
                    rol = EXCLUDED.rol,
                    ubicacion = EXCLUDED.ubicacion,
                    actualizado_en = NOW()
            """),
            {
                "id": params["id"],
                "nombre": params["nombre"],
                "email": params["email"],
                "rol": params["rol"],
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
            text("SELECT id, usuario_id, curso_id, progreso, descargado, modulo_actual_id, tema_ui, inscrito_en, completado_en, actualizado_en FROM inscripciones WHERE usuario_id = :usuario_id AND curso_id = :curso_id"),
            {"usuario_id": usuario_id, "curso_id": curso_id}
        )
        row = res.mappings().one_or_none()
        return RowObject(row) if row else None

    async def get_inscripciones_by_usuario(self, usuario_id: UUID) -> List[RowObject]:
        res = await self.db.execute(
            text("SELECT id, usuario_id, curso_id, progreso, descargado, modulo_actual_id, tema_ui, inscrito_en, completado_en, actualizado_en FROM inscripciones WHERE usuario_id = :usuario_id"),
            {"usuario_id": usuario_id}
        )
        return [RowObject(r) for r in res.mappings().all()]

    async def get_inscripciones_with_curso(self, usuario_id: UUID) -> List[RowObject]:
        res = await self.db.execute(
            text("""
                SELECT 
                    i.id as insc_id, i.usuario_id, i.curso_id, i.progreso, i.descargado, i.modulo_actual_id, i.tema_ui, i.inscrito_en, i.completado_en, i.actualizado_en,
                    c.titulo as curso_titulo, c.descripcion as curso_descripcion, c.categoria as curso_categoria,
                    c.duracion as curso_duracion, c.modulos as curso_modulos, c.nivel as curso_nivel,
                    c.instructor as curso_instructor, c.imagen as curso_imagen, c.color as curso_color, c.disponible as curso_disponible
                FROM inscripciones i
                JOIN cursos c ON i.curso_id = c.id
                WHERE i.usuario_id = :usuario_id
            """),
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
            text("SELECT id, inscripcion_id, modulo_id, completado, puntaje_evaluacion, completado_en FROM progreso_lecciones WHERE inscripcion_id = :inscripcion_id"),
            {"inscripcion_id": inscripcion_id}
        )
        return [RowObject(r) for r in res.mappings().all()]

    async def get_progreso_modulo(self, inscripcion_id: UUID, modulo_id: UUID) -> Optional[RowObject]:
        res = await self.db.execute(
            text("SELECT id, inscripcion_id, modulo_id, completado, puntaje_evaluacion, completado_en FROM progreso_lecciones WHERE inscripcion_id = :inscripcion_id AND modulo_id = :modulo_id"),
            {"inscripcion_id": inscripcion_id, "modulo_id": modulo_id}
        )
        row = res.mappings().one_or_none()
        return RowObject(row) if row else None

    async def get_all_progreso_lecciones_by_usuario(self, usuario_id: UUID) -> List[RowObject]:
        res = await self.db.execute(
            text("""
                SELECT pl.id, pl.inscripcion_id, pl.modulo_id, pl.completado, pl.puntaje_evaluacion, pl.completado_en, i.curso_id
                FROM progreso_lecciones pl
                JOIN inscripciones i ON pl.inscripcion_id = i.id
                WHERE i.usuario_id = :usuario_id
            """),
            {"usuario_id": usuario_id}
        )
        return [RowObject(r) for r in res.mappings().all()]

    async def save_inscripcion(self, inscripcion: Any) -> Any:
        params = inscripcion.__dict__ if hasattr(inscripcion, "__dict__") else inscripcion
        res = await self.db.execute(
            text("""
                INSERT INTO inscripciones (id, usuario_id, curso_id, progreso, descargado, modulo_actual_id, tema_ui, completado_en)
                VALUES (:id, :usuario_id, :curso_id, :progreso, :descargado, :modulo_actual_id, :tema_ui, :completado_en)
                ON CONFLICT (usuario_id, curso_id) DO UPDATE SET
                    progreso = EXCLUDED.progreso,
                    descargado = EXCLUDED.descargado,
                    modulo_actual_id = EXCLUDED.modulo_actual_id,
                    tema_ui = EXCLUDED.tema_ui,
                    completado_en = EXCLUDED.completado_en,
                    actualizado_en = NOW()
                RETURNING inscrito_en, actualizado_en
            """),
            params
        )
        row = res.mappings().one()
        if hasattr(inscripcion, "__dict__"):
            inscripcion.inscrito_en = row["inscrito_en"]
            inscripcion.actualizado_en = row["actualizado_en"]
        else:
            inscripcion["inscrito_en"] = row["inscrito_en"]
            inscripcion["actualizado_en"] = row["actualizado_en"]
        return inscripcion

    async def save_progreso_leccion(self, progreso: Any) -> Any:
        params = progreso.__dict__ if hasattr(progreso, "__dict__") else progreso
        await self.db.execute(
            text("""
                INSERT INTO progreso_lecciones (id, inscripcion_id, modulo_id, completado, puntaje_evaluacion, completado_en)
                VALUES (:id, :inscripcion_id, :modulo_id, :completado, :puntaje_evaluacion, :completado_en)
                ON CONFLICT (inscripcion_id, modulo_id) DO UPDATE SET
                    completado = EXCLUDED.completado,
                    puntaje_evaluacion = EXCLUDED.puntaje_evaluacion,
                    completado_en = EXCLUDED.completado_en,
                    actualizado_en = NOW()
            """),
            params
        )
        return progreso

    async def delete_inscripcion(self, inscripcion: Any) -> None:
        insc_id = inscripcion.id if hasattr(inscripcion, "id") else (inscripcion["id"] if isinstance(inscripcion, dict) else inscripcion)
        await self.db.execute(
            text("DELETE FROM inscripciones WHERE id = :id"),
            {"id": insc_id}
        )


class CertificadoRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_certificados_by_usuario(self, usuario_id: UUID) -> List[RowObject]:
        res = await self.db.execute(
            text("SELECT id, usuario_id, curso_id, codigo_certificado, url_certificado, emitido_en FROM certificados WHERE usuario_id = :usuario_id"),
            {"usuario_id": usuario_id}
        )
        return [RowObject(r) for r in res.mappings().all()]

    async def get_certificado(self, usuario_id: UUID, curso_id: str) -> Optional[RowObject]:
        res = await self.db.execute(
            text("SELECT id, usuario_id, curso_id, codigo_certificado, url_certificado, emitido_en FROM certificados WHERE usuario_id = :usuario_id AND curso_id = :curso_id"),
            {"usuario_id": usuario_id, "curso_id": curso_id}
        )
        row = res.mappings().one_or_none()
        return RowObject(row) if row else None

    async def save_certificado(self, certificado: Any) -> Any:
        params = certificado.__dict__ if hasattr(certificado, "__dict__") else certificado
        await self.db.execute(
            text("""
                INSERT INTO certificados (id, usuario_id, curso_id, codigo_certificado, url_certificado)
                VALUES (:id, :usuario_id, :curso_id, :codigo_certificado, :url_certificado)
                ON CONFLICT (usuario_id, curso_id) DO NOTHING
            """),
            params
        )
        return certificado


class NotificacionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_notificaciones_by_usuario(self, usuario_id: UUID) -> List[RowObject]:
        res = await self.db.execute(
            text("SELECT id, usuario_id, tipo, titulo, mensaje, leido, ruta_accion, creado_en FROM notificaciones WHERE usuario_id = :usuario_id ORDER BY creado_en DESC"),
            {"usuario_id": usuario_id}
        )
        return [RowObject(r) for r in res.mappings().all()]

    async def get_notificacion_by_id(self, notif_id: UUID) -> Optional[RowObject]:
        res = await self.db.execute(
            text("SELECT id, usuario_id, tipo, titulo, mensaje, leido, ruta_accion, creado_en FROM notificaciones WHERE id = :id"),
            {"id": notif_id}
        )
        row = res.mappings().one_or_none()
        return RowObject(row) if row else None

    async def save_notificacion(self, notif: Any) -> Any:
        params = notif.__dict__ if hasattr(notif, "__dict__") else notif
        await self.db.execute(
            text("""
                INSERT INTO notificaciones (id, usuario_id, tipo, titulo, mensaje, leido, ruta_accion)
                VALUES (:id, :usuario_id, :tipo, :titulo, :mensaje, :leido, :ruta_accion)
                ON CONFLICT (id) DO UPDATE SET
                    leido = EXCLUDED.leido
            """),
            params
        )
        return notif

    async def delete_notificacion(self, notif: Any) -> None:
        notif_id = notif.id if hasattr(notif, "id") else (notif["id"] if isinstance(notif, dict) else notif)
        await self.db.execute(
            text("DELETE FROM notificaciones WHERE id = :id"),
            {"id": notif_id}
        )

    async def notify_all_users_new_course(self, curso_id: str, curso_titulo: str) -> None:
        mensaje = f"Se ha publicado un nuevo curso: '{curso_titulo}'. ¡Inscríbete ahora!"
        ruta_accion = f"/courses/{curso_id}"
        await self.db.execute(
            text("""
                INSERT INTO notificaciones (id, usuario_id, tipo, titulo, mensaje, leido, ruta_accion)
                SELECT gen_random_uuid(), id, 'new_course'::notificacion_tipo, 'Nuevo Curso Disponible', :mensaje, FALSE, :ruta_accion
                FROM perfiles
            """),
            {"mensaje": mensaje, "ruta_accion": ruta_accion}
        )

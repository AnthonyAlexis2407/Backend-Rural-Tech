from sqlalchemy.ext.asyncio import AsyncSession
from ..repositories.repositories import CursoRepository, PerfilRepository, InscripcionRepository, CertificadoRepository, NotificacionRepository, RowObject
from uuid import UUID
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

class CursoService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.curso_repo = CursoRepository(db)
        self.insc_repo = InscripcionRepository(db)
        self.cert_repo = CertificadoRepository(db)
        self.notif_repo = NotificacionRepository(db)

    async def obtener_cursos(self, disponible_only: bool = True) -> List[RowObject]:
        return await self.curso_repo.get_all_cursos(disponible_only)

    async def obtener_curso_por_id(self, curso_id: str) -> Optional[RowObject]:
        return await self.curso_repo.get_curso_by_id(curso_id)

    async def inscribir_usuario(self, usuario_id: UUID, curso_id: str, tema_ui: str = "grey") -> RowObject:
        # Verificar si el curso existe
        curso = await self.curso_repo.get_curso_by_id(curso_id)
        if not curso:
            raise ValueError("Curso no encontrado")

        # Verificar si ya está inscrito
        existing = await self.insc_repo.get_inscripcion(usuario_id, curso_id)
        if existing:
            return existing

        # Crear nueva inscripción
        inscripcion = RowObject({
            "id": uuid.uuid4(),
            "usuario_id": usuario_id,
            "curso_id": curso_id,
            "progreso": 0,
            "descargado": False,
            "modulo_actual_id": None,
            "tema_ui": tema_ui,
            "completado_en": None
        })
        await self.insc_repo.save_inscripcion(inscripcion)

        # Crear notificación de bienvenida al curso
        notif = RowObject({
            "id": uuid.uuid4(),
            "usuario_id": usuario_id,
            "tipo": "new_course",
            "titulo": "Inscripción Exitosa",
            "mensaje": f"Te has inscrito correctamente en el curso {curso.titulo}.",
            "ruta_accion": f"/courses/{curso_id}",
            "leido": False
        })
        await self.notif_repo.save_notificacion(notif)

        return inscripcion

    async def desinscribir_usuario(self, usuario_id: UUID, curso_id: str) -> bool:
        """Elimina la inscripción de un usuario en un curso"""
        inscripcion = await self.insc_repo.get_inscripcion(usuario_id, curso_id)
        if not inscripcion:
            return False
        await self.insc_repo.delete_inscripcion(inscripcion)
        return True

    async def registrar_progreso_modulo(
        self, 
        usuario_id: UUID, 
        curso_id: str, 
        modulo_id: UUID, 
        completado: bool,
        score: Optional[int] = None
    ) -> Dict[str, Any]:
        # 1. Buscar la inscripción
        inscripcion = await self.insc_repo.get_inscripcion(usuario_id, curso_id)
        if not inscripcion:
            # Inscribir automáticamente si no lo está
            inscripcion = await self.inscribir_usuario(usuario_id, curso_id)

        # 2. Registrar el progreso de la lección
        progreso = await self.insc_repo.get_progreso_modulo(inscripcion.id, modulo_id)
        module_just_completed = False
        if not progreso:
            if completado:
                module_just_completed = True
            progreso = RowObject({
                "id": uuid.uuid4(),
                "inscripcion_id": inscripcion.id,
                "modulo_id": modulo_id,
                "completado": completado,
                "puntaje_evaluacion": score,
                "completado_en": datetime.now(timezone.utc) if completado else None
            })
            await self.insc_repo.save_progreso_leccion(progreso)
        else:
            if completado and not progreso.completado:
                module_just_completed = True
            progreso.completado = completado
            if score is not None:
                progreso.puntaje_evaluacion = score
            if completado and not progreso.completado_en:
                progreso.completado_en = datetime.now(timezone.utc)
            await self.insc_repo.save_progreso_leccion(progreso)

        if module_just_completed:
            # Obtener detalles de curso y módulo para el mensaje
            curso = await self.curso_repo.get_curso_by_id(curso_id)
            curso_titulo = curso.titulo if curso else curso_id
            
            modulo_obj = await self.curso_repo.get_modulo_by_id(modulo_id)
            modulo_titulo = modulo_obj.titulo if modulo_obj else "módulo"
            
            notif_mod = RowObject({
                "id": uuid.uuid4(),
                "usuario_id": usuario_id,
                "tipo": "lesson_complete",
                "titulo": "Módulo Completado",
                "mensaje": f"¡Buen trabajo! Completaste el módulo '{modulo_titulo}' del curso '{curso_titulo}'.",
                "ruta_accion": f"/courses/{curso_id}",
                "leido": False
            })
            await self.notif_repo.save_notificacion(notif_mod)

        # 3. Recalcular el progreso general de la inscripción
        modulos = await self.curso_repo.get_modulos_by_curso(curso_id)
        total_modulos = len(modulos)
        
        # Obtener lecciones completadas
        detalles = await self.insc_repo.get_progreso_lecciones(inscripcion.id)
        completados = sum(1 for d in detalles if d.completado)

        if total_modulos > 0:
            inscripcion.progreso = int((completados / total_modulos) * 100)
            
        inscripcion.modulo_actual_id = modulo_id

        # 4. Verificar si completó el curso al 100% para emitir certificado
        certificado_emitido = False
        if inscripcion.progreso == 100 and not inscripcion.completado_en:
            inscripcion.completado_en = datetime.now(timezone.utc)
            
            # Emitir Certificado si no existe
            cert_existing = await self.cert_repo.get_certificado(usuario_id, curso_id)
            if not cert_existing:
                cert_code = f"RT-CERT-{int(datetime.now(timezone.utc).timestamp())}"
                certificado = RowObject({
                    "id": uuid.uuid4(),
                    "usuario_id": usuario_id,
                    "curso_id": curso_id,
                    "codigo_certificado": cert_code,
                    "url_certificado": f"/api/certificados/descargar/{cert_code}"
                })
                await self.cert_repo.save_certificado(certificado)
                certificado_emitido = True

                # Crear notificación del certificado obtenido
                notif_cert = RowObject({
                    "id": uuid.uuid4(),
                    "usuario_id": usuario_id,
                    "tipo": "course_complete",
                    "titulo": "¡Felicitaciones! Curso Completado",
                    "mensaje": f"Has completado {curso_id.upper()}. Tu certificado ya está disponible.",
                    "ruta_accion": "/certificates",
                    "leido": False
                })
                await self.notif_repo.save_notificacion(notif_cert)

        # Guardar cambios en la inscripción
        await self.insc_repo.save_inscripcion(inscripcion)

        # 5. Evaluar logros en la base de datos
        from ..repositories.repositories import LogroRepository
        logro_repo = LogroRepository(self.db)
        
        # Obtener todas las inscripciones del usuario para evaluar
        todas_inscripciones = await self.insc_repo.get_inscripciones_by_usuario(usuario_id)
        
        completed_courses = [i for i in todas_inscripciones if i.progreso >= 100]
        completed_count = len(completed_courses)
        
        total_prog = sum(i.progreso for i in todas_inscripciones)
        avg_progress = total_prog / len(todas_inscripciones) if todas_inscripciones else 0
        
        # Logro: Primer curso completado
        if completed_count >= 1:
            await logro_repo.unlock_logro(usuario_id, "first_course")
        
        # Logro: Progreso general > 50%
        if avg_progress > 50:
            await logro_repo.unlock_logro(usuario_id, "half_progress")

        return {
            "progreso_curso": inscripcion.progreso,
            "modulo_completado": completado,
            "certificado_emitido": certificado_emitido
        }

    async def crear_curso(self, data: Any) -> RowObject:
        nivel = data.nivel
        if isinstance(nivel, str) and nivel.startswith("courses."):
            nivel = nivel.replace("courses.", "")
            
        modulos = data.modulos
        if isinstance(modulos, int) and modulos < 1:
            modulos = 1

        curso = RowObject({
            "id": data.id,
            "titulo": data.titulo,
            "descripcion": data.descripcion,
            "categoria": data.categoria,
            "duracion": data.duracion,
            "modulos": modulos,
            "nivel": nivel,
            "instructor": data.instructor,
            "imagen": data.imagen,
            "color": data.color,
            "disponible": data.disponible
        })
        await self.curso_repo.create_curso(curso)
        new_curso = await self.curso_repo.get_curso_by_id(data.id)
        
        # Enviar notificación de nuevo curso a todos los usuarios si está disponible
        if data.disponible and new_curso:
            try:
                await self.notif_repo.notify_all_users_new_course(new_curso.id, new_curso.titulo)
            except Exception as e:
                print(f"Error al notificar nuevo curso: {e}")
                
        return new_curso if new_curso else curso

    async def actualizar_curso(self, curso_id: str, data: Any) -> Optional[RowObject]:
        curso = await self.curso_repo.get_curso_by_id(curso_id)
        if not curso:
            return None
        
        was_available = curso.disponible if hasattr(curso, "disponible") else False
        
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "nivel" and isinstance(value, str) and value.startswith("courses."):
                value = value.replace("courses.", "")
            elif field == "modulos" and isinstance(value, int) and value < 1:
                value = 1
            setattr(curso, field, value)
            
        await self.curso_repo.update_curso(curso)
        updated_curso = await self.curso_repo.get_curso_by_id(curso_id)
        
        # Si pasó a estar disponible, notificar a los usuarios
        if updated_curso and updated_curso.disponible and not was_available:
            try:
                await self.notif_repo.notify_all_users_new_course(updated_curso.id, updated_curso.titulo)
            except Exception as e:
                print(f"Error al notificar nuevo curso por actualización: {e}")
                
        return updated_curso if updated_curso else curso

    async def eliminar_curso(self, curso_id: str) -> bool:
        curso = await self.curso_repo.get_curso_by_id(curso_id)
        if not curso:
            return False
        await self.curso_repo.delete_curso(curso)
        return True

    async def crear_modulo(self, curso_id: str, data: Any) -> RowObject:
        modulo = RowObject({
            "id": uuid.uuid4(),
            "curso_id": curso_id,
            "titulo": data.titulo,
            "descripcion": data.descripcion if hasattr(data, 'descripcion') else None,
            "orden": data.orden,
            "tipo_contenido": data.tipo_contenido,
            "contenido_url": data.contenido_url,
            "duracion_minutos": data.duracion_minutos
        })
        return await self.curso_repo.create_modulo(modulo)

    async def actualizar_modulo(self, modulo_id: UUID, data: Any) -> Optional[RowObject]:
        modulo = await self.curso_repo.get_modulo_by_id(modulo_id)
        if not modulo:
            return None
            
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(modulo, field, value)
            
        await self.curso_repo.update_modulo(modulo)
        return modulo

    async def eliminar_modulo(self, modulo_id: UUID) -> bool:
        modulo = await self.curso_repo.get_modulo_by_id(modulo_id)
        if not modulo:
            return False
        await self.curso_repo.delete_modulo(modulo)
        return True


class SyncService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.curso_service = CursoService(db)
        self.notif_repo = NotificacionRepository(db)

    async def procesar_cola_sincronizacion(
        self, 
        usuario_id: UUID, 
        acciones: List[Dict[str, Any]],
        nodo_id: Optional[str] = None,
        almacenamiento_usado_gb: Optional[float] = 0.00,
        almacenamiento_max_gb: Optional[float] = 5.00,
        version_app: Optional[str] = None
    ) -> Dict[str, Any]:
        from ..repositories.repositories import NodoRepository, ColaSincronizacionRepository

        # 1. Upsertar información del nodo si está disponible
        if nodo_id:
            nodo_repo = NodoRepository(self.db)
            await nodo_repo.upsert_nodo(
                nodo_id=nodo_id,
                usuario_id=usuario_id,
                almacenamiento_usado_gb=almacenamiento_usado_gb or 0.00,
                almacenamiento_max_gb=almacenamiento_max_gb or 5.00,
                version_app=version_app or "1.0.0"
            )

        procesados = 0
        fallidos = 0
        detalles = []
        cola_repo = ColaSincronizacionRepository(self.db)

        for item in acciones:
            accion_tipo = item.get("accion")
            payload = item.get("payload", {})
            
            try:
                if accion_tipo == "COMPLETE_LESSON":
                    curso_id = payload.get("courseId")
                    modulo_id_str = payload.get("moduleId")
                    
                    if not curso_id or not modulo_id_str:
                        raise ValueError("courseId o moduleId faltante en payload")
                    
                    modulo_uuid = UUID(modulo_id_str)
                    
                    res = await self.curso_service.registrar_progreso_modulo(
                        usuario_id=usuario_id,
                        curso_id=curso_id,
                        modulo_id=modulo_uuid,
                        completado=True
                    )
                    procesados += 1
                    detalles.append({"accion": accion_tipo, "estado": "success", "info": res})
                    
                    # Guardar log en cola_sincronizacion
                    await cola_repo.save_sync_log(
                        usuario_id=usuario_id,
                        nodo_id=nodo_id,
                        accion=accion_tipo,
                        payload=payload,
                        estado="completed"
                    )
                    
                elif accion_tipo == "SUBMIT_ASSESSMENT":
                    curso_id = payload.get("courseId")
                    modulo_id_str = payload.get("moduleId")
                    score = payload.get("score")
                    
                    if not curso_id or not modulo_id_str or score is None:
                        raise ValueError("Parámetros faltantes en payload para evaluación")
                    
                    modulo_uuid = UUID(modulo_id_str)
                    
                    res = await self.curso_service.registrar_progreso_modulo(
                        usuario_id=usuario_id,
                        curso_id=curso_id,
                        modulo_id=modulo_uuid,
                        completado=True,
                        score=int(score)
                    )
                    procesados += 1
                    detalles.append({"accion": accion_tipo, "estado": "success", "info": res})
                    
                    # Guardar log en cola_sincronizacion
                    await cola_repo.save_sync_log(
                        usuario_id=usuario_id,
                        nodo_id=nodo_id,
                        accion=accion_tipo,
                        payload=payload,
                        estado="completed"
                    )
                elif accion_tipo == "ENROLL_COURSE":
                    curso_id = payload.get("courseId")
                    tema_ui = payload.get("theme") or "grey"
                    if not curso_id:
                        raise ValueError("courseId faltante en payload para inscripción")
                    
                    res = await self.curso_service.inscribir_usuario(
                        usuario_id=usuario_id,
                        curso_id=curso_id,
                        tema_ui=tema_ui
                    )
                    procesados += 1
                    detalles.append({"accion": accion_tipo, "estado": "success", "info": res})
                    
                    # Guardar log en cola_sincronizacion
                    await cola_repo.save_sync_log(
                        usuario_id=usuario_id,
                        nodo_id=nodo_id,
                        accion=accion_tipo,
                        payload=payload,
                        estado="completed"
                    )
                else:
                    raise ValueError(f"Acción '{accion_tipo}' no reconocida")
            except Exception as e:
                fallidos += 1
                detalles.append({"accion": accion_tipo, "estado": "failed", "error": str(e)})
                
                # Guardar log en cola_sincronizacion
                await cola_repo.save_sync_log(
                    usuario_id=usuario_id,
                    nodo_id=nodo_id,
                    accion=accion_tipo,
                    payload=payload,
                    estado="failed",
                    error_msg=str(e)
                )

        # Si procesó acciones exitosamente, emitimos notificación de sincronización
        if procesados > 0:
            notif = RowObject({
                "id": uuid.uuid4(),
                "usuario_id": usuario_id,
                "tipo": "sync_done",
                "titulo": "Sincronización Completada",
                "mensaje": f"Se han sincronizado {procesados} avances de lecciones con el servidor.",
                "ruta_accion": "/sync-status",
                "leido": False
            })
            await self.notif_repo.save_notificacion(notif)

        return {
            "procesados": procesados,
            "fallidos": fallidos,
            "detalles": detalles
        }

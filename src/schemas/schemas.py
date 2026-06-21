from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

# ==========================================
# PERFILES
# ==========================================
class PerfilBase(BaseModel):
    nombre: str
    email: EmailStr
    ubicacion: Optional[str] = None
    rol: str = "estudiante"
    idioma_preferido: str = "es"
    avatar_url: Optional[str] = None

class PerfilCreate(PerfilBase):
    pass

class PerfilResponse(PerfilBase):
    id: UUID
    creado_en: datetime
    actualizado_en: datetime

    class Config:
        from_attributes = True

# ==========================================
# REGISTRO
# ==========================================
class UsuarioRegister(BaseModel):
    nombre: str
    email: EmailStr
    location: Optional[str] = None
    rol: str = "estudiante"
    password: str

class AdminRegister(BaseModel):
    nombre: str
    email: EmailStr
    location: Optional[str] = None
    password: str
    secreto: str

class CursoCreate(BaseModel):
    id: str
    titulo: str
    descripcion: str
    categoria: str
    duracion: str
    modulos: int
    nivel: str
    instructor: str
    imagen: str
    color: str
    disponible: bool = True

class CursoUpdate(BaseModel):
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    categoria: Optional[str] = None
    duracion: Optional[str] = None
    modulos: Optional[int] = None
    nivel: Optional[str] = None
    instructor: Optional[str] = None
    imagen: Optional[str] = None
    color: Optional[str] = None
    disponible: Optional[bool] = None

class ModuloCreate(BaseModel):
    titulo: str
    descripcion: Optional[str] = None
    orden: int
    tipo_contenido: str
    contenido_url: Optional[str] = None
    duracion_minutos: Optional[int] = None

class ModuloUpdate(BaseModel):
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    orden: Optional[int] = None
    tipo_contenido: Optional[str] = None
    contenido_url: Optional[str] = None
    duracion_minutos: Optional[int] = None



# ==========================================
# CURSOS Y MÓDULOS
# ==========================================
class ModuloResponse(BaseModel):
    id: UUID
    curso_id: str
    titulo: str
    descripcion: Optional[str] = None
    orden: int
    tipo_contenido: str
    contenido_url: Optional[str] = None
    duracion_minutos: Optional[int] = None

    class Config:
        from_attributes = True

class CursoBase(BaseModel):
    id: str
    titulo: str
    descripcion: str
    categoria: str
    duracion: str
    modulos: int
    nivel: str
    instructor: str
    imagen: str
    color: str
    disponible: bool = True

class CursoResponse(CursoBase):
    creado_en: datetime
    actualizado_en: datetime

    class Config:
        from_attributes = True

class CursoDetailResponse(CursoResponse):
    modulo_list: List[ModuloResponse] = []

    class Config:
        from_attributes = True

# ==========================================
# INSCRIPCIONES Y PROGRESO
# ==========================================
class InscripcionCreate(BaseModel):
    curso_id: str
    tema_ui: Optional[str] = "grey"

class ProgresoLeccionUpdate(BaseModel):
    modulo_id: UUID
    completado: bool
    puntaje_evaluacion: Optional[int] = None

class InscripcionResponse(BaseModel):
    id: UUID
    usuario_id: UUID
    curso_id: str
    progreso: int
    descargado: bool
    modulo_actual_id: Optional[UUID] = None
    tema_ui: str
    inscrito_en: datetime
    completado_en: Optional[datetime] = None
    actualizado_en: datetime

    class Config:
        from_attributes = True

class CursoMiniResponse(BaseModel):
    """Respuesta reducida del curso para acompañar inscripciones"""
    id: str
    titulo: str
    descripcion: str
    categoria: str
    duracion: str
    modulos: int
    nivel: str
    instructor: str
    imagen: str
    color: str
    disponible: bool = True

    class Config:
        from_attributes = True

class InscripcionDetailResponse(BaseModel):
    """Inscripción con los datos del curso incluidos"""
    id: UUID
    usuario_id: UUID
    curso_id: str
    progreso: int
    descargado: bool
    modulo_actual_id: Optional[UUID] = None
    tema_ui: str
    inscrito_en: datetime
    completado_en: Optional[datetime] = None
    actualizado_en: datetime
    curso: Optional[CursoMiniResponse] = None

    class Config:
        from_attributes = True

# ==========================================
# CERTIFICADOS
# ==========================================
class CertificadoResponse(BaseModel):
    id: UUID
    usuario_id: UUID
    curso_id: str
    codigo_certificado: str
    url_certificado: Optional[str] = None
    emitido_en: datetime

    class Config:
        from_attributes = True

# ==========================================
# NOTIFICACIONES
# ==========================================
class NotificacionResponse(BaseModel):
    id: UUID
    usuario_id: UUID
    tipo: str
    titulo: str
    mensaje: str
    leido: bool
    ruta_accion: Optional[str] = None
    creado_en: datetime

    class Config:
        from_attributes = True

# ==========================================
# SINCRONIZACIÓN OFFLINE
# ==========================================
class AccionSyncItem(BaseModel):
    accion: str  # COMPLETE_LESSON, SUBMIT_ASSESSMENT
    payload: Dict[str, Any]

class SincronizacionRequest(BaseModel):
    nodo_id: Optional[str] = None
    almacenamiento_usado_gb: Optional[float] = 0.00
    almacenamiento_max_gb: Optional[float] = 5.00
    version_app: Optional[str] = None
    acciones: List[AccionSyncItem]

class SyncResult(BaseModel):
    procesados: int
    fallidos: int
    detalles: List[Dict[str, Any]]

# ==========================================
# ARCHIVOS DESCARGADOS
# ==========================================
class ArchivoDescargadoCreate(BaseModel):
    curso_id: str
    nombre_archivo: str
    tamano: str
    tipo: str
    url_local: Optional[str] = None

class ArchivoDescargadoResponse(BaseModel):
    id: UUID
    usuario_id: UUID
    curso_id: str
    nombre_archivo: str
    tamano: str
    tipo: str
    url_local: Optional[str] = None
    descargado_en: datetime
    eliminado_en: Optional[datetime] = None

    class Config:
        from_attributes = True

# ==========================================
# PREGUNTAS FRECUENTES (FAQs)
# ==========================================
class PreguntaFrecuenteResponse(BaseModel):
    id: int
    clave_pregunta: str
    clave_respuesta: str
    orden: int

    class Config:
        from_attributes = True

# ==========================================
# LOGROS
# ==========================================
class LogroResponse(BaseModel):
    id: str
    titulo_clave: str
    descripcion_clave: str
    icono: str
    desbloqueado_en: Optional[datetime] = None

    class Config:
        from_attributes = True


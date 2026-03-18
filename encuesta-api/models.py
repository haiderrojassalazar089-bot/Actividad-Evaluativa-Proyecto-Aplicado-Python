"""
models.py
---------
Modelos Pydantic V2 para la API de Encuestas Poblacionales.

Jerarquía de modelos:
    Encuestado
        └── campo en EncuestaCompleta
    RespuestaEncuesta
        └── List[RespuestaEncuesta] en EncuestaCompleta
    EncuestaCompleta  ← modelo contenedor (anidado)

Los validadores de campo operan como "aduana transaccional":
ningún dato estadísticamente incoherente atraviesa hacia el
repositorio de análisis.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator
from typing_extensions import Annotated

from validators import (
    DEPARTAMENTOS_COLOMBIA,
    ESTRATO_MAX,
    ESTRATO_MIN,
    TIPOS_PREGUNTA_VALIDOS,
    es_departamento_valido,
    es_porcentaje_valido,
    es_puntaje_likert_valido,
    normalizar_texto,
)


# ══════════════════════════════════════════════════════════════
# MODELO 1 — Encuestado
# ══════════════════════════════════════════════════════════════
class Encuestado(BaseModel):
    """
    Representa los datos demográficos de una persona encuestada.

    Equivalente estadístico: unidad de observación (fila) de la
    matriz de diseño con sus covariables sociodemográficas.
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "nombre": "María Fernanda López",
                    "edad": 34,
                    "estrato": 3,
                    "departamento": "Cundinamarca",
                    "genero": "femenino",
                    "nivel_educativo": "universitario",
                    "email": "mflopez@ejemplo.co",
                }
            ]
        }
    }

    nombre: Annotated[str, Field(min_length=2, max_length=120,
                                  description="Nombre completo del encuestado")]

    edad: Annotated[int, Field(ge=0, le=120,
                                description="Edad en años (restricción biológica: 0–120)")]

    estrato: Annotated[int, Field(ge=ESTRATO_MIN, le=ESTRATO_MAX,
                                   description="Estrato socioeconómico colombiano (1–6)")]

    departamento: Annotated[str, Field(description="Departamento de residencia en Colombia")]

    genero: Optional[str] = Field(
        default=None,
        description="Género auto-reportado (opcional)"
    )

    nivel_educativo: Optional[str] = Field(
        default=None,
        description="Nivel educativo más alto alcanzado"
    )

    email: Optional[str] = Field(
        default=None,
        description="Correo electrónico (opcional)"
    )

    # ── Validadores ──────────────────────────────────────────

    @field_validator("nombre", mode="before")
    @classmethod
    def limpiar_nombre(cls, valor: str) -> str:
        """
        mode='before': opera sobre el dato crudo antes de la coerción.
        Elimina espacios redundantes y normaliza capitalización.
        Equivale a una limpieza de entrada en el libro de códigos.
        """
        if not isinstance(valor, str):
            raise ValueError("El nombre debe ser una cadena de texto.")
        limpio = " ".join(valor.split())          # colapsa espacios múltiples
        if not re.match(r"^[a-záéíóúüñA-ZÁÉÍÓÚÜÑ\s\-']+$", limpio):
            raise ValueError(
                f"El nombre '{limpio}' contiene caracteres no permitidos. "
                "Solo se admiten letras, espacios, guiones y apóstrofes."
            )
        return limpio.title()

    @field_validator("departamento", mode="before")
    @classmethod
    def normalizar_departamento(cls, valor: str) -> str:
        """
        mode='before': normaliza el texto crudo antes de validar.
        Permite ingreso en cualquier capitalización.
        """
        if not isinstance(valor, str):
            raise ValueError("El departamento debe ser texto.")
        return valor.strip().title()

    @field_validator("departamento", mode="after")
    @classmethod
    def validar_departamento(cls, valor: str) -> str:
        """
        mode='after': valida contra el listado oficial ya con tipo seguro.
        Opera sobre el dato ya normalizado por el validador 'before'.
        """
        if not es_departamento_valido(valor):
            sugerencias = sorted(
                d.title() for d in list(DEPARTAMENTOS_COLOMBIA)[:5]
            )
            raise ValueError(
                f"'{valor}' no es un departamento válido de Colombia. "
                f"Ejemplos válidos: {sugerencias}. "
                "Verifique la lista completa de 32 departamentos."
            )
        return valor

    @field_validator("email", mode="after")
    @classmethod
    def validar_email(cls, valor: Optional[str]) -> Optional[str]:
        """Valida formato básico de correo electrónico si se proporciona."""
        if valor is None:
            return valor
        patron = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
        if not re.match(patron, valor):
            raise ValueError(
                f"'{valor}' no tiene formato de correo electrónico válido."
            )
        return valor.lower()

    @field_validator("genero", mode="before")
    @classmethod
    def normalizar_genero(cls, valor: Optional[str]) -> Optional[str]:
        """Normaliza a minúsculas si se proporciona."""
        if valor is None:
            return valor
        return normalizar_texto(valor)

    @field_validator("nivel_educativo", mode="before")
    @classmethod
    def normalizar_nivel_educativo(cls, valor: Optional[str]) -> Optional[str]:
        """Normaliza a minúsculas si se proporciona."""
        if valor is None:
            return valor
        niveles_validos = {
            "primaria", "secundaria", "técnico", "tecnólogo",
            "universitario", "posgrado", "ninguno"
        }
        normalizado = normalizar_texto(valor)
        if normalizado not in niveles_validos:
            raise ValueError(
                f"Nivel educativo '{valor}' no reconocido. "
                f"Valores permitidos: {sorted(niveles_validos)}"
            )
        return normalizado


# ══════════════════════════════════════════════════════════════
# MODELO 2 — RespuestaEncuesta
# ══════════════════════════════════════════════════════════════
class RespuestaEncuesta(BaseModel):
    """
    Representa la respuesta a una pregunta individual de la encuesta.

    El campo `puntaje` admite polimorfismo de tipo (Union[int, float, str])
    según el tipo de pregunta:
        - 'likert'     → int en [1, 5]
        - 'porcentaje' → float en [0.0, 100.0]
        - 'abierta'    → str (texto libre)
        - 'binaria'    → int en {0, 1}
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id_pregunta": "P01",
                    "texto_pregunta": "¿Qué tan satisfecho está con el servicio?",
                    "tipo_pregunta": "likert",
                    "puntaje": 4,
                    "observacion": "Buen servicio en general",
                }
            ]
        }
    }

    id_pregunta: Annotated[str, Field(min_length=1, max_length=20,
                                       description="Identificador único de la pregunta")]

    texto_pregunta: Annotated[str, Field(min_length=5, max_length=500,
                                          description="Enunciado completo de la pregunta")]

    tipo_pregunta: Annotated[str, Field(description="Tipo: likert | porcentaje | abierta | binaria")]

    # Union[int, float, str] → variable aleatoria con espacio muestral heterogéneo
    puntaje: Union[int, float, str] = Field(
        description="Valor de la respuesta según tipo_pregunta"
    )

    observacion: Optional[str] = Field(
        default=None,
        max_length=300,
        description="Comentario libre del encuestado (opcional)"
    )

    # ── Validadores ──────────────────────────────────────────

    @field_validator("tipo_pregunta", mode="before")
    @classmethod
    def validar_tipo_pregunta(cls, valor: str) -> str:
        """Normaliza y valida el tipo de pregunta contra catálogo."""
        normalizado = normalizar_texto(valor)
        if normalizado not in TIPOS_PREGUNTA_VALIDOS:
            raise ValueError(
                f"Tipo de pregunta '{valor}' no válido. "
                f"Tipos permitidos: {sorted(TIPOS_PREGUNTA_VALIDOS)}"
            )
        return normalizado

    @model_validator(mode="after")
    def validar_puntaje_segun_tipo(self) -> "RespuestaEncuesta":
        """
        Validador de modelo (cross-field): verifica la coherencia entre
        tipo_pregunta y puntaje. Equivale a un test de consistencia interna.
        """
        tipo = self.tipo_pregunta
        puntaje = self.puntaje

        if tipo == "likert":
            if not isinstance(puntaje, int):
                raise ValueError(
                    f"Pregunta Likert requiere entero, recibido: {type(puntaje).__name__}."
                )
            if not es_puntaje_likert_valido(puntaje):
                raise ValueError(
                    f"Puntaje Likert {puntaje} fuera del rango [1, 5]. "
                    "La escala Likert clásica comprende 5 niveles ordinales."
                )

        elif tipo == "porcentaje":
            if not isinstance(puntaje, (int, float)):
                raise ValueError(
                    f"Pregunta de porcentaje requiere número, recibido: {type(puntaje).__name__}."
                )
            if not es_porcentaje_valido(float(puntaje)):
                raise ValueError(
                    f"Porcentaje {puntaje} fuera del rango [0.0, 100.0]."
                )

        elif tipo == "binaria":
            if puntaje not in (0, 1):
                raise ValueError(
                    f"Pregunta binaria solo admite 0 o 1, recibido: {puntaje}."
                )

        elif tipo == "abierta":
            if not isinstance(puntaje, str):
                raise ValueError(
                    "Pregunta abierta requiere una respuesta de texto."
                )
            if len(puntaje.strip()) == 0:
                raise ValueError("La respuesta abierta no puede estar vacía.")

        return self


# ══════════════════════════════════════════════════════════════
# MODELO 3 — EncuestaCompleta (modelo contenedor anidado)
# ══════════════════════════════════════════════════════════════
class EncuestaCompleta(BaseModel):
    """
    Modelo contenedor que anida Encuestado + List[RespuestaEncuesta].

    Representa la unidad atómica de ingesta del pipeline estadístico:
    un registro completo que debe pasar todos los filtros de validación
    antes de ingresar al repositorio de análisis.
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "encuestado": {
                        "nombre": "Carlos Andrés Gómez",
                        "edad": 28,
                        "estrato": 2,
                        "departamento": "Antioquia",
                        "genero": "masculino",
                        "nivel_educativo": "universitario",
                        "email": "cgomez@ejemplo.co",
                    },
                    "respuestas": [
                        {
                            "id_pregunta": "P01",
                            "texto_pregunta": "¿Qué tan satisfecho está con el servicio?",
                            "tipo_pregunta": "likert",
                            "puntaje": 4,
                        },
                        {
                            "id_pregunta": "P02",
                            "texto_pregunta": "¿Cuál es su nivel de confianza en las instituciones?",
                            "tipo_pregunta": "porcentaje",
                            "puntaje": 65.5,
                        },
                    ],
                    "nombre_encuesta": "Encuesta de Satisfacción Ciudadana 2025",
                }
            ]
        }
    }

    id: UUID = Field(
        default_factory=uuid4,
        description="Identificador único generado automáticamente"
    )

    nombre_encuesta: Annotated[str, Field(
        min_length=3,
        max_length=200,
        description="Nombre descriptivo de la encuesta"
    )]

    # ── Modelos anidados ─────────────────────────────────────
    encuestado: Encuestado = Field(description="Datos demográficos del encuestado")

    respuestas: List[RespuestaEncuesta] = Field(
        min_length=1,
        description="Lista de respuestas individuales (mínimo 1)"
    )

    fecha_registro: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp UTC de ingesta al sistema"
    )

    activa: bool = Field(
        default=True,
        description="Indica si la encuesta está activa en el repositorio"
    )

    @field_validator("respuestas", mode="after")
    @classmethod
    def validar_ids_unicos(cls, respuestas: List[RespuestaEncuesta]) -> List[RespuestaEncuesta]:
        """
        Garantiza que no existan preguntas duplicadas dentro de una misma
        encuesta. Duplicados introducirían multicolinealidad artificial.
        """
        ids = [r.id_pregunta for r in respuestas]
        duplicados = {i for i in ids if ids.count(i) > 1}
        if duplicados:
            raise ValueError(
                f"IDs de pregunta duplicados detectados: {duplicados}. "
                "Cada pregunta debe tener un identificador único."
            )
        return respuestas


# ══════════════════════════════════════════════════════════════
# MODELOS DE RESPUESTA API
# ══════════════════════════════════════════════════════════════
class EstadisticasResponse(BaseModel):
    """Resumen estadístico del repositorio de encuestas."""
    total_encuestas: int
    promedio_edad: Optional[float]
    distribucion_estrato: dict[str, int]
    distribucion_departamento: dict[str, int]
    distribucion_genero: dict[str, int]
    tasa_completitud_email: float = Field(
        description="Porcentaje de encuestados que proporcionaron email"
    )


class ErrorDetalladoResponse(BaseModel):
    """Estructura estandarizada de respuesta de error HTTP 422."""
    status_code: int = 422
    mensaje: str = "Error de validación de datos"
    errores: list[dict]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MensajeResponse(BaseModel):
    """Respuesta genérica de operación exitosa."""
    mensaje: str
    id: Optional[str] = None
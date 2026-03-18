"""
main.py
-------
Punto de entrada de la API de Gestión de Encuestas Poblacionales.

Arquitectura:
    - FastAPI como framework ASGI
    - Pydantic V2 para validación de esquemas
    - Almacenamiento en memoria (dict) como repositorio simulado
    - Manejador personalizado de errores HTTP 422
    - Decoradores personalizados (@log_request, @timer)

──────────────────────────────────────────────────────────────
NOTA ASGI vs WSGI (RF5):
    WSGI (Web Server Gateway Interface) es una interfaz síncrona:
    cada petición bloquea un hilo hasta completarse. Frameworks
    como Flask y Django (clásico) usan WSGI.

    ASGI (Asynchronous Server Gateway Interface) es la evolución
    asíncrona: permite manejar múltiples conexiones concurrentes
    sin bloquear hilos del sistema operativo. FastAPI es un
    framework ASGI, por eso puede usar `async def` en sus endpoints.

    `async def` vs `def` en FastAPI:
        - `def` normal: FastAPI lo ejecuta en un thread pool para
          no bloquear el event loop. Adecuado para operaciones
          CPU-bound o librerías sincrónicas.
        - `async def`: se ejecuta directamente en el event loop.
          INDISPENSABLE cuando el endpoint realiza I/O asíncrono:
          consultas a bases de datos (asyncpg, motor), llamadas HTTP
          externas (httpx), lectura de archivos (aiofiles), etc.
          Sin async, el event loop quedaría bloqueado esperando I/O.
──────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import functools
import logging
import pickle
import time
from collections import Counter
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from models import (
    EncuestaCompleta,
    ErrorDetalladoResponse,
    EstadisticasResponse,
    MensajeResponse,
)

# ─────────────────────────────────────────────
# Configuración del logger
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("encuesta-api")

# ─────────────────────────────────────────────
# Instancia FastAPI
# ─────────────────────────────────────────────
app = FastAPI(
    title="API de Gestión de Encuestas Poblacionales",
    description=(
        "Sistema de recolección y validación de datos de encuestas "
        "demográficas con pipeline de ingesta estadísticamente riguroso. "
        "Construido con FastAPI + Pydantic V2."
    ),
    version="1.0.0",
    contact={"name": "USTA - Curso Python para APIs e IA"},
    license_info={"name": "MIT"},
)

# ─────────────────────────────────────────────
# Repositorio en memoria
# ─────────────────────────────────────────────
repositorio: Dict[str, EncuestaCompleta] = {}


# ══════════════════════════════════════════════════════════════
# DECORADORES PERSONALIZADOS (RT5)
# ══════════════════════════════════════════════════════════════
def log_request(func: Callable) -> Callable:
    """
    Decorador personalizado que registra en consola la fecha, verbo HTTP
    y ruta de cada petición procesada.

    Relación conceptual con decoradores de ruta FastAPI:
        @app.get('/ruta') es también un decorador; transforma una función
        Python ordinaria en un endpoint HTTP, registrándola en el router
        de FastAPI. De la misma forma, @log_request envuelve (wraps) la
        función para añadir comportamiento transversal sin modificar su
        lógica de negocio — principio de Separación de Responsabilidades.
    """
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Extraer el objeto Request de los kwargs de FastAPI
        request: Optional[Request] = kwargs.get("request")
        if request:
            logger.info(
                "📥 REQUEST | Método: %s | Ruta: %s | IP: %s",
                request.method,
                request.url.path,
                request.client.host if request.client else "desconocido",
            )
        resultado = await func(*args, **kwargs)
        if request:
            logger.info(
                "📤 RESPONSE | Método: %s | Ruta: %s | Completado",
                request.method,
                request.url.path,
            )
        return resultado
    return wrapper


def timer(func: Callable) -> Callable:
    """
    Decorador que mide y registra el tiempo de ejecución de un endpoint.
    Útil para detectar cuellos de botella en operaciones de validación masiva.
    """
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        inicio = time.perf_counter()
        resultado = await func(*args, **kwargs)
        duracion = time.perf_counter() - inicio
        logger.info("⏱️  TIMER | %s | %.4f segundos", func.__name__, duracion)
        return resultado
    return wrapper


# ══════════════════════════════════════════════════════════════
# MANEJADOR PERSONALIZADO DE ERRORES HTTP 422 (RF4)
# ══════════════════════════════════════════════════════════════
@app.exception_handler(RequestValidationError)
async def manejador_validacion(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Intercepta todas las excepciones RequestValidationError de FastAPI.
    Retorna respuestas JSON estructuradas con detalle de cada campo inválido.
    Registra en consola cada intento de ingesta con datos inválidos.
    """
    errores_detallados = []
    for error in exc.errors():
        campo = " → ".join(str(loc) for loc in error.get("loc", []))
        errores_detallados.append({
            "campo": campo,
            "mensaje": error.get("msg", "Error desconocido"),
            "tipo_error": error.get("type", ""),
            "valor_recibido": str(error.get("input", "N/A"))[:100],
        })

    # Log de auditoría: registra cada intento inválido
    logger.warning(
        "⚠️  VALIDACIÓN FALLIDA | Ruta: %s | Errores: %d | Campos: %s",
        request.url.path,
        len(errores_detallados),
        [e["campo"] for e in errores_detallados],
    )

    respuesta = ErrorDetalladoResponse(
        mensaje="Error de validación: los datos enviados no cumplen el esquema requerido.",
        errores=errores_detallados,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=respuesta.model_dump(mode="json"),
    )


# ══════════════════════════════════════════════════════════════
# ENDPOINTS (RF3)
# ══════════════════════════════════════════════════════════════

# ── POST /encuestas/ ─────────────────────────────────────────
@app.post(
    "/encuestas/",
    response_model=EncuestaCompleta,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nueva encuesta",
    description=(
        "Recibe una encuesta completa (encuestado + respuestas), la valida "
        "exhaustivamente mediante Pydantic V2 y la persiste en el repositorio. "
        "Retorna HTTP 422 con detalle de campos inválidos si la validación falla."
    ),
    tags=["Encuestas"],
)
@log_request
@timer
async def crear_encuesta(
    encuesta: EncuestaCompleta,
    request: Request,
) -> EncuestaCompleta:
    """
    Endpoint asíncrono (RF5):
        Se declara `async def` porque en un escenario real este endpoint
        realizaría I/O asíncrono: escritura en base de datos PostgreSQL
        (asyncpg), envío de evento a Kafka, o llamada a un microservicio
        externo via httpx. Sin `async`, el event loop de ASGI quedaría
        bloqueado durante toda la operación I/O, anulando la ventaja
        de concurrencia de FastAPI.
    """
    id_str = str(encuesta.id)
    repositorio[id_str] = encuesta
    logger.info("✅ INGESTA EXITOSA | ID: %s | Encuestado: %s", id_str, encuesta.encuestado.nombre)
    return encuesta


# ── GET /encuestas/ ──────────────────────────────────────────
@app.get(
    "/encuestas/",
    response_model=List[EncuestaCompleta],
    status_code=status.HTTP_200_OK,
    summary="Listar todas las encuestas",
    description="Retorna el listado completo de encuestas registradas en el repositorio.",
    tags=["Encuestas"],
)
@log_request
@timer
async def listar_encuestas(request: Request) -> List[EncuestaCompleta]:
    return list(repositorio.values())


# ── GET /encuestas/estadisticas/ ─────────────────────────────
@app.get(
    "/encuestas/estadisticas/",
    response_model=EstadisticasResponse,
    status_code=status.HTTP_200_OK,
    summary="Resumen estadístico del repositorio",
    description=(
        "Genera estadísticas descriptivas: conteo total, promedio de edad, "
        "distribución por estrato socioeconómico y por departamento."
    ),
    tags=["Estadísticas"],
)
@log_request
@timer
async def obtener_estadisticas(request: Request) -> EstadisticasResponse:
    if not repositorio:
        return EstadisticasResponse(
            total_encuestas=0,
            promedio_edad=None,
            distribucion_estrato={},
            distribucion_departamento={},
            distribucion_genero={},
            tasa_completitud_email=0.0,
        )

    encuestas = list(repositorio.values())
    edades = [e.encuestado.edad for e in encuestas]
    estratos = [str(e.encuestado.estrato) for e in encuestas]
    departamentos = [e.encuestado.departamento for e in encuestas]
    generos = [e.encuestado.genero or "no especificado" for e in encuestas]
    con_email = sum(1 for e in encuestas if e.encuestado.email)

    return EstadisticasResponse(
        total_encuestas=len(encuestas),
        promedio_edad=round(sum(edades) / len(edades), 2),
        distribucion_estrato=dict(Counter(estratos)),
        distribucion_departamento=dict(Counter(departamentos)),
        distribucion_genero=dict(Counter(generos)),
        tasa_completitud_email=round(con_email / len(encuestas) * 100, 2),
    )


# ── GET /encuestas/{id} ──────────────────────────────────────
@app.get(
    "/encuestas/{id}",
    response_model=EncuestaCompleta,
    status_code=status.HTTP_200_OK,
    summary="Obtener encuesta por ID",
    description="Retorna una encuesta específica por su UUID. HTTP 404 si no existe.",
    tags=["Encuestas"],
)
@log_request
@timer
async def obtener_encuesta(id: UUID, request: Request) -> EncuestaCompleta:
    id_str = str(id)
    if id_str not in repositorio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Encuesta con ID '{id_str}' no encontrada en el repositorio.",
        )
    return repositorio[id_str]


# ── PUT /encuestas/{id} ──────────────────────────────────────
@app.put(
    "/encuestas/{id}",
    response_model=EncuestaCompleta,
    status_code=status.HTTP_200_OK,
    summary="Actualizar encuesta existente",
    description=(
        "Reemplaza completamente una encuesta existente. "
        "HTTP 404 si el ID no existe. El ID del path tiene precedencia."
    ),
    tags=["Encuestas"],
)
@log_request
@timer
async def actualizar_encuesta(
    id: UUID,
    encuesta_actualizada: EncuestaCompleta,
    request: Request,
) -> EncuestaCompleta:
    id_str = str(id)
    if id_str not in repositorio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Encuesta con ID '{id_str}' no encontrada.",
        )
    # Preservar el ID original del path
    encuesta_con_id = encuesta_actualizada.model_copy(update={"id": id})
    repositorio[id_str] = encuesta_con_id
    logger.info("🔄 ACTUALIZACIÓN | ID: %s", id_str)
    return encuesta_con_id


# ── DELETE /encuestas/{id} ───────────────────────────────────
@app.delete(
    "/encuestas/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar encuesta",
    description="Elimina permanentemente una encuesta del repositorio. HTTP 404 si no existe.",
    tags=["Encuestas"],
)
@log_request
async def eliminar_encuesta(id: UUID, request: Request) -> Response:
    id_str = str(id)
    if id_str not in repositorio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Encuesta con ID '{id_str}' no encontrada.",
        )
    del repositorio[id_str]
    logger.info("🗑️  ELIMINACIÓN | ID: %s", id_str)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ══════════════════════════════════════════════════════════════
# BONIFICACIÓN: Serialización JSON vs Pickle (+0.1)
# ══════════════════════════════════════════════════════════════
@app.get(
    "/encuestas/exportar/{formato}",
    summary="Exportar encuestas en JSON o Pickle",
    description=(
        "Exporta todo el repositorio en el formato especificado.\n\n"
        "**JSON**: Formato de texto, interoperable entre lenguajes, "
        "legible por humanos, ideal para APIs y almacenamiento de largo plazo.\n\n"
        "**Pickle**: Formato binario exclusivo de Python, más rápido para "
        "serializar objetos Python complejos, pero NO interoperable y con "
        "riesgos de seguridad (nunca deserializar Pickle de fuentes no confiables)."
    ),
    tags=["Exportación"],
)
@log_request
@timer
async def exportar_encuestas(formato: str, request: Request) -> Response:
    formato = formato.lower()

    if formato not in ("json", "pickle"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato inválido. Use 'json' o 'pickle'.",
        )

    datos = [e.model_dump(mode="json") for e in repositorio.values()]

    if formato == "json":
        import json
        contenido = json.dumps(datos, ensure_ascii=False, indent=2, default=str)
        return Response(
            content=contenido,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=encuestas.json"},
        )
    else:
        contenido_pickle = pickle.dumps(datos)
        return Response(
            content=contenido_pickle,
            media_type="application/octet-stream",
            headers={"Content-Disposition": "attachment; filename=encuestas.pkl"},
        )


# ─────────────────────────────────────────────
# Evento de inicio
# ─────────────────────────────────────────────
@app.on_event("startup")
async def startup_event() -> None:
    logger.info("🚀 API de Encuestas Poblacionales iniciada correctamente.")
    logger.info("📖 Documentación disponible en: /docs (Swagger) | /redoc (Redoc)")


# ─────────────────────────────────────────────
# Punto de entrada directo
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
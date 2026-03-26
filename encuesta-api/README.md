# 🗳️ API de Gestión de Encuestas Poblacionales

> **Sistema de recolección y validación de datos de encuestas demográficas construido con FastAPI + Pydantic V2.**  
> Proyecto evaluativo — Semana III: Python para APIs e IA — USTA 2026.

---

## 🌐 Demo en Producción

| Interfaz | URL |
|----------|-----|
| 🖥️ **Frontend Web** | https://encuesta-api-3i2e.onrender.com/ |
| 📖 **Swagger UI** | https://encuesta-api-3i2e.onrender.com/docs |
| 📘 **Redoc** | https://encuesta-api-3i2e.onrender.com/redoc |
| 📊 **API Stats** | https://encuesta-api-3i2e.onrender.com/encuestas/estadisticas/ |

> ⚠️ El servicio gratuito de Render puede tardar ~50 segundos en responder si estuvo inactivo.

---

## 📋 Descripción del Proyecto

El sistema implementa un **pipeline de ingesta estadística** donde la validación actúa como **"aduana transaccional"**: ningún dato inconsistente, fuera de rango o estructuralmente inválido puede contaminar el repositorio de análisis.

El dominio del problema es deliberadamente estadístico: cada encuesta representa una unidad de observación con covariables sociodemográficas (edad, estrato, departamento) y respuestas de múltiples tipos (Likert, porcentaje, binaria, abierta).

### Arquitectura del Pipeline

```
Cliente (Swagger/Frontend)
        │
        ▼
FastAPI (ASGI Router)
        │
        ▼
Pydantic V2 (Validación — "Aduana Transaccional")
        │
   ┌────┴────┐
   │         │
✅ Válido  ❌ Inválido
   │         │
   ▼         ▼
Repositorio  HTTP 422
en Memoria   JSON estructurado
        │
        ▼
Estadísticas / Exportación
```

---

## 🚀 Instalación y Ejecución

### 1. Clonar el repositorio

```bash
git clone https://github.com/haiderrojassalazar089-bot/Actividad-Evaluativa-Proyecto-Aplicado-Python
cd Actividad-Evaluativa-Proyecto-Aplicado-Python/encuesta-api
```

### 2. Crear y activar entorno virtual

> **¿Por qué `venv` y no `conda`?**  
> Se eligió `venv` porque es la solución estándar de la biblioteca estándar de Python, no requiere instalación adicional y es ideal para proyectos de API donde se busca un entorno ligero y reproducible. `conda` es preferible cuando se trabaja con dependencias científicas complejas (C extensions, CUDA) o múltiples lenguajes.

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Ejecutar la API

```bash
uvicorn main:app --reload
```

La API quedará disponible en: `http://127.0.0.1:8000`

### 5. Verificar que funciona

```bash
# Abrir Frontend Web
http://127.0.0.1:8000/

# Abrir Swagger UI
http://127.0.0.1:8000/docs

# Correr los tests
pytest test/ -v
```

---

## 📦 Estructura del Proyecto

```
encuesta-api/
├── main.py              # Punto de entrada FastAPI + endpoints + decoradores + handler 422
├── models.py            # 3 Modelos Pydantic anidados + validadores de campo
├── validators.py        # 32 Departamentos de Colombia + constantes + funciones auxiliares
├── cliente_api.py       # ⭐ Cliente httpx + reporte pandas (Bonificación +0.1)
├── requirements.txt     # Dependencias con versiones fijas
├── README.md            # Este archivo
├── .gitignore           # Excluye __pycache__, .venv/, .pytest_cache/, etc.
├── .python-version      # Especifica Python 3.12.0 para Render
├── static/
│   └── index.html       # Frontend web del sistema
└── test/
    ├── __init__.py
    ├── test_models.py        # ⭐ 22 tests unitarios de modelos Pydantic
    └── test_endpoints.py     # ⭐ 13 tests de integración de endpoints
```

**Principio de separación de responsabilidades:**
- `validators.py` centraliza las reglas del dominio colombiano
- `models.py` define la estructura y validación de datos
- `main.py` orquesta los endpoints sin lógica de negocio

---

## 🔌 Endpoints API REST

| Verbo | Ruta | Descripción | Status Code |
|-------|------|-------------|-------------|
| `GET` | `/` | Frontend web del sistema | 200 |
| `POST` | `/encuestas/` | Registrar encuesta completa | **201 Created** |
| `GET` | `/encuestas/` | Listar todas las encuestas | **200 OK** |
| `GET` | `/encuestas/estadisticas/` | Resumen estadístico | **200 OK** |
| `GET` | `/encuestas/{id}` | Obtener encuesta por UUID | **200** / **404** |
| `PUT` | `/encuestas/{id}` | Actualizar encuesta existente | **200** / **404** |
| `DELETE` | `/encuestas/{id}` | Eliminar encuesta | **204 No Content** / **404** |
| `GET` | `/encuestas/exportar/{formato}` | Exportar en JSON o Pickle ⭐ | **200 OK** |

> **¿Por qué DELETE retorna 204 y no 200?**  
> `200 OK` = éxito + retorna contenido. `204 No Content` = éxito + no hay nada que retornar. Si eliminamos una encuesta ya no existe — no hay objeto que devolver.

> **¿Por qué `/estadisticas/` va antes de `/{id}`?**  
> FastAPI evalúa rutas en orden de declaración. Si `/{id}` estuviera primero, "estadisticas" sería interpretado como UUID y retornaría 404.

---

## 🧩 RF1 · Modelos Pydantic con Tipos Complejos

### Modelo 1 — `Encuestado`

```python
class Encuestado(BaseModel):
    nombre:          Annotated[str, Field(min_length=2, max_length=120)]
    edad:            Annotated[int, Field(ge=0, le=120)]      # restricción biológica
    estrato:         Annotated[int, Field(ge=1, le=6)]        # contexto colombiano
    departamento:    str                                       # validado vs 32 depts
    genero:          Optional[str] = None
    nivel_educativo: Optional[str] = None
    email:           Optional[str] = None
```

### Modelo 2 — `RespuestaEncuesta`

```python
class RespuestaEncuesta(BaseModel):
    id_pregunta:    str
    texto_pregunta: str
    tipo_pregunta:  str                       # likert | porcentaje | abierta | binaria
    puntaje:        Union[int, float, str]    # ← polimorfismo de tipo
    observacion:    Optional[str] = None
```

### Modelo 3 — `EncuestaCompleta` (Anidado)

```python
class EncuestaCompleta(BaseModel):
    id:              UUID     = Field(default_factory=uuid4)
    nombre_encuesta: str
    encuestado:      Encuestado                    # ← modelo anidado
    respuestas:      List[RespuestaEncuesta]        # ← List de modelos
    fecha_registro:  datetime = Field(default_factory=datetime.utcnow)
    activa:          bool     = True
```

**Tipos complejos utilizados:**

| Tipo | Para qué |
|------|----------|
| `List[RespuestaEncuesta]` | Vector homogéneo de observaciones |
| `Union[int, float, str]` | Polimorfismo según tipo de pregunta |
| `Optional[str]` | Fuerza manejo explícito de datos faltantes |
| `Annotated` | Embebe restricciones en la anotación de tipo |
| `UUID` | Identificador único universal auto-generado |

---

## 🛡️ RF2 · Validadores de Campo (@field_validator)

| Validador | Campo | mode | Qué hace |
|-----------|-------|------|----------|
| `limpiar_nombre` | nombre | `before` | Colapsa espacios, capitaliza |
| `normalizar_departamento` | departamento | `before` | Convierte a Title Case |
| `validar_departamento` | departamento | `after` | Verifica contra 32 departamentos |
| `validar_email` | email | `after` | Regex de formato de correo |
| `normalizar_genero` | genero | `before` | Convierte a minúsculas |
| `normalizar_nivel_educativo` | nivel_educativo | `before` | Valida catálogo de niveles |
| `validar_puntaje_segun_tipo` | puntaje + tipo | `model` | Likert[1-5] · Porcentaje[0-100] · Binario{0,1} |
| `validar_ids_unicos` | respuestas | `after` | IDs únicos — evita multicolinealidad |

### Diferencia entre `mode='before'` y `mode='after'`

```
Dato crudo → [before] → Coerción de tipos → [after] → Valor validado

mode='before': recibe el valor SIN tipar → ideal para limpiar y normalizar
mode='after':  recibe el valor YA tipado → ideal para verificar rangos y dominios
```

### Ejemplo — Validadores encadenados en `departamento`

```python
@field_validator("departamento", mode="before")   # PASO 1
@classmethod
def normalizar_departamento(cls, valor: str) -> str:
    return valor.strip().title()   # 'ANTIOQUIA' → 'Antioquia'

@field_validator("departamento", mode="after")    # PASO 2
@classmethod
def validar_departamento(cls, valor: str) -> str:
    if not es_departamento_valido(valor):
        raise ValueError(f"'{valor}' no es un departamento válido de Colombia.")
    return valor
```

---

## ⚠️ RF4 · Manejo de Errores HTTP 422

### Handler personalizado

```python
@app.exception_handler(RequestValidationError)
async def manejador_validacion(request: Request, exc: RequestValidationError):
    errores_detallados = []
    for error in exc.errors():
        campo = " → ".join(str(loc) for loc in error.get("loc", []))
        errores_detallados.append({
            "campo": campo,
            "mensaje": error.get("msg"),
            "tipo_error": error.get("type"),
            "valor_recibido": str(error.get("input"))[:100],
        })
    logger.warning("⚠️ VALIDACIÓN FALLIDA | Ruta: %s | Campos: %s", ...)
    return JSONResponse(status_code=422, content=respuesta.model_dump(mode="json"))
```

### Ejemplo de respuesta HTTP 422

```json
{
  "status_code": 422,
  "mensaje": "Error de validación: los datos no cumplen el esquema requerido.",
  "errores": [
    {
      "campo": "body → encuestado → edad",
      "mensaje": "Input should be less than or equal to 120",
      "tipo_error": "less_than_equal",
      "valor_recibido": "150"
    }
  ],
  "timestamp": "2026-03-25T22:00:00"
}
```

---

## ⚡ RF5 · Async/Await · ASGI vs WSGI

| | WSGI (Flask/Django) | ASGI (FastAPI) |
|--|---------------------|----------------|
| Modelo | 1 petición = 1 hilo bloqueado | Múltiples peticiones concurrentes |
| `async def` | ❌ No soporta | ✅ Nativo |
| I/O | Bloqueante | No bloqueante |
| Escala | Mal con I/O masivo | Excelente |

`async def` es **indispensable** para I/O real: PostgreSQL (asyncpg), microservicios (httpx), colas de mensajes (Kafka).

---

## 🎨 RT5 · Decoradores Personalizados

```python
@app.post("/encuestas/")   # decorador de ruta FastAPI
@log_request               # registra método, ruta e IP
@timer                     # mide tiempo de ejecución
async def crear_encuesta(...):
    ...
```

> **`@functools.wraps`**: preserva el nombre original de la función. Sin él, FastAPI mostraría todos los endpoints como "wrapper" en Swagger.

---

## 🧪 Tests con pytest (Bonificación +0.1)

```bash
pytest test/ -v
# 35 passed, 0 failed in 0.85s ✅
```

| Archivo | Tests | Cobertura |
|---------|-------|-----------|
| `test_models.py` | 22 | Modelos, validadores, restricciones |
| `test_endpoints.py` | 13 | Endpoints, status codes, HTTP 422 |

---

## 📤 Exportación JSON vs Pickle (Bonificación +0.1)

| Característica | JSON | Pickle |
|----------------|------|--------|
| Formato | Texto legible | Binario |
| Interoperable | ✅ Python, JS, Java... | ❌ Solo Python |
| Seguridad | ✅ Seguro | ⚠️ Nunca de fuentes desconocidas |
| Uso | APIs, almacenamiento | Caché interno Python |

---

## 🤖 Cliente Python (Bonificación +0.1)

```bash
python cliente_api.py
# Lee CSV → llama API con httpx → genera reporte pandas → exporta CSV
```

---

## ☁️ Despliegue en Render (Bonificación +0.2)

| Config | Valor |
|--------|-------|
| URL | https://encuesta-api-3i2e.onrender.com/ |
| Branch | main |
| Root Directory | encuesta-api |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Python Version | 3.12.0 |

---

## ✅ Competencias Cubiertas

### Requerimientos Funcionales
- [x] **RF1** — 3 modelos Pydantic anidados con `List`, `Union`, `Optional`, `Annotated`
- [x] **RF2** — 8 validadores con `mode='before'` y `mode='after'`, mensajes descriptivos
- [x] **RF3** — CRUD completo + estadísticas, status codes correctos
- [x] **RF4** — Handler HTTP 422 personalizado con JSON estructurado y logging
- [x] **RF5** — Endpoints `async def` con documentación ASGI vs WSGI

### Requerimientos Técnicos
- [x] **RT1** — Entorno virtual `venv` + `requirements.txt` + README
- [x] **RT2** — Git con 14+ commits, ramas `main` y `develop`, `.gitignore`
- [x] **RT3** — Estructura modular: `main.py`, `models.py`, `validators.py`
- [x] **RT4** — Swagger UI + Redoc con ejemplos JSON
- [x] **RT5** — Decoradores `@log_request` y `@timer` con `@functools.wraps`

### Bonificaciones
- [x] **+0.1** — 35 tests con pytest
- [x] **+0.1** — Exportación JSON vs Pickle
- [x] **+0.1** — Cliente Python httpx + pandas
- [x] **+0.2** — Despliegue en Render

---

## 👨‍💻 Tecnologías

| Tecnología | Versión | Para qué |
|------------|---------|----------|
| Python | 3.12.0 | Lenguaje base |
| FastAPI | 0.115.5 | Framework ASGI |
| Pydantic | 2.10.3 | Validación de datos |
| Uvicorn | 0.32.1 | Servidor ASGI |
| httpx | 0.28.1 | Cliente HTTP asíncrono |
| pandas | 2.2.3 | Análisis de datos |
| pytest | 8.3.4 | Framework de testing |
| Render | — | Despliegue en la nube |

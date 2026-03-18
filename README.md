# 🗳️ API de Gestión de Encuestas Poblacionales

Sistema de recolección y validación de datos de encuestas demográficas construido con **FastAPI + Pydantic V2**.  
Proyecto evaluativo — Semana III: Python para APIs e IA — USTA.

---

## 📋 Descripción

El sistema implementa un **pipeline de ingesta estadística** donde la validación actúa como "aduana transaccional": ningún dato inconsistente, fuera de rango o estructuralmente inválido puede contaminar el repositorio de análisis.

### Arquitectura del pipeline

```
Ingesta (POST) → Validación Pydantic V2 → Repositorio en memoria → Análisis estadístico
```

---

## 🚀 Instalación y Ejecución

### 1. Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd encuesta-api
```

### 2. Crear y activar entorno virtual

**¿Por qué `venv` y no `conda`?**  
Se eligió `venv` porque es la solución estándar de la biblioteca estándar de Python, no requiere instalación adicional y es ideal para proyectos de API donde se busca un entorno ligero y reproducible. `conda` es preferible cuando se trabaja con dependencias científicas complejas (C extensions, CUDA) o múltiples lenguajes.

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

---

## 📖 Documentación interactiva

| Interfaz | URL |
|----------|-----|
| Swagger UI | http://127.0.0.1:8000/docs |
| Redoc | http://127.0.0.1:8000/redoc |

---

## 🔌 Endpoints

| Verbo | Ruta | Descripción | Status |
|-------|------|-------------|--------|
| `POST` | `/encuestas/` | Registrar encuesta completa | 201 |
| `GET` | `/encuestas/` | Listar todas las encuestas | 200 |
| `GET` | `/encuestas/{id}` | Obtener encuesta por UUID | 200 / 404 |
| `PUT` | `/encuestas/{id}` | Actualizar encuesta existente | 200 / 404 |
| `DELETE` | `/encuestas/{id}` | Eliminar encuesta | 204 / 404 |
| `GET` | `/encuestas/estadisticas/` | Resumen estadístico | 200 |
| `GET` | `/encuestas/exportar/{formato}` | Exportar en JSON o Pickle | 200 |

---

## 📦 Estructura del proyecto

```
encuesta-api/
├── main.py           # Punto de entrada FastAPI + endpoints + decoradores
├── models.py         # Modelos Pydantic (Encuestado, RespuestaEncuesta, EncuestaCompleta)
├── validators.py     # Constantes y funciones auxiliares de validación
├── cliente_api.py    # Script cliente httpx + reporte pandas (bonificación)
├── requirements.txt  # Dependencias del proyecto
├── README.md         # Este archivo
├── .gitignore        # Archivos excluidos del control de versiones
└── tests/
    ├── test_models.py     # Tests unitarios de modelos Pydantic
    └── test_endpoints.py  # Tests de integración de endpoints
```

---

## 🧪 Ejecutar tests

```bash
pytest tests/ -v
```

---

## 🤖 Cliente Python (Bonificación)

El script `cliente_api.py` carga encuestas desde un CSV y genera un reporte estadístico:

```bash
# Con la API corriendo en otra terminal:
python cliente_api.py
```

---

## 📤 Exportación JSON vs Pickle

```bash
# Exportar como JSON (interoperable, texto legible)
GET /encuestas/exportar/json

# Exportar como Pickle (binario Python, más rápido)
GET /encuestas/exportar/pickle
```

**Diferencias clave:**
- **JSON**: interoperable entre lenguajes, legible por humanos, ideal para APIs
- **Pickle**: exclusivo de Python, más rápido, pero no seguro con fuentes desconocidas

---

## ✅ Competencias cubiertas

- [x] Modelos Pydantic anidados con `List`, `Union`, `Optional`
- [x] `@field_validator` con `mode='before'` y `mode='after'`
- [x] CRUD completo con verbos y status codes correctos
- [x] Manejador HTTP 422 personalizado con logging
- [x] Endpoint `async def` con comentarios ASGI/WSGI
- [x] Entorno virtual `venv` + `requirements.txt`
- [x] Documentación Swagger/Redoc con ejemplos JSON
- [x] Decoradores personalizados `@log_request` y `@timer`
- [x] Tests con pytest (modelos + endpoints)
- [x] Serialización JSON vs Pickle
- [x] Cliente Python con httpx + reporte pandas
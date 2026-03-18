"""
tests/test_endpoints.py
-----------------------
Tests de integración para los endpoints FastAPI (Bonificación +0.1).

Ejecución:
    pytest tests/ -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from main import app, repositorio

client = TestClient(app)

# Payload válido reutilizable
PAYLOAD_VALIDO = {
    "nombre_encuesta": "Encuesta de Prueba",
    "encuestado": {
        "nombre": "Carlos Gómez",
        "edad": 28,
        "estrato": 2,
        "departamento": "Antioquia",
        "genero": "masculino",
        "nivel_educativo": "universitario",
        "email": "cgomez@test.co",
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
            "texto_pregunta": "¿Cuál es su nivel de confianza?",
            "tipo_pregunta": "porcentaje",
            "puntaje": 65.5,
        },
    ],
}


@pytest.fixture(autouse=True)
def limpiar_repositorio():
    """Limpia el repositorio antes de cada test para independencia."""
    repositorio.clear()
    yield
    repositorio.clear()


# ══════════════════════════════════════════════════════════════
# Tests — POST /encuestas/
# ══════════════════════════════════════════════════════════════

class TestCrearEncuesta:

    def test_crear_encuesta_exitosa(self):
        """POST válido debe retornar HTTP 201 con la encuesta creada."""
        response = client.post("/encuestas/", json=PAYLOAD_VALIDO)
        assert response.status_code == 201
        data = response.json()
        assert data["nombre_encuesta"] == "Encuesta de Prueba"
        assert "id" in data

    def test_crear_encuesta_edad_invalida_retorna_422(self):
        """Edad fuera de rango debe retornar HTTP 422."""
        payload = dict(PAYLOAD_VALIDO)
        payload["encuestado"] = {**PAYLOAD_VALIDO["encuestado"], "edad": 150}
        response = client.post("/encuestas/", json=payload)
        assert response.status_code == 422
        data = response.json()
        assert "errores" in data

    def test_crear_encuesta_departamento_invalido_retorna_422(self):
        """Departamento inventado debe retornar HTTP 422."""
        payload = dict(PAYLOAD_VALIDO)
        payload["encuestado"] = {**PAYLOAD_VALIDO["encuestado"], "departamento": "Narnia"}
        response = client.post("/encuestas/", json=payload)
        assert response.status_code == 422

    def test_crear_encuesta_likert_fuera_rango_retorna_422(self):
        """Puntaje Likert > 5 debe retornar HTTP 422."""
        payload = {**PAYLOAD_VALIDO}
        payload["respuestas"] = [
            {"id_pregunta": "P01", "texto_pregunta": "¿Satisfacción?",
             "tipo_pregunta": "likert", "puntaje": 10}
        ]
        response = client.post("/encuestas/", json=payload)
        assert response.status_code == 422

    def test_respuesta_error_422_tiene_estructura_correcta(self):
        """El manejador personalizado debe retornar JSON estructurado."""
        payload = dict(PAYLOAD_VALIDO)
        payload["encuestado"] = {**PAYLOAD_VALIDO["encuestado"], "edad": -5}
        response = client.post("/encuestas/", json=payload)
        assert response.status_code == 422
        data = response.json()
        assert "errores" in data
        assert "mensaje" in data
        assert "timestamp" in data
        assert isinstance(data["errores"], list)


# ══════════════════════════════════════════════════════════════
# Tests — GET /encuestas/
# ══════════════════════════════════════════════════════════════

class TestListarEncuestas:

    def test_listar_repositorio_vacio(self):
        """GET en repositorio vacío debe retornar lista vacía."""
        response = client.get("/encuestas/")
        assert response.status_code == 200
        assert response.json() == []

    def test_listar_con_encuestas(self):
        """GET debe retornar todas las encuestas registradas."""
        client.post("/encuestas/", json=PAYLOAD_VALIDO)
        client.post("/encuestas/", json=PAYLOAD_VALIDO)
        response = client.get("/encuestas/")
        assert response.status_code == 200
        assert len(response.json()) == 2


# ══════════════════════════════════════════════════════════════
# Tests — GET /encuestas/{id}
# ══════════════════════════════════════════════════════════════

class TestObtenerEncuesta:

    def test_obtener_encuesta_existente(self):
        """GET por ID existente debe retornar la encuesta."""
        post_resp = client.post("/encuestas/", json=PAYLOAD_VALIDO)
        id_encuesta = post_resp.json()["id"]
        response = client.get(f"/encuestas/{id_encuesta}")
        assert response.status_code == 200
        assert response.json()["id"] == id_encuesta

    def test_obtener_encuesta_inexistente_retorna_404(self):
        """GET por ID inexistente debe retornar HTTP 404."""
        response = client.get("/encuestas/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404


# ══════════════════════════════════════════════════════════════
# Tests — DELETE /encuestas/{id}
# ══════════════════════════════════════════════════════════════

class TestEliminarEncuesta:

    def test_eliminar_encuesta_existente(self):
        """DELETE de encuesta existente debe retornar HTTP 204."""
        post_resp = client.post("/encuestas/", json=PAYLOAD_VALIDO)
        id_encuesta = post_resp.json()["id"]
        response = client.delete(f"/encuestas/{id_encuesta}")
        assert response.status_code == 204

    def test_eliminar_encuesta_inexistente_retorna_404(self):
        """DELETE de encuesta inexistente debe retornar HTTP 404."""
        response = client.delete("/encuestas/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404


# ══════════════════════════════════════════════════════════════
# Tests — GET /encuestas/estadisticas/
# ══════════════════════════════════════════════════════════════

class TestEstadisticas:

    def test_estadisticas_repositorio_vacio(self):
        """Estadísticas en repositorio vacío deben retornar ceros."""
        response = client.get("/encuestas/estadisticas/")
        assert response.status_code == 200
        data = response.json()
        assert data["total_encuestas"] == 0

    def test_estadisticas_con_datos(self):
        """Estadísticas deben calcularse correctamente."""
        client.post("/encuestas/", json=PAYLOAD_VALIDO)
        response = client.get("/encuestas/estadisticas/")
        assert response.status_code == 200
        data = response.json()
        assert data["total_encuestas"] == 1
        assert data["promedio_edad"] == 28.0
        assert "2" in data["distribucion_estrato"]

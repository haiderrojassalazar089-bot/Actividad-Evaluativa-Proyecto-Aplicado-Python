"""
tests/test_models.py
--------------------
Tests unitarios para los modelos Pydantic (Bonificación +0.1).
Valida que las restricciones estadísticas funcionen correctamente.

Ejecución:
    pytest tests/ -v
"""

import pytest
from pydantic import ValidationError

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Encuestado, RespuestaEncuesta, EncuestaCompleta


# ══════════════════════════════════════════════════════════════
# Tests — Encuestado
# ══════════════════════════════════════════════════════════════

class TestEncuestado:

    def test_encuestado_valido(self):
        """Un encuestado con datos correctos debe crearse sin errores."""
        enc = Encuestado(
            nombre="María Fernanda López",
            edad=34,
            estrato=3,
            departamento="Cundinamarca",
        )
        assert enc.nombre == "María Fernanda López"
        assert enc.edad == 34
        assert enc.estrato == 3

    def test_edad_fuera_de_rango_superior(self):
        """Edad mayor a 120 viola restricción biológica."""
        with pytest.raises(ValidationError) as exc_info:
            Encuestado(nombre="Test", edad=121, estrato=1, departamento="Antioquia")
        assert "edad" in str(exc_info.value).lower() or "121" in str(exc_info.value)

    def test_edad_negativa(self):
        """Edad negativa es biológicamente imposible."""
        with pytest.raises(ValidationError):
            Encuestado(nombre="Test", edad=-1, estrato=1, departamento="Antioquia")

    def test_estrato_invalido_mayor(self):
        """Estrato mayor a 6 no existe en Colombia."""
        with pytest.raises(ValidationError):
            Encuestado(nombre="Test", edad=25, estrato=7, departamento="Antioquia")

    def test_estrato_invalido_menor(self):
        """Estrato menor a 1 no existe."""
        with pytest.raises(ValidationError):
            Encuestado(nombre="Test", edad=25, estrato=0, departamento="Antioquia")

    def test_departamento_invalido(self):
        """Un departamento inventado debe fallar la validación."""
        with pytest.raises(ValidationError) as exc_info:
            Encuestado(nombre="Test", edad=25, estrato=3, departamento="Utopía")
        assert "utopía" in str(exc_info.value).lower() or "válido" in str(exc_info.value).lower()

    def test_departamento_case_insensitive(self):
        """El validador debe aceptar el departamento en cualquier capitalización."""
        enc = Encuestado(nombre="Test User", edad=25, estrato=3, departamento="ANTIOQUIA")
        assert enc.departamento == "Antioquia"

    def test_nombre_limpia_espacios(self):
        """El validador before debe colapsar espacios múltiples."""
        enc = Encuestado(nombre="  Juan   Pablo  ", edad=30, estrato=2, departamento="Bogotá D.C.")
        assert enc.nombre == "Juan Pablo"

    def test_email_valido(self):
        """Email con formato correcto debe aceptarse."""
        enc = Encuestado(
            nombre="Ana Ruiz", edad=28, estrato=4,
            departamento="Valle del Cauca", email="ana@test.co"
        )
        assert enc.email == "ana@test.co"

    def test_email_invalido(self):
        """Email malformado debe rechazarse."""
        with pytest.raises(ValidationError):
            Encuestado(
                nombre="Ana Ruiz", edad=28, estrato=4,
                departamento="Valle del Cauca", email="no-es-un-email"
            )


# ══════════════════════════════════════════════════════════════
# Tests — RespuestaEncuesta
# ══════════════════════════════════════════════════════════════

class TestRespuestaEncuesta:

    def test_respuesta_likert_valida(self):
        """Likert con valor 1-5 debe ser aceptado."""
        r = RespuestaEncuesta(
            id_pregunta="P01",
            texto_pregunta="¿Satisfacción con el servicio?",
            tipo_pregunta="likert",
            puntaje=4,
        )
        assert r.puntaje == 4

    def test_likert_fuera_de_rango(self):
        """Likert con valor 6 viola la escala clásica de 5 niveles."""
        with pytest.raises(ValidationError):
            RespuestaEncuesta(
                id_pregunta="P01",
                texto_pregunta="¿Satisfacción?",
                tipo_pregunta="likert",
                puntaje=6,
            )

    def test_porcentaje_valido(self):
        """Porcentaje en [0, 100] debe aceptarse."""
        r = RespuestaEncuesta(
            id_pregunta="P02",
            texto_pregunta="¿Confianza institucional?",
            tipo_pregunta="porcentaje",
            puntaje=75.5,
        )
        assert r.puntaje == 75.5

    def test_porcentaje_fuera_de_rango(self):
        """Porcentaje mayor a 100 es inválido."""
        with pytest.raises(ValidationError):
            RespuestaEncuesta(
                id_pregunta="P02",
                texto_pregunta="¿Confianza?",
                tipo_pregunta="porcentaje",
                puntaje=150.0,
            )

    def test_binaria_valida(self):
        """Binaria con valor 0 o 1 debe aceptarse."""
        r = RespuestaEncuesta(
            id_pregunta="P03",
            texto_pregunta="¿Votó en las últimas elecciones?",
            tipo_pregunta="binaria",
            puntaje=1,
        )
        assert r.puntaje == 1

    def test_binaria_invalida(self):
        """Binaria con valor distinto de 0/1 debe rechazarse."""
        with pytest.raises(ValidationError):
            RespuestaEncuesta(
                id_pregunta="P03",
                texto_pregunta="¿Votó?",
                tipo_pregunta="binaria",
                puntaje=2,
            )

    def test_tipo_pregunta_invalido(self):
        """Tipo de pregunta fuera del catálogo debe rechazarse."""
        with pytest.raises(ValidationError):
            RespuestaEncuesta(
                id_pregunta="P04",
                texto_pregunta="¿Test?",
                tipo_pregunta="desconocido",
                puntaje=3,
            )


# ══════════════════════════════════════════════════════════════
# Tests — EncuestaCompleta
# ══════════════════════════════════════════════════════════════

class TestEncuestaCompleta:

    def _encuesta_base(self) -> dict:
        return {
            "nombre_encuesta": "Encuesta Test",
            "encuestado": {
                "nombre": "Test User",
                "edad": 30,
                "estrato": 3,
                "departamento": "Antioquia",
            },
            "respuestas": [
                {
                    "id_pregunta": "P01",
                    "texto_pregunta": "¿Satisfacción con el servicio?",
                    "tipo_pregunta": "likert",
                    "puntaje": 4,
                }
            ],
        }

    def test_encuesta_completa_valida(self):
        """Encuesta con datos correctos debe instanciarse correctamente."""
        enc = EncuestaCompleta(**self._encuesta_base())
        assert enc.nombre_encuesta == "Encuesta Test"
        assert len(enc.respuestas) == 1

    def test_respuestas_vacias_rechazadas(self):
        """Una encuesta sin respuestas debe rechazarse."""
        datos = self._encuesta_base()
        datos["respuestas"] = []
        with pytest.raises(ValidationError):
            EncuestaCompleta(**datos)

    def test_ids_pregunta_duplicados_rechazados(self):
        """IDs de pregunta duplicados introducen multicolinealidad artificial."""
        datos = self._encuesta_base()
        datos["respuestas"] = [
            {"id_pregunta": "P01", "texto_pregunta": "¿Test 1?", "tipo_pregunta": "likert", "puntaje": 3},
            {"id_pregunta": "P01", "texto_pregunta": "¿Test 2?", "tipo_pregunta": "likert", "puntaje": 4},
        ]
        with pytest.raises(ValidationError) as exc_info:
            EncuestaCompleta(**datos)
        assert "duplicados" in str(exc_info.value).lower() or "P01" in str(exc_info.value)

    def test_uuid_generado_automaticamente(self):
        """El ID UUID debe generarse automáticamente."""
        enc = EncuestaCompleta(**self._encuesta_base())
        assert enc.id is not None

    def test_fecha_registro_generada(self):
        """La fecha de registro debe generarse automáticamente."""
        enc = EncuestaCompleta(**self._encuesta_base())
        assert enc.fecha_registro is not None
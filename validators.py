"""
validators.py
-------------
Constantes y funciones auxiliares de validación para la API de Encuestas.
Centraliza las reglas del dominio (listas de referencia, rangos, etc.)
separándolas de los modelos Pydantic para mayor mantenibilidad.
"""

# ─────────────────────────────────────────────
# Listado oficial de los 32 departamentos de
# Colombia + D.C., en minúsculas normalizadas.
# ─────────────────────────────────────────────
DEPARTAMENTOS_COLOMBIA: set[str] = {
    "amazonas", "antioquia", "arauca", "atlántico", "bolívar",
    "boyacá", "caldas", "caquetá", "casanare", "cauca",
    "cesar", "chocó", "córdoba", "cundinamarca", "guainía",
    "guaviare", "huila", "la guajira", "magdalena", "meta",
    "nariño", "norte de santander", "putumayo", "quindío",
    "risaralda", "san andrés y providencia", "santander", "sucre",
    "tolima", "valle del cauca", "vaupés", "vichada",
    "bogotá d.c.", "bogota d.c.", "bogotá", "bogota",
}

# ─────────────────────────────────────────────
# Tipos de pregunta admitidos en la encuesta
# ─────────────────────────────────────────────
TIPOS_PREGUNTA_VALIDOS: set[str] = {"likert", "porcentaje", "abierta", "binaria"}

# ─────────────────────────────────────────────
# Rangos numéricos del dominio
# ─────────────────────────────────────────────
EDAD_MIN: int = 0
EDAD_MAX: int = 120

ESTRATO_MIN: int = 1
ESTRATO_MAX: int = 6

LIKERT_MIN: int = 1
LIKERT_MAX: int = 5

PORCENTAJE_MIN: float = 0.0
PORCENTAJE_MAX: float = 100.0


def normalizar_texto(valor: str) -> str:
    """Elimina espacios extremos y convierte a minúsculas."""
    return valor.strip().lower()


def es_departamento_valido(departamento: str) -> bool:
    """Comprueba si el departamento pertenece al listado oficial."""
    return normalizar_texto(departamento) in DEPARTAMENTOS_COLOMBIA


def es_puntaje_likert_valido(puntaje: int) -> bool:
    """Valida que el puntaje Likert esté en [1, 5]."""
    return LIKERT_MIN <= puntaje <= LIKERT_MAX


def es_porcentaje_valido(valor: float) -> bool:
    """Valida que el porcentaje esté en [0.0, 100.0]."""
    return PORCENTAJE_MIN <= valor <= PORCENTAJE_MAX

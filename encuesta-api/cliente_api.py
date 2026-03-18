"""
cliente_api.py
--------------
Script cliente Python independiente (Bonificación +0.1).

Funciones:
    1. Lee encuestas desde un archivo CSV (datos_encuestas.csv)
    2. Las envía a la API usando httpx (cliente HTTP asíncrono)
    3. Genera un reporte estadístico con pandas
    4. Exporta el reporte a reporte_estadistico.csv

Uso:
    # Asegúrese de que la API esté corriendo:
    # uvicorn main:app --reload

    python cliente_api.py
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pandas as pd

API_BASE = "http://127.0.0.1:8000"
CSV_ENTRADA = Path(__file__).parent / "datos_encuestas.csv"
CSV_REPORTE = Path(__file__).parent / "reporte_estadistico.csv"


# ─────────────────────────────────────────────
# Generador de CSV de prueba
# ─────────────────────────────────────────────
def generar_csv_prueba() -> None:
    """Crea un CSV de muestra si no existe."""
    filas = [
        "nombre,edad,estrato,departamento,genero,nivel_educativo,email,pregunta,tipo,puntaje",
        "Laura Medina,29,3,Antioquia,femenino,universitario,lmedina@test.co,¿Satisfacción con el servicio?,likert,4",
        "Pedro Ruiz,45,2,Cundinamarca,masculino,secundaria,,¿Confianza institucional?,porcentaje,72.5",
        "Ana Torres,22,4,Valle del Cauca,femenino,universitario,atorres@test.co,¿Satisfacción con el servicio?,likert,5",
        "Jorge Mora,58,1,Bolívar,masculino,primaria,,¿Confianza institucional?,porcentaje,30.0",
        "Sofía Pinto,34,5,Bogotá D.C.,femenino,posgrado,spinto@test.co,¿Satisfacción con el servicio?,likert,3",
        "Luis Soto,41,3,Santander,masculino,técnico,,¿Confianza institucional?,porcentaje,55.0",
        "Camila Vega,27,2,Nariño,femenino,universitario,cvega@test.co,¿Satisfacción con el servicio?,likert,2",
        "Andrés Gil,63,1,Chocó,masculino,primaria,,¿Confianza institucional?,porcentaje,15.0",
    ]
    with open(CSV_ENTRADA, "w", encoding="utf-8") as f:
        f.write("\n".join(filas))
    print(f"📄 CSV de prueba creado: {CSV_ENTRADA}")


def csv_a_payloads(ruta_csv: Path) -> list[dict]:
    """
    Lee el CSV y construye los payloads JSON para la API.
    Agrupa las filas por encuestado (mismo nombre).
    """
    df = pd.read_csv(ruta_csv)
    payloads = []
    contador_pregunta = {}

    for nombre, grupo in df.groupby("nombre"):
        primera_fila = grupo.iloc[0]
        respuestas = []
        contador_pregunta[nombre] = contador_pregunta.get(nombre, 0)

        for _, fila in grupo.iterrows():
            contador_pregunta[nombre] += 1
            pid = f"P{contador_pregunta[nombre]:02d}"
            puntaje = fila["puntaje"]
            tipo = fila["tipo"].strip().lower()

            # Conversión de tipo según la pregunta
            if tipo == "likert":
                puntaje = int(puntaje)
            elif tipo == "porcentaje":
                puntaje = float(puntaje)

            respuestas.append({
                "id_pregunta": pid,
                "texto_pregunta": str(fila["pregunta"]),
                "tipo_pregunta": tipo,
                "puntaje": puntaje,
            })

        email = str(primera_fila.get("email", "")).strip()
        payload = {
            "nombre_encuesta": "Encuesta Ciudadana 2025 - Carga CSV",
            "encuestado": {
                "nombre": str(primera_fila["nombre"]),
                "edad": int(primera_fila["edad"]),
                "estrato": int(primera_fila["estrato"]),
                "departamento": str(primera_fila["departamento"]),
                "genero": str(primera_fila.get("genero", "")).strip() or None,
                "nivel_educativo": str(primera_fila.get("nivel_educativo", "")).strip() or None,
                "email": email if email and email != "nan" else None,
            },
            "respuestas": respuestas,
        }
        payloads.append(payload)

    return payloads


# ─────────────────────────────────────────────
# Cliente asíncrono
# ─────────────────────────────────────────────
async def cargar_encuestas(payloads: list[dict]) -> tuple[list, list]:
    """Envía cada payload a POST /encuestas/ y recoge resultados."""
    exitosos, fallidos = [], []

    async with httpx.AsyncClient(base_url=API_BASE, timeout=10.0) as cliente:
        for i, payload in enumerate(payloads, 1):
            try:
                respuesta = await cliente.post("/encuestas/", json=payload)
                if respuesta.status_code == 201:
                    exitosos.append(respuesta.json())
                    print(f"  ✅ [{i}/{len(payloads)}] Encuesta cargada: "
                          f"{payload['encuestado']['nombre']}")
                else:
                    fallidos.append({"payload": payload, "error": respuesta.json()})
                    print(f"  ❌ [{i}/{len(payloads)}] Error {respuesta.status_code}: "
                          f"{payload['encuestado']['nombre']}")
            except httpx.ConnectError:
                print("\n❌ No se pudo conectar a la API. "
                      "Asegúrese de que esté corriendo con: uvicorn main:app --reload")
                sys.exit(1)

    return exitosos, fallidos


async def obtener_estadisticas() -> dict:
    """Consulta GET /encuestas/estadisticas/ y retorna el JSON."""
    async with httpx.AsyncClient(base_url=API_BASE, timeout=10.0) as cliente:
        respuesta = await cliente.get("/encuestas/estadisticas/")
        return respuesta.json()


# ─────────────────────────────────────────────
# Generador de reporte pandas
# ─────────────────────────────────────────────
def generar_reporte(exitosos: list[dict], stats: dict) -> pd.DataFrame:
    """
    Construye un DataFrame con métricas estadísticas
    y lo exporta a CSV.
    """
    filas = []
    for enc in exitosos:
        encuestado = enc.get("encuestado", {})
        respuestas = enc.get("respuestas", [])
        puntajes_numericos = [
            r["puntaje"] for r in respuestas
            if isinstance(r["puntaje"], (int, float))
        ]
        filas.append({
            "nombre": encuestado.get("nombre"),
            "edad": encuestado.get("edad"),
            "estrato": encuestado.get("estrato"),
            "departamento": encuestado.get("departamento"),
            "genero": encuestado.get("genero"),
            "total_respuestas": len(respuestas),
            "puntaje_promedio": round(
                sum(puntajes_numericos) / len(puntajes_numericos), 2
            ) if puntajes_numericos else None,
        })

    df = pd.DataFrame(filas)

    print("\n" + "═" * 55)
    print("  📊 REPORTE ESTADÍSTICO — Encuesta Ciudadana 2025")
    print("═" * 55)
    print(f"  Total encuestas cargadas : {stats.get('total_encuestas', 0)}")
    print(f"  Promedio de edad         : {stats.get('promedio_edad', 'N/A')}")
    print(f"  Completitud email        : {stats.get('tasa_completitud_email', 0)}%")

    print("\n  📌 Distribución por Estrato:")
    for estrato, conteo in sorted(stats.get("distribucion_estrato", {}).items()):
        barra = "█" * conteo
        print(f"     Estrato {estrato}: {barra} ({conteo})")

    print("\n  🗺️  Distribución por Departamento:")
    for dept, conteo in stats.get("distribucion_departamento", {}).items():
        print(f"     {dept:<25} : {conteo}")

    if not df.empty:
        print("\n  📈 Estadísticas descriptivas (edad):")
        print(df["edad"].describe().to_string())

    df.to_csv(CSV_REPORTE, index=False, encoding="utf-8")
    print(f"\n  💾 Reporte guardado en: {CSV_REPORTE}")
    print("═" * 55 + "\n")

    return df


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
async def main() -> None:
    print("\n🔌 Cliente API — Encuestas Poblacionales")
    print("─" * 40)

    # 1. Generar CSV de prueba si no existe
    if not CSV_ENTRADA.exists():
        generar_csv_prueba()

    # 2. Leer CSV y construir payloads
    print(f"\n📂 Leyendo datos desde: {CSV_ENTRADA}")
    payloads = csv_a_payloads(CSV_ENTRADA)
    print(f"   {len(payloads)} encuestas encontradas en el CSV")

    # 3. Cargar encuestas en la API
    print("\n📡 Enviando encuestas a la API...")
    exitosos, fallidos = await cargar_encuestas(payloads)
    print(f"\n   ✅ Exitosas: {len(exitosos)}  |  ❌ Fallidas: {len(fallidos)}")

    # 4. Obtener estadísticas
    print("\n📊 Consultando estadísticas...")
    stats = await obtener_estadisticas()

    # 5. Generar reporte
    generar_reporte(exitosos, stats)


if __name__ == "__main__":
    asyncio.run(main())

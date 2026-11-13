"""Carga celdas de DEMOSTRACIÓN en una base de datos aparte de la real.

No se ejecuta automáticamente. Uso:
    python cargar_celdas_demo.py            (crea/usa parqueadero_demo.db)
    python cargar_celdas_demo.py ruta.db    (otra base de datos de demostración)

Por seguridad, se niega a escribir en parqueadero.db (la base de datos real).

Para ver las celdas en la aplicación (PowerShell):
    $env:BASE_DE_DATOS = "parqueadero_demo.db"; python app.py
"""
import os
import sys

import database

CARPETA_PROYECTO = os.path.dirname(os.path.abspath(__file__))

CELDAS_DEMO = [
    ("Zona A", "Automóvil", "Disponible"),
    ("Zona A", "Automóvil", "Ocupada"),
    ("Zona B", "Motocicleta", "Disponible"),
    ("Zona B", "Motocicleta", "Ocupada"),
]


def es_base_de_datos_real(ruta_bd):
    """True si la ruta es la base de datos real del proyecto (o un archivo llamado parqueadero.db)."""
    ruta = os.path.abspath(ruta_bd)
    real = os.path.join(CARPETA_PROYECTO, "parqueadero.db")
    return (
        os.path.normcase(ruta) == os.path.normcase(real)
        or os.path.basename(ruta).lower() == "parqueadero.db"
    )


def cargar_celdas_demo(ruta_bd):
    """Agrega las celdas de demostración solo si la tabla está vacía. Devuelve cuántas agregó."""
    if es_base_de_datos_real(ruta_bd):
        raise ValueError(
            "No se cargan datos de demostración en parqueadero.db (la base de datos real). "
            "Use otra ruta, por ejemplo parqueadero_demo.db."
        )
    database.crear_tablas(ruta_bd)
    conexion = database.conectar(ruta_bd)
    try:
        with conexion:
            if database.contar_celdas(conexion) > 0:
                return 0
            for ubicacion, tipo_vehiculo, estado in CELDAS_DEMO:
                database.crear_celda(conexion, ubicacion, tipo_vehiculo, estado)
        return len(CELDAS_DEMO)
    finally:
        conexion.close()


if __name__ == "__main__":
    ruta = sys.argv[1] if len(sys.argv) > 1 else "parqueadero_demo.db"
    try:
        agregadas = cargar_celdas_demo(ruta)
    except ValueError as error:
        print(error)
        sys.exit(1)
    if agregadas:
        print(f"Se agregaron {agregadas} celdas de demostración en {ruta}.")
    else:
        print(f"{ruta} ya tiene celdas registradas; no se agregó nada.")

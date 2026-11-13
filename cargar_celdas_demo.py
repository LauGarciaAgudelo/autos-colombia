"""Carga celdas de DEMOSTRACIÓN en una base de datos aparte de la real.

No se ejecuta automáticamente. Uso:
    python cargar_celdas_demo.py            (crea/usa parqueadero_demo.db)
    python cargar_celdas_demo.py ruta.db    (otra base de datos de demostración)

Para ver las celdas en la aplicación (PowerShell):
    $env:BASE_DE_DATOS = "parqueadero_demo.db"; python app.py
"""
import sys

import database

CELDAS_DEMO = [
    ("Zona A", "Automóvil", "Disponible"),
    ("Zona A", "Automóvil", "Ocupada"),
    ("Zona B", "Motocicleta", "Disponible"),
    ("Zona B", "Motocicleta", "Ocupada"),
]


def cargar_celdas_demo(ruta_bd):
    """Agrega las celdas de demostración solo si la tabla está vacía. Devuelve cuántas agregó."""
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
    agregadas = cargar_celdas_demo(ruta)
    if agregadas:
        print(f"Se agregaron {agregadas} celdas de demostración en {ruta}.")
    else:
        print(f"{ruta} ya tiene celdas registradas; no se agregó nada.")

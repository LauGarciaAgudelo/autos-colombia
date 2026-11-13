import sqlite3


def conectar(ruta_bd):
    conexion = sqlite3.connect(ruta_bd)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


def crear_tablas(ruta_bd):
    """Crea las tablas si no existen; no borra datos previos."""
    conexion = conectar(ruta_bd)
    with conexion:
        conexion.execute(
            """
            CREATE TABLE IF NOT EXISTS vehiculos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                placa TEXT NOT NULL UNIQUE,
                tipo TEXT NOT NULL
            )
            """
        )
        conexion.execute(
            """
            CREATE TABLE IF NOT EXISTS movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehiculo_id INTEGER NOT NULL,
                fecha_entrada TEXT NOT NULL,
                fecha_salida TEXT,
                FOREIGN KEY (vehiculo_id) REFERENCES vehiculos (id)
            )
            """
        )
        # Garantiza que un vehículo no tenga dos entradas activas (sin fecha de salida)
        conexion.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS indice_entrada_activa
            ON movimientos (vehiculo_id) WHERE fecha_salida IS NULL
            """
        )
    conexion.close()


def buscar_vehiculo_por_placa(conexion, placa):
    return conexion.execute(
        "SELECT id, placa, tipo FROM vehiculos WHERE placa = ?", (placa,)
    ).fetchone()


def crear_vehiculo(conexion, placa, tipo):
    cursor = conexion.execute(
        "INSERT INTO vehiculos (placa, tipo) VALUES (?, ?)", (placa, tipo)
    )
    return cursor.lastrowid


def vehiculo_esta_dentro(conexion, vehiculo_id):
    fila = conexion.execute(
        "SELECT id FROM movimientos WHERE vehiculo_id = ? AND fecha_salida IS NULL",
        (vehiculo_id,),
    ).fetchone()
    return fila is not None


def crear_movimiento_entrada(conexion, vehiculo_id, fecha_entrada):
    conexion.execute(
        "INSERT INTO movimientos (vehiculo_id, fecha_entrada) VALUES (?, ?)",
        (vehiculo_id, fecha_entrada),
    )


def buscar_movimiento_activo(conexion, vehiculo_id):
    return conexion.execute(
        "SELECT id, fecha_entrada FROM movimientos "
        "WHERE vehiculo_id = ? AND fecha_salida IS NULL",
        (vehiculo_id,),
    ).fetchone()


def buscar_movimiento(conexion, movimiento_id):
    return conexion.execute(
        "SELECT id, vehiculo_id, fecha_entrada, fecha_salida FROM movimientos WHERE id = ?",
        (movimiento_id,),
    ).fetchone()


def contar_movimientos(conexion):
    return conexion.execute("SELECT COUNT(*) FROM movimientos").fetchone()[0]


def consultar_movimientos(conexion, placa="", estado="todos"):
    """Lista movimientos con su vehículo, del más reciente al más antiguo.
    La placa puede ser parcial (placa ya en mayúsculas); estado: todos, dentro o salio."""
    sql = (
        "SELECT m.id, v.placa, v.tipo, m.fecha_entrada, m.fecha_salida "
        "FROM movimientos m JOIN vehiculos v ON v.id = m.vehiculo_id WHERE 1 = 1"
    )
    parametros = []
    if placa:
        sql += " AND instr(v.placa, ?) > 0"
        parametros.append(placa)
    if estado == "dentro":
        sql += " AND m.fecha_salida IS NULL"
    elif estado == "salio":
        sql += " AND m.fecha_salida IS NOT NULL"
    sql += " ORDER BY m.fecha_entrada DESC, m.id DESC"
    return conexion.execute(sql, parametros).fetchall()


def registrar_fecha_salida(conexion, movimiento_id, vehiculo_id, fecha_salida):
    """Cierra el movimiento solo si es del vehículo indicado y sigue activo.
    Devuelve True si se actualizó exactamente un registro."""
    cursor = conexion.execute(
        "UPDATE movimientos SET fecha_salida = ? "
        "WHERE id = ? AND vehiculo_id = ? AND fecha_salida IS NULL",
        (fecha_salida, movimiento_id, vehiculo_id),
    )
    return cursor.rowcount == 1

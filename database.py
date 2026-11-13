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
                tipo_vehiculo TEXT NOT NULL
            )
            """
        )
        conexion.execute(
            """
            CREATE TABLE IF NOT EXISTS movimientos (
                id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
                vehiculo_id INTEGER NOT NULL,
                fecha_hora_entrada TEXT NOT NULL,
                fecha_hora_salida TEXT,
                id_celda INTEGER,
                id_usuario INTEGER,
                FOREIGN KEY (vehiculo_id) REFERENCES vehiculos (id),
                FOREIGN KEY (id_celda) REFERENCES celdas (id_celda),
                FOREIGN KEY (id_usuario) REFERENCES usuarios (id_usuario)
            )
            """
        )
        renombrar_columnas_antiguas(conexion)
        agregar_columnas_de_asignacion(conexion)
        conexion.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                documento TEXT NOT NULL UNIQUE,
                correo TEXT NOT NULL
            )
            """
        )
        # tipo_vehiculo no está en el modelo relacional: se agregó para validar la compatibilidad (RF09)
        conexion.execute(
            """
            CREATE TABLE IF NOT EXISTS celdas (
                id_celda INTEGER PRIMARY KEY AUTOINCREMENT,
                ubicacion TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'Disponible'
                    CHECK (estado IN ('Disponible', 'Ocupada')),
                tipo_vehiculo TEXT NOT NULL
                    CHECK (tipo_vehiculo IN ('Automóvil', 'Motocicleta'))
            )
            """
        )
        # Garantiza que un vehículo no tenga dos entradas activas (sin fecha de salida)
        conexion.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS indice_entrada_activa
            ON movimientos (vehiculo_id) WHERE fecha_hora_salida IS NULL
            """
        )
        # Garantiza que una celda no esté asignada a dos movimientos activos a la vez
        conexion.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS indice_celda_ocupada
            ON movimientos (id_celda)
            WHERE fecha_hora_salida IS NULL AND id_celda IS NOT NULL
            """
        )
    conexion.close()


def agregar_columnas_de_asignacion(conexion):
    """Agrega id_celda e id_usuario a una base de datos anterior; los movimientos existentes
    quedan con ambas vacías y no se modifica ningún dato."""
    columnas = [fila["name"] for fila in conexion.execute("PRAGMA table_info(movimientos)")]
    if "id_celda" not in columnas:
        conexion.execute(
            "ALTER TABLE movimientos ADD COLUMN id_celda INTEGER REFERENCES celdas (id_celda)"
        )
    if "id_usuario" not in columnas:
        conexion.execute(
            "ALTER TABLE movimientos ADD COLUMN id_usuario INTEGER REFERENCES usuarios (id_usuario)"
        )


def renombrar_columnas_antiguas(conexion):
    """Actualiza una base de datos creada con los nombres anteriores, conservando sus datos."""
    cambios = [
        ("vehiculos", "tipo", "tipo_vehiculo"),
        ("movimientos", "id", "id_movimiento"),
        ("movimientos", "fecha_entrada", "fecha_hora_entrada"),
        ("movimientos", "fecha_salida", "fecha_hora_salida"),
    ]
    for tabla, nombre_antiguo, nombre_nuevo in cambios:
        columnas = [fila["name"] for fila in conexion.execute(f"PRAGMA table_info({tabla})")]
        if nombre_antiguo in columnas and nombre_nuevo not in columnas:
            conexion.execute(
                f"ALTER TABLE {tabla} RENAME COLUMN {nombre_antiguo} TO {nombre_nuevo}"
            )


def buscar_usuario_por_documento(conexion, documento):
    return conexion.execute(
        "SELECT id_usuario, nombre, documento, correo FROM usuarios WHERE documento = ?",
        (documento,),
    ).fetchone()


def crear_usuario(conexion, nombre, documento, correo):
    cursor = conexion.execute(
        "INSERT INTO usuarios (nombre, documento, correo) VALUES (?, ?, ?)",
        (nombre, documento, correo),
    )
    return cursor.lastrowid


def buscar_usuario_por_id(conexion, id_usuario):
    return conexion.execute(
        "SELECT id_usuario, nombre, documento, correo FROM usuarios WHERE id_usuario = ?",
        (id_usuario,),
    ).fetchone()


def actualizar_usuario(conexion, id_usuario, nombre, documento, correo):
    """Actualiza solo al usuario indicado. Devuelve True si existía y se actualizó."""
    cursor = conexion.execute(
        "UPDATE usuarios SET nombre = ?, documento = ?, correo = ? WHERE id_usuario = ?",
        (nombre, documento, correo, id_usuario),
    )
    return cursor.rowcount == 1


def contar_usuarios(conexion):
    return conexion.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]


def consultar_usuarios(conexion, busqueda=""):
    """Lista usuarios ordenados por nombre. La búsqueda es parcial, por nombre o documento,
    sin distinguir mayúsculas (casefold también funciona con tildes y ñ)."""
    conexion.create_function("minusculas", 1, lambda texto: texto.casefold())
    sql = "SELECT id_usuario, nombre, documento, correo FROM usuarios"
    parametros = []
    if busqueda:
        sql += " WHERE instr(minusculas(nombre), ?) > 0 OR instr(minusculas(documento), ?) > 0"
        parametros = [busqueda.casefold(), busqueda.casefold()]
    sql += " ORDER BY minusculas(nombre), id_usuario"
    return conexion.execute(sql, parametros).fetchall()


def contar_celdas(conexion):
    return conexion.execute("SELECT COUNT(*) FROM celdas").fetchone()[0]


def consultar_celdas(conexion, tipo_vehiculo=""):
    """Lista las celdas por id. Si se indica un tipo de vehículo, solo las compatibles."""
    sql = "SELECT id_celda, ubicacion, estado, tipo_vehiculo FROM celdas"
    parametros = []
    if tipo_vehiculo:
        sql += " WHERE tipo_vehiculo = ?"
        parametros.append(tipo_vehiculo)
    sql += " ORDER BY id_celda"
    return conexion.execute(sql, parametros).fetchall()


def crear_celda(conexion, ubicacion, tipo_vehiculo, estado="Disponible"):
    cursor = conexion.execute(
        "INSERT INTO celdas (ubicacion, estado, tipo_vehiculo) VALUES (?, ?, ?)",
        (ubicacion, estado, tipo_vehiculo),
    )
    return cursor.lastrowid


def buscar_celda(conexion, id_celda):
    return conexion.execute(
        "SELECT id_celda, ubicacion, estado, tipo_vehiculo FROM celdas WHERE id_celda = ?",
        (id_celda,),
    ).fetchone()


def cambiar_estado_celda(conexion, id_celda, estado_actual, estado_nuevo):
    """Cambia el estado solo si la celda sigue en el estado esperado.
    Devuelve True si se actualizó exactamente una celda."""
    cursor = conexion.execute(
        "UPDATE celdas SET estado = ? WHERE id_celda = ? AND estado = ?",
        (estado_nuevo, id_celda, estado_actual),
    )
    return cursor.rowcount == 1


def listar_vehiculos_sin_celda(conexion):
    """Vehículos que están dentro del parqueadero y todavía no tienen celda asignada."""
    return conexion.execute(
        "SELECT v.placa, v.tipo_vehiculo, m.id_movimiento "
        "FROM movimientos m JOIN vehiculos v ON v.id = m.vehiculo_id "
        "WHERE m.fecha_hora_salida IS NULL AND m.id_celda IS NULL "
        "ORDER BY v.placa"
    ).fetchall()


def asignar_celda_a_movimiento(conexion, id_movimiento, vehiculo_id, id_celda):
    """Asigna la celda solo si el movimiento es del vehículo, sigue activo y no tiene celda.
    Devuelve True si se actualizó exactamente un movimiento."""
    cursor = conexion.execute(
        "UPDATE movimientos SET id_celda = ? "
        "WHERE id_movimiento = ? AND vehiculo_id = ? "
        "AND fecha_hora_salida IS NULL AND id_celda IS NULL",
        (id_celda, id_movimiento, vehiculo_id),
    )
    return cursor.rowcount == 1


def buscar_vehiculo_por_placa(conexion, placa):
    return conexion.execute(
        "SELECT id, placa, tipo_vehiculo FROM vehiculos WHERE placa = ?", (placa,)
    ).fetchone()


def crear_vehiculo(conexion, placa, tipo):
    cursor = conexion.execute(
        "INSERT INTO vehiculos (placa, tipo_vehiculo) VALUES (?, ?)", (placa, tipo)
    )
    return cursor.lastrowid


def vehiculo_esta_dentro(conexion, vehiculo_id):
    fila = conexion.execute(
        "SELECT id_movimiento FROM movimientos "
        "WHERE vehiculo_id = ? AND fecha_hora_salida IS NULL",
        (vehiculo_id,),
    ).fetchone()
    return fila is not None


def crear_movimiento_entrada(conexion, vehiculo_id, fecha_entrada):
    conexion.execute(
        "INSERT INTO movimientos (vehiculo_id, fecha_hora_entrada) VALUES (?, ?)",
        (vehiculo_id, fecha_entrada),
    )


def buscar_movimiento_activo(conexion, vehiculo_id):
    return conexion.execute(
        "SELECT id_movimiento, fecha_hora_entrada, id_celda FROM movimientos "
        "WHERE vehiculo_id = ? AND fecha_hora_salida IS NULL",
        (vehiculo_id,),
    ).fetchone()


def buscar_movimiento(conexion, movimiento_id):
    return conexion.execute(
        "SELECT id_movimiento, vehiculo_id, fecha_hora_entrada, fecha_hora_salida, id_celda "
        "FROM movimientos WHERE id_movimiento = ?",
        (movimiento_id,),
    ).fetchone()


def contar_movimientos(conexion):
    return conexion.execute("SELECT COUNT(*) FROM movimientos").fetchone()[0]


def consultar_movimientos(conexion, placa="", estado="todos"):
    """Lista movimientos con su vehículo, del más reciente al más antiguo.
    La placa puede ser parcial (placa ya en mayúsculas); estado: todos, dentro o salio."""
    sql = (
        "SELECT m.id_movimiento, v.placa, v.tipo_vehiculo, "
        "m.fecha_hora_entrada, m.fecha_hora_salida "
        "FROM movimientos m JOIN vehiculos v ON v.id = m.vehiculo_id WHERE 1 = 1"
    )
    parametros = []
    if placa:
        sql += " AND instr(v.placa, ?) > 0"
        parametros.append(placa)
    if estado == "dentro":
        sql += " AND m.fecha_hora_salida IS NULL"
    elif estado == "salio":
        sql += " AND m.fecha_hora_salida IS NOT NULL"
    sql += " ORDER BY m.fecha_hora_entrada DESC, m.id_movimiento DESC"
    return conexion.execute(sql, parametros).fetchall()


def registrar_fecha_salida(conexion, movimiento_id, vehiculo_id, fecha_salida):
    """Cierra el movimiento solo si es del vehículo indicado y sigue activo.
    Devuelve True si se actualizó exactamente un registro."""
    cursor = conexion.execute(
        "UPDATE movimientos SET fecha_hora_salida = ? "
        "WHERE id_movimiento = ? AND vehiculo_id = ? AND fecha_hora_salida IS NULL",
        (fecha_salida, movimiento_id, vehiculo_id),
    )
    return cursor.rowcount == 1

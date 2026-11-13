import atexit
import os
import shutil
import sqlite3
import tempfile
import unittest

# Debe configurarse antes de importar app para no crear la base de datos real
_carpeta_inicial = tempfile.mkdtemp()
atexit.register(shutil.rmtree, _carpeta_inicial, ignore_errors=True)
os.environ["BASE_DE_DATOS"] = os.path.join(_carpeta_inicial, "inicial.db")

import app as aplicacion
import database


class PruebasRegistroEntrada(unittest.TestCase):
    def setUp(self):
        # Base de datos temporal: no se tocan los datos reales
        self.carpeta = tempfile.TemporaryDirectory()
        self.ruta_bd = os.path.join(self.carpeta.name, "prueba.db")
        aplicacion.app.config["BASE_DE_DATOS"] = self.ruta_bd
        database.crear_tablas(self.ruta_bd)
        self.cliente = aplicacion.app.test_client()

    def tearDown(self):
        self.carpeta.cleanup()

    def registrar(self, placa, tipo):
        return self.cliente.post(
            "/entrada",
            data={"placa": placa, "tipo_vehiculo": tipo},
            follow_redirects=True,
        )

    def consultar(self, sql):
        conexion = database.conectar(self.ruta_bd)
        filas = conexion.execute(sql).fetchall()
        conexion.close()
        return filas

    def test_registrar_automovil_nuevo(self):
        respuesta = self.registrar("ABC123", "Automóvil")
        self.assertIn("Entrada registrada correctamente", respuesta.get_data(as_text=True))
        vehiculos = self.consultar("SELECT placa, tipo_vehiculo FROM vehiculos")
        self.assertEqual([tuple(v) for v in vehiculos], [("ABC123", "Automóvil")])
        movimientos = self.consultar(
            "SELECT fecha_hora_entrada, fecha_hora_salida FROM movimientos"
        )
        self.assertEqual(len(movimientos), 1)
        self.assertIsNotNone(movimientos[0]["fecha_hora_entrada"])
        self.assertIsNone(movimientos[0]["fecha_hora_salida"])

    def test_registrar_motocicleta_nueva(self):
        respuesta = self.registrar("XYZ98A", "Motocicleta")
        self.assertIn("Entrada registrada correctamente", respuesta.get_data(as_text=True))
        vehiculos = self.consultar("SELECT placa, tipo_vehiculo FROM vehiculos")
        self.assertEqual([tuple(v) for v in vehiculos], [("XYZ98A", "Motocicleta")])

    def test_entrada_sin_placa(self):
        respuesta = self.registrar("   ", "Automóvil")
        self.assertIn("La placa del vehículo es obligatoria", respuesta.get_data(as_text=True))
        self.assertEqual(self.consultar("SELECT id_movimiento FROM movimientos"), [])

    def test_entrada_sin_tipo(self):
        respuesta = self.registrar("ABC123", "")
        self.assertIn("Debe seleccionar el tipo de vehículo", respuesta.get_data(as_text=True))
        self.assertEqual(self.consultar("SELECT id FROM vehiculos"), [])

    def test_tipo_invalido(self):
        respuesta = self.registrar("ABC123", "Camión")
        self.assertIn("no es válido", respuesta.get_data(as_text=True))
        self.assertEqual(self.consultar("SELECT id FROM vehiculos"), [])

    def test_no_permite_dos_entradas_activas(self):
        self.registrar("ABC123", "Automóvil")
        respuesta = self.registrar("ABC123", "Automóvil")
        self.assertIn("ya se encuentra dentro del parqueadero", respuesta.get_data(as_text=True))
        self.assertEqual(len(self.consultar("SELECT id_movimiento FROM movimientos")), 1)

    def test_placa_se_guarda_en_mayusculas_sin_espacios(self):
        self.registrar("  abc123  ", "Automóvil")
        vehiculos = self.consultar("SELECT placa FROM vehiculos")
        self.assertEqual([v["placa"] for v in vehiculos], ["ABC123"])

    def test_placa_existente_con_otro_tipo(self):
        self.registrar("ABC123", "Automóvil")
        respuesta = self.registrar("abc123", "Motocicleta")
        self.assertIn("ya está registrada como Automóvil", respuesta.get_data(as_text=True))
        vehiculos = self.consultar("SELECT tipo_vehiculo FROM vehiculos")
        self.assertEqual([v["tipo_vehiculo"] for v in vehiculos], ["Automóvil"])
        self.assertEqual(len(self.consultar("SELECT id_movimiento FROM movimientos")), 1)

    def test_reutiliza_vehiculo_si_ya_salio(self):
        self.registrar("ABC123", "Automóvil")
        conexion = database.conectar(self.ruta_bd)
        with conexion:
            conexion.execute("UPDATE movimientos SET fecha_hora_salida = '2026-01-01 10:00:00'")
        conexion.close()
        respuesta = self.registrar("ABC123", "Automóvil")
        self.assertIn("Entrada registrada correctamente", respuesta.get_data(as_text=True))
        self.assertEqual(len(self.consultar("SELECT id FROM vehiculos")), 1)
        self.assertEqual(len(self.consultar("SELECT id_movimiento FROM movimientos")), 2)

    def test_datos_persisten_al_reiniciar(self):
        self.registrar("ABC123", "Automóvil")
        database.crear_tablas(self.ruta_bd)
        self.assertEqual(len(self.consultar("SELECT id FROM vehiculos")), 1)
        self.assertEqual(len(self.consultar("SELECT id_movimiento FROM movimientos")), 1)

    def test_base_de_datos_con_nombres_antiguos_se_actualiza_sin_perder_datos(self):
        ruta_antigua = os.path.join(self.carpeta.name, "antigua.db")
        conexion = database.conectar(ruta_antigua)
        with conexion:
            conexion.execute(
                "CREATE TABLE vehiculos (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "placa TEXT NOT NULL UNIQUE, tipo TEXT NOT NULL)"
            )
            conexion.execute(
                "CREATE TABLE movimientos (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "vehiculo_id INTEGER NOT NULL, fecha_entrada TEXT NOT NULL, fecha_salida TEXT, "
                "FOREIGN KEY (vehiculo_id) REFERENCES vehiculos (id))"
            )
            conexion.execute(
                "CREATE UNIQUE INDEX indice_entrada_activa "
                "ON movimientos (vehiculo_id) WHERE fecha_salida IS NULL"
            )
            conexion.execute("INSERT INTO vehiculos (placa, tipo) VALUES ('ABC123', 'Automóvil')")
            conexion.execute(
                "INSERT INTO movimientos (vehiculo_id, fecha_entrada, fecha_salida) "
                "VALUES (1, '2026-01-01 08:00:00', '2026-01-01 10:00:00')"
            )
            conexion.execute(
                "INSERT INTO movimientos (vehiculo_id, fecha_entrada) VALUES (1, '2026-01-02 08:00:00')"
            )
        conexion.close()

        database.crear_tablas(ruta_antigua)
        database.crear_tablas(ruta_antigua)  # repetirlo no debe causar errores

        conexion = database.conectar(ruta_antigua)
        vehiculos = [tuple(f) for f in conexion.execute("SELECT placa, tipo_vehiculo FROM vehiculos")]
        movimientos = [
            tuple(f)
            for f in conexion.execute(
                "SELECT id_movimiento, fecha_hora_entrada, fecha_hora_salida FROM movimientos "
                "ORDER BY id_movimiento"
            )
        ]
        # El índice que impide dos entradas activas sigue funcionando tras renombrar
        with self.assertRaises(sqlite3.IntegrityError):
            with conexion:
                conexion.execute(
                    "INSERT INTO movimientos (vehiculo_id, fecha_hora_entrada) "
                    "VALUES (1, '2026-01-03 08:00:00')"
                )
        conexion.close()
        self.assertEqual(vehiculos, [("ABC123", "Automóvil")])
        self.assertEqual(
            movimientos,
            [
                (1, "2026-01-01 08:00:00", "2026-01-01 10:00:00"),
                (2, "2026-01-02 08:00:00", None),
            ],
        )

    def test_claves_foraneas_activas(self):
        conexion = database.conectar(self.ruta_bd)
        self.assertEqual(conexion.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        conexion.close()


if __name__ == "__main__":
    unittest.main()

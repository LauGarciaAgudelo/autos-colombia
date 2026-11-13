import atexit
import os
import shutil
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
        vehiculos = self.consultar("SELECT placa, tipo FROM vehiculos")
        self.assertEqual([tuple(v) for v in vehiculos], [("ABC123", "Automóvil")])
        movimientos = self.consultar("SELECT fecha_entrada, fecha_salida FROM movimientos")
        self.assertEqual(len(movimientos), 1)
        self.assertIsNotNone(movimientos[0]["fecha_entrada"])
        self.assertIsNone(movimientos[0]["fecha_salida"])

    def test_registrar_motocicleta_nueva(self):
        respuesta = self.registrar("XYZ98A", "Motocicleta")
        self.assertIn("Entrada registrada correctamente", respuesta.get_data(as_text=True))
        vehiculos = self.consultar("SELECT placa, tipo FROM vehiculos")
        self.assertEqual([tuple(v) for v in vehiculos], [("XYZ98A", "Motocicleta")])

    def test_entrada_sin_placa(self):
        respuesta = self.registrar("   ", "Automóvil")
        self.assertIn("La placa del vehículo es obligatoria", respuesta.get_data(as_text=True))
        self.assertEqual(self.consultar("SELECT id FROM movimientos"), [])

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
        self.assertEqual(len(self.consultar("SELECT id FROM movimientos")), 1)

    def test_placa_se_guarda_en_mayusculas_sin_espacios(self):
        self.registrar("  abc123  ", "Automóvil")
        vehiculos = self.consultar("SELECT placa FROM vehiculos")
        self.assertEqual([v["placa"] for v in vehiculos], ["ABC123"])

    def test_placa_existente_con_otro_tipo(self):
        self.registrar("ABC123", "Automóvil")
        respuesta = self.registrar("abc123", "Motocicleta")
        self.assertIn("ya está registrada como Automóvil", respuesta.get_data(as_text=True))
        vehiculos = self.consultar("SELECT tipo FROM vehiculos")
        self.assertEqual([v["tipo"] for v in vehiculos], ["Automóvil"])
        self.assertEqual(len(self.consultar("SELECT id FROM movimientos")), 1)

    def test_reutiliza_vehiculo_si_ya_salio(self):
        self.registrar("ABC123", "Automóvil")
        conexion = database.conectar(self.ruta_bd)
        with conexion:
            conexion.execute("UPDATE movimientos SET fecha_salida = '2026-01-01 10:00:00'")
        conexion.close()
        respuesta = self.registrar("ABC123", "Automóvil")
        self.assertIn("Entrada registrada correctamente", respuesta.get_data(as_text=True))
        self.assertEqual(len(self.consultar("SELECT id FROM vehiculos")), 1)
        self.assertEqual(len(self.consultar("SELECT id FROM movimientos")), 2)

    def test_datos_persisten_al_reiniciar(self):
        self.registrar("ABC123", "Automóvil")
        database.crear_tablas(self.ruta_bd)
        self.assertEqual(len(self.consultar("SELECT id FROM vehiculos")), 1)
        self.assertEqual(len(self.consultar("SELECT id FROM movimientos")), 1)

    def test_claves_foraneas_activas(self):
        conexion = database.conectar(self.ruta_bd)
        self.assertEqual(conexion.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        conexion.close()


if __name__ == "__main__":
    unittest.main()

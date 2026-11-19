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


class PruebasRegistroSalida(unittest.TestCase):
    def setUp(self):
        # Base de datos temporal: no se tocan los datos reales
        self.carpeta = tempfile.TemporaryDirectory()
        self.ruta_bd = os.path.join(self.carpeta.name, "prueba.db")
        aplicacion.app.config["BASE_DE_DATOS"] = self.ruta_bd
        database.crear_tablas(self.ruta_bd)
        self.cliente = aplicacion.app.test_client()

    def tearDown(self):
        self.carpeta.cleanup()

    def registrar_entrada(self, placa, tipo="Automóvil"):
        return self.cliente.post(
            "/entrada", data={"placa": placa, "tipo_vehiculo": tipo}, follow_redirects=True
        )

    def buscar(self, placa):
        return self.cliente.post("/salida", data={"placa": placa, "accion": "buscar"})

    def registrar_salida(self, placa, movimiento_id):
        return self.cliente.post(
            "/salida",
            data={"placa": placa, "movimiento_id": movimiento_id, "accion": "registrar"},
            follow_redirects=True,
        )

    def consultar(self, sql, parametros=()):
        conexion = database.conectar(self.ruta_bd)
        filas = conexion.execute(sql, parametros).fetchall()
        conexion.close()
        return filas

    def movimientos_de(self, placa):
        return self.consultar(
            "SELECT m.id_movimiento AS id, m.fecha_hora_entrada AS fecha_entrada, "
            "m.fecha_hora_salida AS fecha_salida FROM movimientos m "
            "JOIN vehiculos v ON v.id = m.vehiculo_id WHERE v.placa = ? ORDER BY m.id_movimiento",
            (placa,),
        )

    def id_movimiento_activo(self, placa):
        activos = [m for m in self.movimientos_de(placa) if m["fecha_salida"] is None]
        return activos[0]["id"]

    def test_buscar_vehiculo_con_entrada_activa(self):
        self.registrar_entrada("ABC123", "Motocicleta")
        respuesta = self.buscar("  abc123 ").get_data(as_text=True)
        self.assertIn("Placa: ABC123", respuesta)
        self.assertIn("Tipo: Motocicleta", respuesta)
        fecha_bd = self.movimientos_de("ABC123")[0]["fecha_entrada"]
        fecha_pantalla = aplicacion.formatear_fecha(fecha_bd)
        self.assertIn(fecha_pantalla, respuesta)
        self.assertIn('name="movimiento_id"', respuesta)
        self.assertNotIn("disabled>Registrar salida", respuesta)

    def test_buscar_vehiculo_inexistente(self):
        respuesta = self.buscar("ZZZ999").get_data(as_text=True)
        self.assertIn("No existe un vehículo registrado con la placa ZZZ999", respuesta)
        self.assertNotIn('name="movimiento_id"', respuesta)
        self.assertIn("disabled", respuesta)

    def test_buscar_vehiculo_que_ya_salio(self):
        self.registrar_entrada("ABC123")
        self.registrar_salida("ABC123", self.id_movimiento_activo("ABC123"))
        respuesta = self.buscar("ABC123").get_data(as_text=True)
        self.assertIn("no tiene una entrada activa", respuesta)
        self.assertNotIn('name="movimiento_id"', respuesta)

    def test_buscar_sin_placa(self):
        respuesta = self.buscar("   ").get_data(as_text=True)
        self.assertIn("La placa del vehículo es obligatoria", respuesta)

    def test_registrar_salida_correctamente(self):
        self.registrar_entrada("ABC123")
        respuesta = self.registrar_salida("ABC123", self.id_movimiento_activo("ABC123"))
        texto = respuesta.get_data(as_text=True)
        self.assertIn("Salida registrada correctamente: ABC123", texto)
        # Después de la salida el formulario queda vacío y sin permitir otro registro
        self.assertNotIn('name="movimiento_id"', texto)
        self.assertIn("disabled", texto)

    def test_se_guarda_la_fecha_de_salida(self):
        self.registrar_entrada("ABC123")
        self.registrar_salida("ABC123", self.id_movimiento_activo("ABC123"))
        movimiento = self.movimientos_de("ABC123")[0]
        self.assertIsNotNone(movimiento["fecha_salida"])
        self.assertGreaterEqual(movimiento["fecha_salida"], movimiento["fecha_entrada"])

    def test_no_permite_cerrar_dos_veces_el_mismo_movimiento(self):
        self.registrar_entrada("ABC123")
        movimiento_id = self.id_movimiento_activo("ABC123")
        self.registrar_salida("ABC123", movimiento_id)
        salida_original = self.movimientos_de("ABC123")[0]["fecha_salida"]

        respuesta = self.registrar_salida("ABC123", movimiento_id)
        self.assertIn("ya fue registrada", respuesta.get_data(as_text=True))
        self.assertEqual(self.movimientos_de("ABC123")[0]["fecha_salida"], salida_original)

    def test_registrar_fecha_salida_no_actualiza_un_movimiento_cerrado(self):
        self.registrar_entrada("ABC123")
        movimiento_id = self.id_movimiento_activo("ABC123")
        vehiculo_id = self.consultar("SELECT id FROM vehiculos")[0]["id"]
        conexion = database.conectar(self.ruta_bd)
        with conexion:
            primera = database.registrar_fecha_salida(
                conexion, movimiento_id, vehiculo_id, "2026-01-01 10:00:00"
            )
            segunda = database.registrar_fecha_salida(
                conexion, movimiento_id, vehiculo_id, "2026-02-02 10:00:00"
            )
        conexion.close()
        self.assertTrue(primera)
        self.assertFalse(segunda)
        self.assertEqual(self.movimientos_de("ABC123")[0]["fecha_salida"], "2026-01-01 10:00:00")

    def test_vehiculo_puede_volver_a_ingresar_despues_de_salir(self):
        self.registrar_entrada("ABC123")
        self.registrar_salida("ABC123", self.id_movimiento_activo("ABC123"))
        respuesta = self.registrar_entrada("ABC123")
        self.assertIn("Entrada registrada correctamente", respuesta.get_data(as_text=True))
        movimientos = self.movimientos_de("ABC123")
        self.assertEqual(len(movimientos), 2)
        self.assertIsNone(movimientos[1]["fecha_salida"])

    def test_la_salida_de_un_vehiculo_no_afecta_a_otro(self):
        self.registrar_entrada("ABC123")
        self.registrar_entrada("XYZ98A", "Motocicleta")
        self.registrar_salida("ABC123", self.id_movimiento_activo("ABC123"))
        self.assertIsNotNone(self.movimientos_de("ABC123")[0]["fecha_salida"])
        self.assertIsNone(self.movimientos_de("XYZ98A")[0]["fecha_salida"])

    def test_no_permite_cerrar_un_movimiento_de_otra_placa(self):
        self.registrar_entrada("ABC123")
        self.registrar_entrada("XYZ98A", "Motocicleta")
        movimiento_ajeno = self.id_movimiento_activo("XYZ98A")

        respuesta = self.registrar_salida("ABC123", movimiento_ajeno)
        self.assertIn("no corresponde a la placa ABC123", respuesta.get_data(as_text=True))
        self.assertIsNone(self.movimientos_de("ABC123")[0]["fecha_salida"])
        self.assertIsNone(self.movimientos_de("XYZ98A")[0]["fecha_salida"])

    def test_no_permite_registrar_salida_sin_consultar_o_con_datos_invalidos(self):
        self.registrar_entrada("ABC123")
        for movimiento_id in ["", "abc", "9999"]:
            respuesta = self.registrar_salida("ABC123", movimiento_id)
            self.assertNotIn("Salida registrada correctamente", respuesta.get_data(as_text=True))
        respuesta = self.registrar_salida("NOEXISTE", self.id_movimiento_activo("ABC123"))
        self.assertIn("No existe un vehículo registrado", respuesta.get_data(as_text=True))
        self.assertIsNone(self.movimientos_de("ABC123")[0]["fecha_salida"])

    def test_movimientos_anteriores_permanecen_guardados(self):
        self.registrar_entrada("ABC123")
        self.registrar_salida("ABC123", self.id_movimiento_activo("ABC123"))
        primero = self.movimientos_de("ABC123")[0]
        self.registrar_entrada("ABC123")
        self.registrar_salida("ABC123", self.id_movimiento_activo("ABC123"))

        movimientos = self.movimientos_de("ABC123")
        self.assertEqual(len(movimientos), 2)
        self.assertEqual(tuple(movimientos[0]), tuple(primero))
        self.assertEqual(len(self.consultar("SELECT id FROM vehiculos")), 1)


if __name__ == "__main__":
    unittest.main()

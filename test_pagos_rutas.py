import atexit
import os
import shutil
import tempfile
import unittest
from contextlib import closing

_carpeta_inicial = tempfile.mkdtemp()
atexit.register(shutil.rmtree, _carpeta_inicial, ignore_errors=True)
os.environ["BASE_DE_DATOS"] = os.path.join(_carpeta_inicial, "inicial.db")

import app as aplicacion
import database


class PruebasRutasPagos(unittest.TestCase):
    def setUp(self):
        self.carpeta = tempfile.TemporaryDirectory()
        self.ruta_bd = os.path.join(self.carpeta.name, "pagos.db")
        aplicacion.app.config["BASE_DE_DATOS"] = self.ruta_bd
        database.crear_tablas(self.ruta_bd)
        self.cliente = aplicacion.app.test_client()

    def tearDown(self):
        self.carpeta.cleanup()

    def registrar(self, placa, valor=120000, fecha_pago="2026-11-18", periodo="2026-11"):
        return self.cliente.post(
            "/pagos/registrar",
            data={
                "placa": placa,
                "valor": str(valor),
                "fecha_pago": fecha_pago,
                "periodo": periodo,
            },
            follow_redirects=True,
        )

    def crear_vehiculo(self, placa):
        with closing(database.conectar(self.ruta_bd)) as conexion:
            with conexion:
                return database.crear_vehiculo(conexion, placa, "Automóvil")

    def crear_pago(self, vehiculo_id, valor, fecha_pago, periodo):
        with closing(database.conectar(self.ruta_bd)) as conexion:
            with conexion:
                return database.crear_pago(
                    conexion, vehiculo_id, valor, fecha_pago, periodo
                )

    def consultar_bd(self, sql, parametros=()):
        with closing(database.conectar(self.ruta_bd)) as conexion:
            return conexion.execute(sql, parametros).fetchall()

    def test_pantallas_de_registro_y_consulta_se_muestran(self):
        registro = self.cliente.get("/pagos/registrar")
        consulta = self.cliente.get("/pagos")

        self.assertEqual(registro.status_code, 200)
        self.assertIn('name="fecha_pago"', registro.get_data(as_text=True))
        self.assertIn('name="periodo"', registro.get_data(as_text=True))
        self.assertEqual(consulta.status_code, 200)
        self.assertIn("Consultar pagos", consulta.get_data(as_text=True))

    def test_registra_pago_valido(self):
        vehiculo_id = self.crear_vehiculo("ABC123")

        respuesta = self.registrar("abc123")

        self.assertIn(
            "Pago registrado correctamente", respuesta.get_data(as_text=True)
        )
        pagos = self.consultar_bd(
            "SELECT vehiculo_id, valor, fecha_pago, periodo FROM pagos"
        )
        self.assertEqual(
            [tuple(fila) for fila in pagos],
            [(vehiculo_id, 120000, "2026-11-18", "2026-11")],
        )

    def test_rechaza_registro_para_vehiculo_inexistente(self):
        respuesta = self.registrar("ZZZ999")

        self.assertIn(
            "No existe un vehículo registrado con la placa ZZZ999",
            respuesta.get_data(as_text=True),
        )
        self.assertEqual(self.consultar_bd("SELECT id_pago FROM pagos"), [])

    def test_rechaza_pago_duplicado_del_mismo_periodo(self):
        self.crear_vehiculo("ABC123")
        self.registrar("ABC123")

        respuesta = self.registrar("ABC123")

        self.assertIn(
            "Ya existe un pago registrado", respuesta.get_data(as_text=True)
        )
        self.assertEqual(
            len(self.consultar_bd("SELECT id_pago FROM pagos")), 1
        )

    def test_valida_campos_obligatorios_y_valor_positivo_entero(self):
        self.crear_vehiculo("ABC123")

        respuesta = self.cliente.post(
            "/pagos/registrar",
            data={"placa": "", "valor": "", "fecha_pago": "", "periodo": ""},
        )
        html = respuesta.get_data(as_text=True)
        self.assertIn("La placa del vehículo es obligatoria", html)
        self.assertIn("El valor del pago es obligatorio", html)
        self.assertIn("La fecha de pago es obligatoria", html)
        self.assertIn("El período que se paga es obligatorio", html)

        for valor, mensaje in (
            ("0", "mayor que cero"),
            ("-1", "mayor que cero"),
            ("1000.50", "número entero"),
        ):
            with self.subTest(valor=valor):
                respuesta = self.registrar("ABC123", valor=valor)
                self.assertIn(mensaje, respuesta.get_data(as_text=True))

        self.assertEqual(self.consultar_bd("SELECT id_pago FROM pagos"), [])

    def test_valida_formatos_de_fecha_y_periodo(self):
        self.crear_vehiculo("ABC123")

        for fecha_pago, periodo, mensaje in (
            ("2026-02-30", "2026-11", "fecha de pago"),
            ("2026-11-18", "2026-13", "período"),
        ):
            with self.subTest(fecha_pago=fecha_pago, periodo=periodo):
                respuesta = self.registrar(
                    "ABC123", fecha_pago=fecha_pago, periodo=periodo
                )
                self.assertIn(mensaje, respuesta.get_data(as_text=True))

        self.assertEqual(self.consultar_bd("SELECT id_pago FROM pagos"), [])

    def test_consulta_muestra_los_pagos_del_vehiculo_en_formato_legible(self):
        vehiculo_id = self.crear_vehiculo("ABC123")
        otro_vehiculo_id = self.crear_vehiculo("XYZ789")
        self.crear_pago(vehiculo_id, 150000, "2026-10-05", "2026-10")
        self.crear_pago(vehiculo_id, 213000, "2026-11-05", "2026-11")
        self.crear_pago(otro_vehiculo_id, 999000, "2026-11-05", "2026-11")

        respuesta = self.cliente.get(
            "/pagos", query_string={"placa": " abc123 "}
        )
        html = respuesta.get_data(as_text=True)

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Octubre 2026", html)
        self.assertIn("Noviembre 2026", html)
        self.assertIn("05/10/2026", html)
        self.assertIn("$150.000", html)
        self.assertIn("$213.000", html)
        self.assertNotIn("$999.000", html)

    def test_consulta_vehiculo_registrado_sin_pagos(self):
        self.crear_vehiculo("ABC123")

        respuesta = self.cliente.get("/pagos?placa=ABC123")

        self.assertIn(
            "No hay pagos registrados para el vehículo ABC123",
            respuesta.get_data(as_text=True),
        )

    def test_consulta_vehiculo_inexistente(self):
        respuesta = self.cliente.get("/pagos?placa=ZZZ999")

        self.assertIn(
            "No existe un vehículo registrado con la placa ZZZ999",
            respuesta.get_data(as_text=True),
        )


if __name__ == "__main__":
    unittest.main()

import atexit
import os
import re
import shutil
import tempfile
import unittest

# Debe configurarse antes de importar app para no crear la base de datos real
_carpeta_inicial = tempfile.mkdtemp()
atexit.register(shutil.rmtree, _carpeta_inicial, ignore_errors=True)
os.environ["BASE_DE_DATOS"] = os.path.join(_carpeta_inicial, "inicial.db")

import app as aplicacion
import database

SIN_MOVIMIENTOS = "No hay movimientos registrados en el parqueadero"
SIN_COINCIDENCIAS = "No se encontraron movimientos con los filtros seleccionados"


class PruebasHistorial(unittest.TestCase):
    def setUp(self):
        # Base de datos temporal: no se tocan los datos reales
        self.carpeta = tempfile.TemporaryDirectory()
        self.ruta_bd = os.path.join(self.carpeta.name, "prueba.db")
        aplicacion.app.config["BASE_DE_DATOS"] = self.ruta_bd
        database.crear_tablas(self.ruta_bd)
        self.cliente = aplicacion.app.test_client()

    def tearDown(self):
        self.carpeta.cleanup()

    def insertar(self, placa, tipo, fecha_entrada, fecha_salida=None):
        """Inserta un movimiento con fechas conocidas para controlar el orden."""
        conexion = database.conectar(self.ruta_bd)
        with conexion:
            vehiculo = database.buscar_vehiculo_por_placa(conexion, placa)
            vehiculo_id = vehiculo["id"] if vehiculo else database.crear_vehiculo(conexion, placa, tipo)
            conexion.execute(
                "INSERT INTO movimientos (vehiculo_id, fecha_hora_entrada, fecha_hora_salida) "
                "VALUES (?, ?, ?)",
                (vehiculo_id, fecha_entrada, fecha_salida),
            )
        conexion.close()

    def datos_de_prueba(self):
        self.insertar("ABC123", "Automóvil", "2026-01-01 08:00:00", "2026-01-01 10:00:00")
        self.insertar("ABC123", "Automóvil", "2026-01-02 08:00:00")
        self.insertar("XYZ98A", "Motocicleta", "2026-01-03 09:00:00", "2026-01-03 11:00:00")
        self.insertar("ABD777", "Automóvil", "2026-01-04 07:00:00")

    def pedir(self, **parametros):
        return self.cliente.get("/historial", query_string=parametros).get_data(as_text=True)

    def filas(self, html):
        """Devuelve las filas de la tabla como listas de celdas."""
        cuerpo = html.split("<tbody>")[1].split("</tbody>")[0] if "<tbody>" in html else ""
        return [
            re.findall(r"<td>(.*?)</td>", fila)
            for fila in re.findall(r"<tr>(.*?)</tr>", cuerpo, re.S)
        ]

    def placas(self, html):
        return [fila[0] for fila in self.filas(html)]

    def contenido_bd(self):
        conexion = database.conectar(self.ruta_bd)
        datos = (
            [tuple(f) for f in conexion.execute("SELECT * FROM vehiculos ORDER BY id")],
            [tuple(f) for f in conexion.execute("SELECT * FROM movimientos ORDER BY id_movimiento")],
        )
        conexion.close()
        return datos

    def test_historial_sin_registros(self):
        respuesta = self.cliente.get("/historial")
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.get_data(as_text=True)
        self.assertIn(SIN_MOVIMIENTOS, html)
        self.assertNotIn("<tbody>", html)

    def test_historial_con_entradas_activas(self):
        self.cliente.post("/entrada", data={"placa": "abc123", "tipo_vehiculo": "Automóvil"})
        html = self.pedir()
        filas = self.filas(html)
        self.assertEqual(len(filas), 1)
        placa, tipo, entrada, salida, estado = filas[0]
        self.assertEqual((placa, tipo, salida, estado), ("ABC123", "Automóvil", "-", "Dentro"))
        self.assertRegex(entrada, r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}$")

    def test_historial_con_salidas_registradas(self):
        self.cliente.post("/entrada", data={"placa": "ABC123", "tipo_vehiculo": "Automóvil"})
        movimiento_id = database.conectar(self.ruta_bd).execute("SELECT id_movimiento FROM movimientos").fetchone()[0]
        self.cliente.post(
            "/salida", data={"placa": "ABC123", "movimiento_id": movimiento_id, "accion": "registrar"}
        )
        filas = self.filas(self.pedir())
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0][4], "Salió")
        self.assertRegex(filas[0][3], r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}$")

    def test_estado_dentro_y_salio_en_la_tabla(self):
        self.datos_de_prueba()
        estados = {(f[0], f[2]): f[4] for f in self.filas(self.pedir())}
        self.assertEqual(estados[("ABC123", "01/01/2026 08:00:00")], "Salió")
        self.assertEqual(estados[("ABC123", "02/01/2026 08:00:00")], "Dentro")
        self.assertEqual(estados[("ABD777", "04/01/2026 07:00:00")], "Dentro")

    def test_vehiculo_con_varios_movimientos(self):
        self.datos_de_prueba()
        filas = self.filas(self.pedir(placa="ABC123"))
        self.assertEqual([f[0] for f in filas], ["ABC123", "ABC123"])
        self.assertEqual([f[4] for f in filas], ["Dentro", "Salió"])

    def test_filtrar_por_placa_completa(self):
        self.datos_de_prueba()
        self.assertEqual(self.placas(self.pedir(placa="XYZ98A")), ["XYZ98A"])

    def test_filtrar_por_placa_parcial_sin_importar_mayusculas_ni_espacios(self):
        self.datos_de_prueba()
        self.assertEqual(self.placas(self.pedir(placa="  ab ")), ["ABD777", "ABC123", "ABC123"])
        self.assertEqual(self.placas(self.pedir(placa="98a")), ["XYZ98A"])

    def test_la_placa_no_usa_comodines(self):
        self.datos_de_prueba()
        html = self.pedir(placa="%")
        self.assertIn(SIN_COINCIDENCIAS, html)
        self.assertIn(SIN_COINCIDENCIAS, self.pedir(placa="_"))

    def test_filtrar_por_estado_dentro(self):
        self.datos_de_prueba()
        filas = self.filas(self.pedir(estado="dentro"))
        self.assertEqual([f[0] for f in filas], ["ABD777", "ABC123"])
        self.assertTrue(all(f[4] == "Dentro" and f[3] == "-" for f in filas))

    def test_filtrar_por_estado_salio(self):
        self.datos_de_prueba()
        filas = self.filas(self.pedir(estado="salio"))
        self.assertEqual([f[0] for f in filas], ["XYZ98A", "ABC123"])
        self.assertTrue(all(f[4] == "Salió" for f in filas))

    def test_combinar_placa_y_estado(self):
        self.datos_de_prueba()
        filas = self.filas(self.pedir(placa="abc", estado="salio"))
        self.assertEqual(len(filas), 1)
        self.assertEqual((filas[0][0], filas[0][2]), ("ABC123", "01/01/2026 08:00:00"))

    def test_estado_todos_o_invalido_muestra_todo(self):
        self.datos_de_prueba()
        self.assertEqual(len(self.filas(self.pedir(estado="todos"))), 4)
        self.assertEqual(len(self.filas(self.pedir(estado="cualquiera"))), 4)

    def test_filtros_sin_resultados(self):
        self.datos_de_prueba()
        html = self.pedir(placa="NOEXISTE")
        self.assertIn(SIN_COINCIDENCIAS, html)
        self.assertNotIn(SIN_MOVIMIENTOS, html)
        self.assertIn(SIN_COINCIDENCIAS, self.pedir(placa="XYZ", estado="dentro"))

    def test_orden_mas_reciente_primero_y_por_id_si_hay_empate(self):
        self.insertar("AAA111", "Automóvil", "2026-03-01 08:00:00", "2026-03-01 09:00:00")
        self.insertar("BBB222", "Automóvil", "2026-03-05 08:00:00")
        self.insertar("CCC333", "Motocicleta", "2026-03-01 08:00:00")
        # AAA111 y CCC333 tienen la misma fecha de entrada: gana el ID mayor (CCC333)
        self.assertEqual(self.placas(self.pedir()), ["BBB222", "CCC333", "AAA111"])

    def test_consultar_historial_no_modifica_los_datos(self):
        self.datos_de_prueba()
        antes = self.contenido_bd()
        self.pedir()
        self.pedir(placa="abc", estado="dentro")
        self.pedir(placa="nada")
        self.assertEqual(self.contenido_bd(), antes)

    def test_menu_historial_habilitado(self):
        html = self.cliente.get("/").get_data(as_text=True)
        self.assertIn('href="/historial"', html)


if __name__ == "__main__":
    unittest.main()

import atexit
import os
import re
import shutil
import sqlite3
import tempfile
import unittest

# Debe configurarse antes de importar app para no crear la base de datos real
_carpeta_inicial = tempfile.mkdtemp()
atexit.register(shutil.rmtree, _carpeta_inicial, ignore_errors=True)
os.environ["BASE_DE_DATOS"] = os.path.join(_carpeta_inicial, "inicial.db")

import app as aplicacion
import cargar_celdas_demo
import database

SIN_CELDAS = "No hay celdas registradas en el parqueadero"
SIN_COMPATIBLES = "No hay celdas compatibles con este vehículo"
SIN_DISPONIBLES = "No hay celdas disponibles para este tipo de vehículo"


class PruebasCeldas(unittest.TestCase):
    def setUp(self):
        # Base de datos temporal: no se tocan los datos reales
        self.carpeta = tempfile.TemporaryDirectory()
        self.ruta_bd = os.path.join(self.carpeta.name, "prueba.db")
        aplicacion.app.config["BASE_DE_DATOS"] = self.ruta_bd
        database.crear_tablas(self.ruta_bd)
        self.cliente = aplicacion.app.test_client()

    def tearDown(self):
        self.carpeta.cleanup()

    def insertar(self, celdas):
        """celdas: lista de (ubicacion, tipo_vehiculo, estado)."""
        conexion = database.conectar(self.ruta_bd)
        with conexion:
            for ubicacion, tipo_vehiculo, estado in celdas:
                database.crear_celda(conexion, ubicacion, tipo_vehiculo, estado)
        conexion.close()

    def datos_de_prueba(self):
        self.insertar(
            [
                ("Zona A", "Automóvil", "Disponible"),
                ("Zona A", "Automóvil", "Ocupada"),
                ("Zona B", "Motocicleta", "Disponible"),
            ]
        )

    def consultar_bd(self, sql):
        conexion = database.conectar(self.ruta_bd)
        filas = [tuple(f) for f in conexion.execute(sql)]
        conexion.close()
        return filas

    def pedir(self, **parametros):
        return self.cliente.get("/celdas", query_string=parametros).get_data(as_text=True)

    def filas(self, html):
        cuerpo = html.split("<tbody>")[1].split("</tbody>")[0] if "<tbody>" in html else ""
        return [
            re.findall(r"<td[^>]*>(.*?)</td>", fila, re.S)
            for fila in re.findall(r"<tr>(.*?)</tr>", cuerpo, re.S)
        ]

    def test_consultar_celdas_sin_registros(self):
        respuesta = self.cliente.get("/celdas")
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.get_data(as_text=True)
        self.assertIn(SIN_CELDAS, html)
        self.assertNotIn("<tbody>", html)

    def test_consultar_celdas_registradas(self):
        self.datos_de_prueba()
        self.assertEqual(
            self.filas(self.pedir()),
            [["1", "Zona A", "Disponible"], ["2", "Zona A", "Ocupada"], ["3", "Zona B", "Disponible"]],
        )

    def test_se_muestran_solo_los_campos_del_mockup(self):
        self.datos_de_prueba()
        html = self.pedir()
        encabezados = re.findall(r"<th>(.*?)</th>", html)
        self.assertEqual(encabezados, ["Celda", "Ubicación", "Estado"])
        self.assertIn("Tipo de vehículo", html)  # filtro del mockup, no columna
        self.assertTrue(all(len(fila) == 3 for fila in self.filas(html)))

    def test_disponibilidad_y_colores_por_estado(self):
        self.datos_de_prueba()
        html = self.pedir()
        self.assertEqual(html.count('class="estado-disponible"'), 2)
        self.assertEqual(html.count('class="estado-ocupada"'), 1)

    def test_estados_definidos_en_el_modelo(self):
        self.insertar([("Zona A", "Automóvil", "Disponible"), ("Zona A", "Automóvil", "Ocupada")])
        conexion = database.conectar(self.ruta_bd)
        with self.assertRaises(sqlite3.IntegrityError):
            with conexion:
                database.crear_celda(conexion, "Zona X", "Automóvil", "En mantenimiento")
        conexion.close()
        estados = {f[0] for f in self.consultar_bd("SELECT estado FROM celdas")}
        self.assertEqual(estados, {"Disponible", "Ocupada"})

    def test_estado_por_defecto_es_disponible(self):
        conexion = database.conectar(self.ruta_bd)
        with conexion:
            conexion.execute("INSERT INTO celdas (ubicacion, tipo_vehiculo) VALUES ('Zona A', 'Automóvil')")
        conexion.close()
        self.assertEqual(self.consultar_bd("SELECT estado FROM celdas"), [("Disponible",)])

    def test_tipos_de_vehiculo_validos_en_celdas(self):
        conexion = database.conectar(self.ruta_bd)
        with self.assertRaises(sqlite3.IntegrityError):
            with conexion:
                database.crear_celda(conexion, "Zona A", "Camión")
        conexion.close()

    def test_compatibilidad_automovil(self):
        self.datos_de_prueba()
        filas = self.filas(self.pedir(tipo="Automóvil"))
        self.assertEqual(filas, [["1", "Zona A", "Disponible"], ["2", "Zona A", "Ocupada"]])

    def test_compatibilidad_motocicleta(self):
        self.datos_de_prueba()
        self.assertEqual(self.filas(self.pedir(tipo="Motocicleta")), [["3", "Zona B", "Disponible"]])

    def test_filtro_muestra_celdas_disponibles_y_ocupadas_compatibles(self):
        self.datos_de_prueba()
        estados = [f[2] for f in self.filas(self.pedir(tipo="Automóvil"))]
        self.assertEqual(estados, ["Disponible", "Ocupada"])

    def test_sin_celdas_compatibles_con_el_tipo(self):
        self.insertar([("Zona A", "Automóvil", "Disponible")])
        html = self.pedir(tipo="Motocicleta")
        self.assertIn(SIN_COMPATIBLES, html)
        self.assertNotIn(SIN_CELDAS, html)
        self.assertNotIn("<tbody>", html)

    def test_compatibles_pero_ninguna_disponible(self):
        self.insertar([("Zona A", "Automóvil", "Ocupada"), ("Zona B", "Motocicleta", "Disponible")])
        html = self.pedir(tipo="Automóvil")
        self.assertIn(SIN_DISPONIBLES, html)
        self.assertEqual(self.filas(html), [["1", "Zona A", "Ocupada"]])

    def test_no_aparece_aviso_de_sin_disponibles_si_hay_disponibles(self):
        self.datos_de_prueba()
        self.assertNotIn(SIN_DISPONIBLES, self.pedir(tipo="Automóvil"))
        self.assertNotIn(SIN_DISPONIBLES, self.pedir())

    def test_tipo_invalido_en_la_url_se_ignora(self):
        self.datos_de_prueba()
        self.assertEqual(len(self.filas(self.pedir(tipo="Camión"))), 3)

    def test_consultar_celdas_no_modifica_los_registros(self):
        self.datos_de_prueba()
        antes = self.consultar_bd("SELECT * FROM celdas ORDER BY id_celda")
        self.pedir()
        self.pedir(tipo="Automóvil")
        self.pedir(tipo="Camión")
        self.assertEqual(self.consultar_bd("SELECT * FROM celdas ORDER BY id_celda"), antes)

    def test_no_se_crean_celdas_automaticamente(self):
        self.pedir()
        self.cliente.get("/")
        database.crear_tablas(self.ruta_bd)  # equivale a iniciar de nuevo la aplicación
        self.assertEqual(self.consultar_bd("SELECT COUNT(*) FROM celdas"), [(0,)])

    def test_celdas_permanecen_al_reiniciar(self):
        self.datos_de_prueba()
        database.crear_tablas(self.ruta_bd)
        self.assertEqual(len(self.filas(self.pedir())), 3)

    def test_enlace_de_navegacion_a_celdas(self):
        for ruta in ("/", "/entrada", "/salida", "/historial", "/usuarios", "/celdas"):
            html = self.cliente.get(ruta).get_data(as_text=True)
            self.assertIn('href="/celdas"', html, ruta)
        html = self.pedir()
        self.assertRegex(html, r'menu-enlace activo"\s+href="/celdas"')

    def test_menu_existente_sigue_completo(self):
        html = self.cliente.get("/celdas").get_data(as_text=True)
        for ruta in ("/", "/entrada", "/salida", "/historial", "/usuarios"):
            self.assertIn(f'href="{ruta}"', html)

    def test_pantalla_adaptable_a_distintos_tamanos(self):
        self.datos_de_prueba()
        html = self.pedir()
        self.assertIn('name="viewport" content="width=device-width, initial-scale=1"', html)
        self.assertIn("table-responsive", html)  # la tabla se desplaza sola en pantallas pequeñas
        self.assertIn("col-12 col-md-9", html)  # el formulario se apila en móvil

    def test_tablas_de_iteraciones_anteriores_no_cambian(self):
        columnas = {
            tabla: [f[1] for f in self.consultar_bd(f"PRAGMA table_info({tabla})")]
            for tabla in ("vehiculos", "movimientos", "usuarios", "celdas")
        }
        self.assertEqual(columnas["vehiculos"], ["id", "placa", "tipo_vehiculo"])
        self.assertEqual(
            columnas["movimientos"],
            [
                "id_movimiento",
                "vehiculo_id",
                "fecha_hora_entrada",
                "fecha_hora_salida",
                "id_celda",
                "id_usuario",
            ],
        )
        self.assertEqual(columnas["usuarios"], ["id_usuario", "nombre", "documento", "correo"])
        self.assertEqual(columnas["celdas"], ["id_celda", "ubicacion", "estado", "tipo_vehiculo"])

    def test_crear_tablas_no_borra_datos_existentes_de_otras_tablas(self):
        self.cliente.post("/entrada", data={"placa": "ABC123", "tipo_vehiculo": "Automóvil"})
        self.cliente.post(
            "/usuarios/registrar",
            data={"nombre": "Ana", "documento": "1", "correo": "ana@correo.com"},
        )
        self.datos_de_prueba()
        database.crear_tablas(self.ruta_bd)
        self.assertEqual(self.consultar_bd("SELECT COUNT(*) FROM vehiculos"), [(1,)])
        self.assertEqual(self.consultar_bd("SELECT COUNT(*) FROM usuarios"), [(1,)])
        self.assertEqual(self.consultar_bd("SELECT COUNT(*) FROM celdas"), [(3,)])

    def test_script_de_demostracion_solo_carga_en_la_base_indicada(self):
        ruta_demo = os.path.join(self.carpeta.name, "demo.db")
        self.assertEqual(cargar_celdas_demo.cargar_celdas_demo(ruta_demo), 4)
        self.assertEqual(cargar_celdas_demo.cargar_celdas_demo(ruta_demo), 0)  # no duplica
        conexion = database.conectar(ruta_demo)
        self.assertEqual(database.contar_celdas(conexion), 4)
        conexion.close()
        self.assertEqual(self.consultar_bd("SELECT COUNT(*) FROM celdas"), [(0,)])

    def test_script_de_demostracion_se_niega_a_escribir_en_la_base_real(self):
        # La ruta real solo se compara, nunca se abre
        real = os.path.join(os.path.dirname(os.path.abspath(cargar_celdas_demo.__file__)), "parqueadero.db")
        self.assertTrue(cargar_celdas_demo.es_base_de_datos_real(real))
        self.assertTrue(cargar_celdas_demo.es_base_de_datos_real("parqueadero.db"))
        self.assertFalse(cargar_celdas_demo.es_base_de_datos_real("parqueadero_demo.db"))
        # Un archivo con ese nombre en una carpeta temporal tampoco se toca
        falsa_real = os.path.join(self.carpeta.name, "parqueadero.db")
        with self.assertRaises(ValueError):
            cargar_celdas_demo.cargar_celdas_demo(falsa_real)
        self.assertFalse(os.path.exists(falsa_real))


if __name__ == "__main__":
    unittest.main()

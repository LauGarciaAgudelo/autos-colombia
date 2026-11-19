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
import database

CELDA_NO_VALIDA = "La celda no está disponible o no es compatible con el vehículo"
ASIGNADA = "Celda asignada correctamente"


class PruebasAsignacionDeCeldas(unittest.TestCase):
    def setUp(self):
        # Base de datos temporal: no se tocan los datos reales
        self.carpeta = tempfile.TemporaryDirectory()
        self.ruta_bd = os.path.join(self.carpeta.name, "prueba.db")
        aplicacion.app.config["BASE_DE_DATOS"] = self.ruta_bd
        database.crear_tablas(self.ruta_bd)
        self.cliente = aplicacion.app.test_client()

    def tearDown(self):
        self.carpeta.cleanup()

    # ---- ayudas ----
    def crear_celdas(self, celdas):
        """celdas: lista de (ubicacion, tipo_vehiculo, estado). Devuelve los id_celda."""
        conexion = database.conectar(self.ruta_bd)
        with conexion:
            ids = [database.crear_celda(conexion, u, t, e) for u, t, e in celdas]
        conexion.close()
        return ids

    def ingresar(self, placa, tipo="Automóvil"):
        return self.cliente.post(
            "/entrada", data={"placa": placa, "tipo_vehiculo": tipo}, follow_redirects=True
        )

    def asignar(self, placa, id_celda):
        return self.cliente.post(
            "/celdas/asignar", data={"placa": placa, "id_celda": id_celda}, follow_redirects=True
        ).get_data(as_text=True)

    def id_movimiento_activo(self, placa):
        return self.consultar(
            "SELECT m.id_movimiento FROM movimientos m JOIN vehiculos v ON v.id = m.vehiculo_id "
            "WHERE v.placa = ? AND m.fecha_hora_salida IS NULL",
            (placa,),
        )[0][0]

    def registrar_salida(self, placa, **extra):
        datos = {"placa": placa, "movimiento_id": self.id_movimiento_activo(placa), "accion": "registrar"}
        datos.update(extra)
        return self.cliente.post("/salida", data=datos, follow_redirects=True).get_data(as_text=True)

    def consultar(self, sql, parametros=()):
        conexion = database.conectar(self.ruta_bd)
        filas = [tuple(f) for f in conexion.execute(sql, parametros)]
        conexion.close()
        return filas

    def estado_celda(self, id_celda):
        return self.consultar("SELECT estado FROM celdas WHERE id_celda = ?", (id_celda,))[0][0]

    def celda_de_movimientos(self, placa):
        """id_celda de todos los movimientos del vehículo, del más antiguo al más reciente."""
        return [
            f[0]
            for f in self.consultar(
                "SELECT m.id_celda FROM movimientos m JOIN vehiculos v ON v.id = m.vehiculo_id "
                "WHERE v.placa = ? ORDER BY m.id_movimiento",
                (placa,),
            )
        ]

    def instantanea(self):
        return (
            self.consultar("SELECT * FROM vehiculos ORDER BY id"),
            self.consultar("SELECT * FROM movimientos ORDER BY id_movimiento"),
            self.consultar("SELECT * FROM celdas ORDER BY id_celda"),
        )

    # ---- asignación (RF10) ----
    def test_asignar_celda_disponible_y_compatible(self):
        auto, = self.crear_celdas([("Zona A", "Automóvil", "Disponible")])
        self.ingresar("ABC123")
        html = self.asignar("ABC123", auto)
        self.assertIn(ASIGNADA, html)
        self.assertEqual(self.celda_de_movimientos("ABC123"), [auto])
        self.assertEqual(self.estado_celda(auto), "Ocupada")

    def test_asignar_celda_ocupada_se_rechaza(self):
        ocupada, = self.crear_celdas([("Zona A", "Automóvil", "Ocupada")])
        self.ingresar("ABC123")
        antes = self.instantanea()
        self.assertIn(CELDA_NO_VALIDA, self.asignar("ABC123", ocupada))
        self.assertEqual(self.instantanea(), antes)

    def test_asignar_celda_incompatible_se_rechaza(self):
        moto, = self.crear_celdas([("Zona B", "Motocicleta", "Disponible")])
        self.ingresar("ABC123", "Automóvil")
        antes = self.instantanea()
        self.assertIn(CELDA_NO_VALIDA, self.asignar("ABC123", moto))
        self.assertEqual(self.instantanea(), antes)
        self.assertEqual(self.estado_celda(moto), "Disponible")

    def test_compatibilidad_usa_el_tipo_guardado_del_vehiculo(self):
        auto, moto = self.crear_celdas(
            [("Zona A", "Automóvil", "Disponible"), ("Zona B", "Motocicleta", "Disponible")]
        )
        self.ingresar("XYZ98A", "Motocicleta")
        # aunque el formulario enviara otro tipo, solo cuenta el tipo guardado
        html = self.cliente.post(
            "/celdas/asignar",
            data={"placa": "XYZ98A", "id_celda": auto, "tipo_vehiculo": "Automóvil"},
            follow_redirects=True,
        ).get_data(as_text=True)
        self.assertIn(CELDA_NO_VALIDA, html)
        self.assertIn(ASIGNADA, self.asignar("XYZ98A", moto))

    def test_celda_inexistente(self):
        self.ingresar("ABC123")
        self.assertIn("La celda seleccionada no existe", self.asignar("ABC123", 999))
        self.assertEqual(self.celda_de_movimientos("ABC123"), [None])

    def test_vehiculo_sin_entrada_activa_o_inexistente(self):
        auto, = self.crear_celdas([("Zona A", "Automóvil", "Disponible")])
        self.assertIn("No existe un vehículo registrado", self.asignar("NOEXISTE", auto))
        self.ingresar("ABC123")
        self.registrar_salida("ABC123")
        self.assertIn("no tiene una entrada activa", self.asignar("ABC123", auto))
        self.assertEqual(self.estado_celda(auto), "Disponible")

    def test_vehiculo_que_ya_tiene_celda_no_recibe_otra(self):
        primera, segunda = self.crear_celdas(
            [("Zona A", "Automóvil", "Disponible"), ("Zona A", "Automóvil", "Disponible")]
        )
        self.ingresar("ABC123")
        self.asignar("ABC123", primera)
        self.assertIn("ya tiene una celda asignada", self.asignar("ABC123", segunda))
        self.assertEqual(self.celda_de_movimientos("ABC123"), [primera])
        self.assertEqual(self.estado_celda(segunda), "Disponible")

    def test_una_celda_no_se_asigna_a_dos_vehiculos(self):
        celda, = self.crear_celdas([("Zona A", "Automóvil", "Disponible")])
        self.ingresar("AAA111")
        self.ingresar("BBB222")
        self.assertIn(ASIGNADA, self.asignar("AAA111", celda))
        self.assertIn(CELDA_NO_VALIDA, self.asignar("BBB222", celda))
        self.assertEqual(self.celda_de_movimientos("AAA111"), [celda])
        self.assertEqual(self.celda_de_movimientos("BBB222"), [None])

    def test_la_base_de_datos_impide_dos_movimientos_activos_en_la_misma_celda(self):
        celda, = self.crear_celdas([("Zona A", "Automóvil", "Disponible")])
        self.ingresar("AAA111")
        self.ingresar("BBB222")
        conexion = database.conectar(self.ruta_bd)
        with conexion:
            conexion.execute("UPDATE movimientos SET id_celda = ? WHERE id_movimiento = ?", (celda, self.id_movimiento_activo("AAA111")))
        with self.assertRaises(sqlite3.IntegrityError):
            with conexion:
                conexion.execute("UPDATE movimientos SET id_celda = ? WHERE id_movimiento = ?", (celda, self.id_movimiento_activo("BBB222")))
        conexion.close()

    def test_no_se_puede_referenciar_una_celda_inexistente(self):
        self.ingresar("ABC123")
        conexion = database.conectar(self.ruta_bd)
        with self.assertRaises(sqlite3.IntegrityError):
            with conexion:
                conexion.execute("UPDATE movimientos SET id_celda = 999")
        conexion.close()

    def test_asignar_sin_vehiculo_o_sin_celda(self):
        celda, = self.crear_celdas([("Zona A", "Automóvil", "Disponible")])
        self.ingresar("ABC123")
        self.assertIn("Debe seleccionar un vehículo", self.asignar("", celda))
        self.assertIn("Debe seleccionar una celda", self.asignar("ABC123", ""))
        self.assertEqual(self.estado_celda(celda), "Disponible")

    def test_vehiculo_que_ya_estaba_dentro_sin_celda_puede_recibirla(self):
        # movimiento anterior a la Fase 9: sin id_celda
        self.ingresar("ABC123")
        self.assertEqual(self.celda_de_movimientos("ABC123"), [None])
        celda, = self.crear_celdas([("Zona A", "Automóvil", "Disponible")])
        self.assertIn(ASIGNADA, self.asignar("ABC123", celda))

    # ---- liberación (RF11) ----
    def test_la_salida_libera_la_celda(self):
        celda, = self.crear_celdas([("Zona A", "Automóvil", "Disponible")])
        self.ingresar("ABC123")
        self.asignar("ABC123", celda)
        self.assertIn("Salida registrada correctamente", self.registrar_salida("ABC123"))
        self.assertEqual(self.estado_celda(celda), "Disponible")
        # el historial conserva qué celda ocupó el movimiento
        self.assertEqual(self.celda_de_movimientos("ABC123"), [celda])

    def test_celda_liberada_puede_asignarse_a_otro_vehiculo(self):
        celda, = self.crear_celdas([("Zona A", "Automóvil", "Disponible")])
        self.ingresar("AAA111")
        self.ingresar("BBB222")
        self.asignar("AAA111", celda)
        self.registrar_salida("AAA111")
        self.assertIn(ASIGNADA, self.asignar("BBB222", celda))
        self.assertEqual(self.celda_de_movimientos("AAA111"), [celda])
        self.assertEqual(self.celda_de_movimientos("BBB222"), [celda])

    def test_salida_sin_celda_asignada_no_afecta_ninguna_celda(self):
        ocupada, libre = self.crear_celdas(
            [("Zona A", "Automóvil", "Ocupada"), ("Zona A", "Automóvil", "Disponible")]
        )
        self.ingresar("ABC123")
        self.assertIn("Salida registrada correctamente", self.registrar_salida("ABC123"))
        self.assertEqual((self.estado_celda(ocupada), self.estado_celda(libre)), ("Ocupada", "Disponible"))

    def test_la_salida_solo_libera_la_celda_de_su_propio_movimiento(self):
        celda_a, celda_b = self.crear_celdas(
            [("Zona A", "Automóvil", "Disponible"), ("Zona A", "Automóvil", "Disponible")]
        )
        self.ingresar("AAA111")
        self.ingresar("BBB222")
        self.asignar("AAA111", celda_a)
        self.asignar("BBB222", celda_b)
        # aunque el formulario traiga otra celda, solo cuenta la del movimiento guardado
        self.registrar_salida("AAA111", id_celda=celda_b)
        self.assertEqual((self.estado_celda(celda_a), self.estado_celda(celda_b)), ("Disponible", "Ocupada"))
        self.assertEqual(self.celda_de_movimientos("BBB222"), [celda_b])

    def test_segunda_salida_no_libera_una_celda_reasignada(self):
        celda, = self.crear_celdas([("Zona A", "Automóvil", "Disponible")])
        self.ingresar("AAA111")
        self.ingresar("BBB222")
        self.asignar("AAA111", celda)
        movimiento_a = self.id_movimiento_activo("AAA111")
        self.registrar_salida("AAA111")
        self.asignar("BBB222", celda)
        # reenvío del formulario antiguo de la salida de AAA111
        html = self.cliente.post(
            "/salida",
            data={"placa": "AAA111", "movimiento_id": movimiento_a, "accion": "registrar"},
            follow_redirects=True,
        ).get_data(as_text=True)
        self.assertIn("ya fue registrada", html)
        self.assertEqual(self.estado_celda(celda), "Ocupada")

    def test_vehiculo_reingresa_y_los_movimientos_anteriores_se_conservan(self):
        celda, = self.crear_celdas([("Zona A", "Automóvil", "Disponible")])
        self.ingresar("ABC123")
        self.asignar("ABC123", celda)
        self.registrar_salida("ABC123")
        self.ingresar("ABC123")
        self.assertIn(ASIGNADA, self.asignar("ABC123", celda))
        self.registrar_salida("ABC123")
        self.assertEqual(self.celda_de_movimientos("ABC123"), [celda, celda])
        self.assertEqual(len(self.consultar("SELECT id_movimiento FROM movimientos")), 2)
        self.assertEqual(self.estado_celda(celda), "Disponible")

    # ---- pantalla ----
    def test_pantalla_lista_solo_vehiculos_dentro_sin_celda_y_todas_las_celdas(self):
        auto, moto, ocupada = self.crear_celdas(
            [
                ("Zona A", "Automóvil", "Disponible"),
                ("Zona B", "Motocicleta", "Disponible"),
                ("Zona A", "Automóvil", "Ocupada"),
            ]
        )
        self.ingresar("AAA111")
        self.ingresar("BBB222")
        self.ingresar("CCC333")
        self.asignar("BBB222", auto)  # BBB222 ya tiene celda; la celda auto queda Ocupada
        self.registrar_salida("CCC333")
        html = self.cliente.get("/celdas/asignar").get_data(as_text=True)
        self.assertIn("Asignar celda a un vehículo", html)
        self.assertIn("Seleccione un vehículo y una celda disponible compatible.", html)
        self.assertIn('value="AAA111"', html)
        self.assertNotIn('value="BBB222"', html)  # ya tiene celda
        self.assertNotIn('value="CCC333"', html)  # ya salió
        filas = re.findall(r"<tr>(.*?)</tr>", html.split("<tbody>")[1], re.S)
        self.assertEqual(len(filas), 3)  # se muestran todas las celdas
        # botón de opción solo en la única celda disponible (moto); auto y ocupada no lo tienen
        self.assertEqual(html.count('type="radio"'), 1)
        self.assertIn(f'value="{moto}" aria-label', html)
        self.assertNotIn(f'value="{auto}" aria-label', html)
        self.assertNotIn(f'value="{ocupada}" aria-label', html)

    def test_pantalla_tiene_los_botones_del_mockup_y_el_menu(self):
        html = self.cliente.get("/celdas/asignar").get_data(as_text=True)
        self.assertIn("Asignar celda</button>", html)
        self.assertIn('href="/celdas"', html)
        self.assertIn("Cancelar", html)
        self.assertRegex(html, r'menu-enlace activo"\s+href="/celdas"')
        self.assertIn('href="/celdas/asignar"', self.cliente.get("/celdas").get_data(as_text=True))

    def test_pantalla_sin_vehiculos_ni_celdas(self):
        html = self.cliente.get("/celdas/asignar").get_data(as_text=True)
        self.assertIn("No hay vehículos dentro del parqueadero sin celda asignada", html)
        self.assertIn("No hay celdas registradas en el parqueadero", html)

    def test_consultar_la_pantalla_no_modifica_los_datos(self):
        self.crear_celdas([("Zona A", "Automóvil", "Disponible")])
        self.ingresar("ABC123")
        antes = self.instantanea()
        self.cliente.get("/celdas/asignar")
        self.cliente.get("/celdas")
        self.assertEqual(self.instantanea(), antes)

    def test_error_conserva_el_vehiculo_seleccionado(self):
        moto, = self.crear_celdas([("Zona B", "Motocicleta", "Disponible")])
        self.ingresar("ABC123", "Automóvil")
        html = self.asignar("ABC123", moto)
        self.assertRegex(html, r'<option value="ABC123"\s+selected>')

    def test_consulta_de_celdas_refleja_la_asignacion(self):
        celda, = self.crear_celdas([("Zona A", "Automóvil", "Disponible")])
        self.ingresar("ABC123")
        self.asignar("ABC123", celda)
        html = self.cliente.get("/celdas").get_data(as_text=True)
        self.assertIn("Ocupada", html)
        self.registrar_salida("ABC123")
        self.assertIn("Disponible", self.cliente.get("/celdas").get_data(as_text=True))

    # ---- esquema y migración ----
    def test_id_usuario_existe_y_no_se_llena(self):
        celda, = self.crear_celdas([("Zona A", "Automóvil", "Disponible")])
        self.ingresar("ABC123")
        self.asignar("ABC123", celda)
        self.registrar_salida("ABC123")
        self.assertEqual(self.consultar("SELECT id_celda, id_usuario FROM movimientos"), [(celda, None)])

    def test_migracion_de_una_base_anterior_conserva_los_datos(self):
        ruta = os.path.join(self.carpeta.name, "anterior.db")
        conexion = database.conectar(ruta)
        with conexion:
            conexion.execute(
                "CREATE TABLE vehiculos (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "placa TEXT NOT NULL UNIQUE, tipo_vehiculo TEXT NOT NULL)"
            )
            conexion.execute(
                "CREATE TABLE movimientos (id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT, "
                "vehiculo_id INTEGER NOT NULL, fecha_hora_entrada TEXT NOT NULL, fecha_hora_salida TEXT, "
                "FOREIGN KEY (vehiculo_id) REFERENCES vehiculos (id))"
            )
            conexion.execute("INSERT INTO vehiculos (placa, tipo_vehiculo) VALUES ('ABC123', 'Automóvil')")
            conexion.execute(
                "INSERT INTO movimientos (vehiculo_id, fecha_hora_entrada, fecha_hora_salida) "
                "VALUES (1, '2026-01-01 08:00:00', '2026-01-01 10:00:00')"
            )
            conexion.execute(
                "INSERT INTO movimientos (vehiculo_id, fecha_hora_entrada) VALUES (1, '2026-01-02 08:00:00')"
            )
        conexion.close()

        database.crear_tablas(ruta)
        database.crear_tablas(ruta)  # repetirlo no debe causar errores

        conexion = database.conectar(ruta)
        columnas = [f["name"] for f in conexion.execute("PRAGMA table_info(movimientos)")]
        movimientos = [
            tuple(f)
            for f in conexion.execute(
                "SELECT id_movimiento, fecha_hora_entrada, fecha_hora_salida, id_celda, id_usuario "
                "FROM movimientos ORDER BY id_movimiento"
            )
        ]
        celda = database.crear_celda(conexion, "Zona A", "Automóvil")
        # el índice nuevo funciona tras la migración
        with conexion:
            database.asignar_celda_a_movimiento(conexion, 2, 1, celda)
        conexion.close()
        self.assertEqual(columnas[-2:], ["id_celda", "id_usuario"])
        self.assertEqual(
            movimientos,
            [
                (1, "2026-01-01 08:00:00", "2026-01-01 10:00:00", None, None),
                (2, "2026-01-02 08:00:00", None, None, None),
            ],
        )

    def test_asignacion_no_cambia_vehiculos_ni_historial(self):
        celda, = self.crear_celdas([("Zona A", "Automóvil", "Disponible")])
        self.ingresar("ABC123")
        vehiculos_antes = self.consultar("SELECT * FROM vehiculos")
        self.asignar("ABC123", celda)
        self.assertEqual(self.consultar("SELECT * FROM vehiculos"), vehiculos_antes)
        historial = self.cliente.get("/historial").get_data(as_text=True)
        self.assertIn("ABC123", historial)
        self.assertIn("Dentro", historial)

    def test_funcion_cambiar_estado_celda_es_condicional(self):
        celda, = self.crear_celdas([("Zona A", "Automóvil", "Disponible")])
        conexion = database.conectar(self.ruta_bd)
        with conexion:
            self.assertFalse(database.cambiar_estado_celda(conexion, celda, "Ocupada", "Disponible"))
            self.assertTrue(database.cambiar_estado_celda(conexion, celda, "Disponible", "Ocupada"))
            self.assertFalse(database.cambiar_estado_celda(conexion, celda, "Disponible", "Ocupada"))
        conexion.close()
        self.assertEqual(self.estado_celda(celda), "Ocupada")


if __name__ == "__main__":
    unittest.main()

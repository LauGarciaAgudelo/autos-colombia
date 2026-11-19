import os
import sqlite3
import tempfile
import unittest

import database


class PruebasPagos(unittest.TestCase):
    def setUp(self):
        self.carpeta = tempfile.TemporaryDirectory()
        self.ruta_bd = os.path.join(self.carpeta.name, "pagos.db")
        database.crear_tablas(self.ruta_bd)
        self.conexion = database.conectar(self.ruta_bd)

    def tearDown(self):
        self.conexion.close()
        self.carpeta.cleanup()

    def crear_vehiculo(self, placa="ABC123"):
        return database.crear_vehiculo(self.conexion, placa, "Automóvil")

    def registrar_pago(
        self, vehiculo_id, valor=120000, fecha_pago="2026-11-18", periodo="2026-11"
    ):
        return database.crear_pago(
            self.conexion, vehiculo_id, valor, fecha_pago, periodo
        )

    def test_tabla_pagos_se_crea_con_claves_y_restricciones(self):
        columnas = [
            fila["name"] for fila in self.conexion.execute("PRAGMA table_info(pagos)")
        ]
        self.assertEqual(
            columnas, ["id_pago", "vehiculo_id", "valor", "fecha_pago", "periodo"]
        )
        columnas_no_nulas = [
            fila["name"]
            for fila in self.conexion.execute("PRAGMA table_info(pagos)")
            if fila["notnull"]
        ]
        self.assertEqual(
            columnas_no_nulas, ["vehiculo_id", "valor", "fecha_pago", "periodo"]
        )
        self.assertEqual(self.conexion.execute("PRAGMA foreign_keys").fetchone()[0], 1)

        claves_foraneas = self.conexion.execute(
            "PRAGMA foreign_key_list(pagos)"
        ).fetchall()
        self.assertEqual(
            [(fila["table"], fila["from"], fila["to"]) for fila in claves_foraneas],
            [("vehiculos", "vehiculo_id", "id")],
        )

        indices = self.conexion.execute("PRAGMA index_list(pagos)").fetchall()
        indices_unicos = [fila["name"] for fila in indices if fila["unique"]]
        columnas_unicas = [
            tuple(
                columna["name"]
                for columna in self.conexion.execute(
                    f"PRAGMA index_info({nombre})"
                ).fetchall()
            )
            for nombre in indices_unicos
        ]
        self.assertIn(("vehiculo_id", "periodo"), columnas_unicas)

    def test_crear_tablas_conserva_las_tablas_y_datos_anteriores(self):
        vehiculo_id = self.crear_vehiculo()
        usuario_id = database.crear_usuario(
            self.conexion, "Ana Pérez", "00123", "ana@correo.com"
        )
        celda_id = database.crear_celda(self.conexion, "Zona A", "Automóvil")
        database.crear_movimiento_entrada(
            self.conexion, vehiculo_id, "2026-11-18 10:00:00"
        )
        movimiento = self.conexion.execute(
            "SELECT id_movimiento FROM movimientos WHERE vehiculo_id = ?",
            (vehiculo_id,),
        ).fetchone()
        database.asignar_celda_a_movimiento(
            self.conexion, movimiento["id_movimiento"], vehiculo_id, celda_id
        )
        self.conexion.execute(
            "UPDATE movimientos SET id_usuario = ? WHERE id_movimiento = ?",
            (usuario_id, movimiento["id_movimiento"]),
        )
        self.conexion.commit()

        tablas = ("vehiculos", "movimientos", "usuarios", "celdas")
        antes = {
            tabla: (
                [
                    fila["name"]
                    for fila in self.conexion.execute(
                        f"PRAGMA table_info({tabla})"
                    )
                ],
                [
                    tuple(fila)
                    for fila in self.conexion.execute(f"SELECT * FROM {tabla}")
                ],
            )
            for tabla in tablas
        }

        database.crear_tablas(self.ruta_bd)

        despues = {
            tabla: (
                [
                    fila["name"]
                    for fila in self.conexion.execute(
                        f"PRAGMA table_info({tabla})"
                    )
                ],
                [
                    tuple(fila)
                    for fila in self.conexion.execute(f"SELECT * FROM {tabla}")
                ],
            )
            for tabla in tablas
        }
        self.assertEqual(despues, antes)

    def test_guarda_un_pago_valido(self):
        vehiculo_id = self.crear_vehiculo()

        pago_id = self.registrar_pago(vehiculo_id)

        pago = self.conexion.execute(
            "SELECT id_pago, vehiculo_id, valor, fecha_pago, periodo "
            "FROM pagos WHERE id_pago = ?",
            (pago_id,),
        ).fetchone()
        self.assertEqual(
            tuple(pago), (pago_id, vehiculo_id, 120000, "2026-11-18", "2026-11")
        )

    def test_pago_se_conserva_al_reinicializar_la_base_de_datos(self):
        vehiculo_id = self.crear_vehiculo()
        self.registrar_pago(vehiculo_id)
        self.conexion.commit()
        self.conexion.close()

        database.crear_tablas(self.ruta_bd)
        self.conexion = database.conectar(self.ruta_bd)

        pagos = database.consultar_pagos_por_vehiculo(self.conexion, vehiculo_id)
        self.assertEqual(len(pagos), 1)
        self.assertEqual(pagos[0]["periodo"], "2026-11")

    def test_rechaza_pagos_de_vehiculos_inexistentes(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.registrar_pago(99999)

    def test_rechaza_un_pago_duplicado_del_mismo_periodo(self):
        vehiculo_id = self.crear_vehiculo()
        self.registrar_pago(vehiculo_id)

        with self.assertRaises(sqlite3.IntegrityError):
            self.registrar_pago(vehiculo_id)

    def test_permite_pagos_de_periodos_diferentes(self):
        vehiculo_id = self.crear_vehiculo()
        self.registrar_pago(vehiculo_id, periodo="2026-10")

        pago_id = self.registrar_pago(vehiculo_id, periodo="2026-11")

        self.assertEqual(
            [fila["periodo"] for fila in database.consultar_pagos_por_vehiculo(
                self.conexion, vehiculo_id
            )],
            ["2026-11", "2026-10"],
        )
        self.assertIsNotNone(pago_id)

    def test_permite_el_mismo_periodo_para_vehiculos_diferentes(self):
        primer_vehiculo = self.crear_vehiculo("ABC123")
        segundo_vehiculo = self.crear_vehiculo("XYZ789")

        self.registrar_pago(primer_vehiculo)
        pago_id = self.registrar_pago(segundo_vehiculo)

        pago = self.conexion.execute(
            "SELECT vehiculo_id, periodo FROM pagos WHERE id_pago = ?",
            (pago_id,),
        ).fetchone()
        self.assertEqual(tuple(pago), (segundo_vehiculo, "2026-11"))

    def test_rechaza_valores_cero_o_negativos(self):
        vehiculo_id = self.crear_vehiculo()

        for valor in (0, -1):
            with self.subTest(valor=valor):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.registrar_pago(vehiculo_id, valor=valor)

    def test_rechaza_valores_que_no_sean_enteros(self):
        vehiculo_id = self.crear_vehiculo()

        with self.assertRaises(ValueError):
            self.registrar_pago(vehiculo_id, valor=120000.5)

    def test_rechaza_fechas_que_no_sean_iso_8601(self):
        vehiculo_id = self.crear_vehiculo()

        for fecha_pago in ("18/11/2026", "2026-02-30", "2026-2-03"):
            with self.subTest(fecha_pago=fecha_pago):
                with self.assertRaises(ValueError):
                    self.registrar_pago(vehiculo_id, fecha_pago=fecha_pago)

    def test_rechaza_periodos_que_no_sean_ano_y_mes_validos(self):
        vehiculo_id = self.crear_vehiculo()

        for periodo in ("2026-2", "2026-13", "2026/11"):
            with self.subTest(periodo=periodo):
                with self.assertRaises(ValueError):
                    self.registrar_pago(vehiculo_id, periodo=periodo)

    def test_consulta_solo_los_pagos_del_vehiculo_indicado(self):
        primer_vehiculo = self.crear_vehiculo("ABC123")
        segundo_vehiculo = self.crear_vehiculo("XYZ789")
        self.registrar_pago(primer_vehiculo, periodo="2026-10")
        self.registrar_pago(primer_vehiculo, periodo="2026-11")
        self.registrar_pago(segundo_vehiculo, periodo="2026-11")

        pagos = database.consultar_pagos_por_vehiculo(self.conexion, primer_vehiculo)

        self.assertEqual([fila["vehiculo_id"] for fila in pagos], [primer_vehiculo] * 2)
        self.assertEqual([fila["periodo"] for fila in pagos], ["2026-11", "2026-10"])

    def test_consulta_duplicado_por_vehiculo_y_periodo(self):
        vehiculo_id = self.crear_vehiculo()
        self.assertFalse(
            database.existe_pago_para_periodo(self.conexion, vehiculo_id, "2026-11")
        )

        self.registrar_pago(vehiculo_id)

        self.assertTrue(
            database.existe_pago_para_periodo(self.conexion, vehiculo_id, "2026-11")
        )

    def test_las_pruebas_usan_una_base_temporal_no_la_base_real(self):
        ruta_real = os.path.join(os.path.dirname(database.__file__), "parqueadero.db")

        self.assertEqual(
            os.path.commonpath([self.ruta_bd, self.carpeta.name]), self.carpeta.name
        )
        self.assertNotEqual(os.path.realpath(self.ruta_bd), os.path.realpath(ruta_real))
        self.assertTrue(os.path.isfile(self.ruta_bd))


if __name__ == "__main__":
    unittest.main()

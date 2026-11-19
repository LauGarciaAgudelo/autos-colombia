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

SIN_USUARIOS = "No hay usuarios registrados en el parqueadero"
SIN_COINCIDENCIAS = "No se encontraron usuarios con la búsqueda realizada"


class PruebasUsuarios(unittest.TestCase):
    def setUp(self):
        # Base de datos temporal: no se tocan los datos reales
        self.carpeta = tempfile.TemporaryDirectory()
        self.ruta_bd = os.path.join(self.carpeta.name, "prueba.db")
        aplicacion.app.config["BASE_DE_DATOS"] = self.ruta_bd
        database.crear_tablas(self.ruta_bd)
        self.cliente = aplicacion.app.test_client()

    def tearDown(self):
        self.carpeta.cleanup()

    def registrar(self, nombre="Ana María Pérez", documento="1020304050", correo="ana@correo.com"):
        return self.cliente.post(
            "/usuarios/registrar",
            data={"nombre": nombre, "documento": documento, "correo": correo},
            follow_redirects=True,
        )

    def consultar_bd(self, sql="SELECT nombre, documento, correo FROM usuarios ORDER BY id_usuario"):
        conexion = database.conectar(self.ruta_bd)
        filas = [tuple(f) for f in conexion.execute(sql)]
        conexion.close()
        return filas

    def pedir(self, **parametros):
        return self.cliente.get("/usuarios", query_string=parametros).get_data(as_text=True)

    def filas(self, html):
        """Filas de la tabla con las 3 columnas de datos (sin la columna Acciones)."""
        cuerpo = html.split("<tbody>")[1].split("</tbody>")[0] if "<tbody>" in html else ""
        return [
            re.findall(r"<td>(.*?)</td>", fila, re.S)[:3]
            for fila in re.findall(r"<tr>(.*?)</tr>", cuerpo, re.S)
        ]

    def datos_de_prueba(self):
        self.registrar("Ana María Pérez", "1020304050", "ana@correo.com")
        self.registrar("Carlos Gómez", "0098765", "carlos@correo.com")
        self.registrar("Luisa Fernanda Rojas", "52123456", "luisa@correo.com")

    def id_de(self, documento):
        return self.consultar_bd(
            f"SELECT id_usuario FROM usuarios WHERE documento = '{documento}'"
        )[0][0]

    def actualizar(self, id_usuario, nombre, documento, correo):
        return self.cliente.post(
            f"/usuarios/actualizar/{id_usuario}",
            data={"nombre": nombre, "documento": documento, "correo": correo},
            follow_redirects=True,
        )

    def test_registrar_usuario_correctamente(self):
        respuesta = self.registrar()
        self.assertIn("Usuario registrado correctamente", respuesta.get_data(as_text=True))
        self.assertEqual(
            self.consultar_bd(), [("Ana María Pérez", "1020304050", "ana@correo.com")]
        )

    def test_registrar_sin_nombre(self):
        html = self.registrar(nombre="   ").get_data(as_text=True)
        self.assertIn("El nombre completo es obligatorio", html)
        self.assertEqual(self.consultar_bd(), [])

    def test_registrar_sin_documento(self):
        html = self.registrar(documento="").get_data(as_text=True)
        self.assertIn("El documento de identidad es obligatorio", html)
        self.assertEqual(self.consultar_bd(), [])

    def test_registrar_sin_correo(self):
        html = self.registrar(correo="").get_data(as_text=True)
        self.assertIn("El correo electrónico es obligatorio", html)
        self.assertEqual(self.consultar_bd(), [])

    def test_documento_duplicado(self):
        self.registrar(nombre="Ana", documento="123")
        html = self.registrar(nombre="Otra Persona", documento="123", correo="otra@correo.com").get_data(as_text=True)
        self.assertIn("Ya existe un usuario registrado con el documento 123", html)
        self.assertEqual(self.consultar_bd(), [("Ana", "123", "ana@correo.com")])

    def test_documento_duplicado_con_espacios(self):
        self.registrar(documento="123")
        html = self.registrar(documento="  123  ").get_data(as_text=True)
        self.assertIn("Ya existe un usuario registrado con el documento 123", html)
        self.assertEqual(len(self.consultar_bd()), 1)

    def test_espacios_al_inicio_y_al_final_se_eliminan(self):
        self.registrar(nombre="  Ana Pérez  ", documento="  0012345  ", correo="  ana@correo.com  ")
        self.assertEqual(self.consultar_bd(), [("Ana Pérez", "0012345", "ana@correo.com")])

    def test_documento_conserva_ceros_iniciales(self):
        self.registrar(documento="000123")
        self.assertEqual(self.consultar_bd("SELECT documento FROM usuarios"), [("000123",)])

    def test_correo_con_formato_invalido(self):
        for correo in ["ana", "ana@", "@correo.com", "ana@correo", "ana correo@correo.com"]:
            html = self.registrar(correo=correo).get_data(as_text=True)
            self.assertIn("no tiene un formato válido", html, correo)
        self.assertEqual(self.consultar_bd(), [])

    def test_errores_conservan_los_valores_escritos(self):
        html = self.registrar(nombre="Ana Pérez", documento="555", correo="mal").get_data(as_text=True)
        self.assertIn('value="Ana Pérez"', html)
        self.assertIn('value="555"', html)
        self.assertIn('value="mal"', html)

    def test_la_base_de_datos_rechaza_documentos_duplicados(self):
        self.registrar(documento="123")
        conexion = database.conectar(self.ruta_bd)
        with self.assertRaises(Exception) as contexto:
            with conexion:
                database.crear_usuario(conexion, "Otro", "123", "otro@correo.com")
        conexion.close()
        self.assertEqual(type(contexto.exception).__name__, "IntegrityError")

    def test_consultar_usuarios_registrados(self):
        self.datos_de_prueba()
        filas = self.filas(self.pedir())
        self.assertEqual(
            filas,
            [
                ["Ana María Pérez", "1020304050", "ana@correo.com"],
                ["Carlos Gómez", "0098765", "carlos@correo.com"],
                ["Luisa Fernanda Rojas", "52123456", "luisa@correo.com"],
            ],
        )

    def test_consultar_sin_usuarios(self):
        respuesta = self.cliente.get("/usuarios")
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.get_data(as_text=True)
        self.assertIn(SIN_USUARIOS, html)
        self.assertNotIn("<tbody>", html)

    def test_buscar_por_nombre_completo(self):
        self.datos_de_prueba()
        filas = self.filas(self.pedir(q="Carlos Gómez"))
        self.assertEqual([f[0] for f in filas], ["Carlos Gómez"])

    def test_buscar_por_nombre_parcial_sin_importar_mayusculas(self):
        self.datos_de_prueba()
        self.assertEqual([f[0] for f in self.filas(self.pedir(q="  FERNANDA "))], ["Luisa Fernanda Rojas"])
        self.assertEqual([f[0] for f in self.filas(self.pedir(q="gómez"))], ["Carlos Gómez"])
        self.assertEqual([f[0] for f in self.filas(self.pedir(q="MARÍA"))], ["Ana María Pérez"])

    def test_buscar_por_documento(self):
        self.datos_de_prueba()
        self.assertEqual([f[1] for f in self.filas(self.pedir(q="0098765"))], ["0098765"])
        self.assertEqual([f[0] for f in self.filas(self.pedir(q="5212"))], ["Luisa Fernanda Rojas"])

    def test_buscar_sin_coincidencias(self):
        self.datos_de_prueba()
        html = self.pedir(q="inexistente")
        self.assertIn(SIN_COINCIDENCIAS, html)
        self.assertNotIn(SIN_USUARIOS, html)
        self.assertNotIn("<tbody>", html)

    def test_la_busqueda_no_usa_comodines(self):
        self.datos_de_prueba()
        self.assertIn(SIN_COINCIDENCIAS, self.pedir(q="%"))
        self.assertIn(SIN_COINCIDENCIAS, self.pedir(q="_"))

    def test_consultar_usuarios_no_modifica_la_base_de_datos(self):
        self.datos_de_prueba()
        antes = self.consultar_bd("SELECT * FROM usuarios ORDER BY id_usuario")
        self.pedir()
        self.pedir(q="ana")
        self.pedir(q="nadie")
        self.assertEqual(self.consultar_bd("SELECT * FROM usuarios ORDER BY id_usuario"), antes)

    def test_usuarios_permanecen_al_reiniciar_la_aplicacion(self):
        self.datos_de_prueba()
        database.crear_tablas(self.ruta_bd)  # equivale a iniciar de nuevo la aplicación
        self.assertEqual(len(self.consultar_bd()), 3)
        self.assertEqual(len(self.filas(self.pedir())), 3)

    def test_menu_usuarios_y_acceso_a_registrar(self):
        html = self.cliente.get("/").get_data(as_text=True)
        self.assertIn('href="/usuarios"', html)
        self.assertIn('href="/usuarios/registrar"', self.pedir())

    def test_actualizar_abre_el_formulario_con_los_datos_actuales(self):
        self.datos_de_prueba()
        id_carlos = self.id_de("0098765")
        respuesta = self.cliente.get(f"/usuarios/actualizar/{id_carlos}")
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.get_data(as_text=True)
        self.assertIn("Actualizar usuario", html)
        self.assertIn('value="Carlos Gómez"', html)
        self.assertIn('value="0098765"', html)
        self.assertIn('value="carlos@correo.com"', html)
        self.assertIn("Guardar cambios", html)
        self.assertIn("Cancelar", html)

    def test_listado_tiene_columna_acciones_con_enlace_por_id(self):
        self.datos_de_prueba()
        html = self.pedir()
        self.assertIn("<th>Acciones</th>", html)
        for documento in ("1020304050", "0098765", "52123456"):
            self.assertIn(f'href="/usuarios/actualizar/{self.id_de(documento)}"', html)

    def test_actualizar_nombre(self):
        self.datos_de_prueba()
        id_carlos = self.id_de("0098765")
        respuesta = self.actualizar(id_carlos, "Carlos Andrés Gómez", "0098765", "carlos@correo.com")
        self.assertIn("Usuario actualizado correctamente", respuesta.get_data(as_text=True))
        self.assertEqual(
            self.consultar_bd(f"SELECT nombre, documento, correo FROM usuarios WHERE id_usuario = {id_carlos}"),
            [("Carlos Andrés Gómez", "0098765", "carlos@correo.com")],
        )

    def test_actualizar_correo(self):
        self.datos_de_prueba()
        id_carlos = self.id_de("0098765")
        self.actualizar(id_carlos, "Carlos Gómez", "0098765", "nuevo@correo.com")
        self.assertEqual(
            self.consultar_bd(f"SELECT correo FROM usuarios WHERE id_usuario = {id_carlos}"),
            [("nuevo@correo.com",)],
        )

    def test_actualizar_con_documento_disponible_conserva_el_id(self):
        self.datos_de_prueba()
        id_carlos = self.id_de("0098765")
        respuesta = self.actualizar(id_carlos, "Carlos Gómez", " 7777777 ", "carlos@correo.com")
        self.assertIn("Usuario actualizado correctamente", respuesta.get_data(as_text=True))
        self.assertEqual(self.id_de("7777777"), id_carlos)
        self.assertEqual(self.consultar_bd("SELECT COUNT(*) FROM usuarios"), [(3,)])

    def test_actualizar_conservando_el_mismo_documento(self):
        self.datos_de_prueba()
        id_carlos = self.id_de("0098765")
        respuesta = self.actualizar(id_carlos, "Carlos G.", "0098765", "carlos@correo.com")
        html = respuesta.get_data(as_text=True)
        self.assertIn("Usuario actualizado correctamente", html)
        self.assertNotIn("Ya existe", html)

    def test_actualizar_rechaza_documento_de_otro_usuario(self):
        self.datos_de_prueba()
        antes = self.consultar_bd("SELECT * FROM usuarios ORDER BY id_usuario")
        id_carlos = self.id_de("0098765")
        html = self.actualizar(id_carlos, "Carlos Gómez", "1020304050", "carlos@correo.com").get_data(as_text=True)
        self.assertIn("Ya existe otro usuario registrado con el documento 1020304050", html)
        self.assertEqual(self.consultar_bd("SELECT * FROM usuarios ORDER BY id_usuario"), antes)

    def test_actualizar_rechaza_campos_vacios_y_conserva_lo_escrito(self):
        self.datos_de_prueba()
        antes = self.consultar_bd("SELECT * FROM usuarios ORDER BY id_usuario")
        id_carlos = self.id_de("0098765")
        casos = [
            (("  ", "0098765", "carlos@correo.com"), "El nombre completo es obligatorio"),
            (("Carlos Gómez", "  ", "carlos@correo.com"), "El documento de identidad es obligatorio"),
            (("Carlos Gómez", "0098765", ""), "El correo electrónico es obligatorio"),
        ]
        for (nombre, documento, correo), mensaje in casos:
            html = self.actualizar(id_carlos, nombre, documento, correo).get_data(as_text=True)
            self.assertIn(mensaje, html)
        self.assertEqual(self.consultar_bd("SELECT * FROM usuarios ORDER BY id_usuario"), antes)

    def test_actualizar_rechaza_correo_invalido_y_conserva_lo_escrito(self):
        self.datos_de_prueba()
        id_carlos = self.id_de("0098765")
        html = self.actualizar(id_carlos, "Nombre Nuevo", "5555", "correo-malo").get_data(as_text=True)
        self.assertIn("no tiene un formato válido", html)
        self.assertIn('value="Nombre Nuevo"', html)
        self.assertIn('value="5555"', html)
        self.assertIn('value="correo-malo"', html)
        self.assertEqual(
            self.consultar_bd(f"SELECT nombre FROM usuarios WHERE id_usuario = {id_carlos}"),
            [("Carlos Gómez",)],
        )

    def test_actualizar_usuario_inexistente_devuelve_404(self):
        self.datos_de_prueba()
        for ruta in ("/usuarios/actualizar/9999", "/usuarios/actualizar/0", "/usuarios/actualizar/abc"):
            self.assertEqual(self.cliente.get(ruta).status_code, 404, ruta)
        respuesta = self.cliente.post(
            "/usuarios/actualizar/9999",
            data={"nombre": "X", "documento": "1", "correo": "x@correo.com"},
        )
        self.assertEqual(respuesta.status_code, 404)
        html = self.cliente.get("/usuarios/actualizar/9999").get_data(as_text=True)
        self.assertIn("No existe un usuario con el identificador 9999", html)
        self.assertEqual(len(self.consultar_bd()), 3)

    def test_cambios_permanecen_al_reiniciar(self):
        self.datos_de_prueba()
        self.actualizar(self.id_de("0098765"), "Carlos Andrés Gómez", "7777777", "nuevo@correo.com")
        database.crear_tablas(self.ruta_bd)  # equivale a iniciar de nuevo la aplicación
        self.assertIn(
            ("Carlos Andrés Gómez", "7777777", "nuevo@correo.com"), self.consultar_bd()
        )

    def test_actualizar_no_modifica_a_otros_usuarios(self):
        self.datos_de_prueba()
        otros_antes = self.consultar_bd(
            "SELECT * FROM usuarios WHERE documento != '0098765' ORDER BY id_usuario"
        )
        self.actualizar(self.id_de("0098765"), "Carlos Andrés Gómez", "7777777", "nuevo@correo.com")
        otros_despues = self.consultar_bd(
            "SELECT * FROM usuarios WHERE documento != '7777777' ORDER BY id_usuario"
        )
        self.assertEqual(otros_despues, otros_antes)

    def test_listado_muestra_la_informacion_actualizada(self):
        self.datos_de_prueba()
        respuesta = self.actualizar(self.id_de("0098765"), "Carlos Andrés Gómez", "7777777", "nuevo@correo.com")
        html = respuesta.get_data(as_text=True)  # tras guardar se redirige al listado
        self.assertIn("Consultar usuarios", html)
        self.assertIn("Usuario actualizado correctamente", html)
        filas = self.filas(html)
        self.assertIn(["Carlos Andrés Gómez", "7777777", "nuevo@correo.com"], filas)
        self.assertNotIn(["Carlos Gómez", "0098765", "carlos@correo.com"], filas)

    def test_registrar_usuarios_sigue_funcionando(self):
        self.datos_de_prueba()
        html = self.registrar("Nuevo Usuario", "999", "nuevo@correo.com").get_data(as_text=True)
        self.assertIn("Usuario registrado correctamente", html)
        self.assertEqual(len(self.consultar_bd()), 4)

    def test_pagina_inexistente_muestra_404_con_el_diseno_de_la_aplicacion(self):
        respuesta = self.cliente.get("/no-existe")
        self.assertEqual(respuesta.status_code, 404)
        html = respuesta.get_data(as_text=True)
        self.assertIn("La página solicitada no existe", html)
        self.assertIn("encabezado", html)

    def test_las_tablas_de_la_iteracion_1_no_cambian(self):
        columnas = {
            tabla: [f[1] for f in self.consultar_bd(f"PRAGMA table_info({tabla})")]
            for tabla in ("vehiculos", "movimientos", "usuarios")
        }
        self.assertEqual(columnas["usuarios"], ["id_usuario", "nombre", "documento", "correo"])
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


if __name__ == "__main__":
    unittest.main()

import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime

from flask import Flask, abort, flash, redirect, render_template, request, url_for
from werkzeug.exceptions import NotFound

import database

TIPOS_VEHICULO = ["Automóvil", "Motocicleta"]
ESTADOS_FILTRO = {"todos": "Todos", "dentro": "Dentro", "salio": "Salió"}
FORMATO_FECHA_BD = "%Y-%m-%d %H:%M:%S"
FORMATO_FECHA_PANTALLA = "%d/%m/%Y %H:%M:%S"
FORMATO_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

app = Flask(__name__)
# Clave necesaria para mostrar mensajes con flash().
# El valor por defecto es solo para desarrollo: no usar en producción.
# Para usar otra clave, definir la variable de entorno CLAVE_SECRETA.
app.secret_key = os.environ.get(
    "CLAVE_SECRETA", "clave-solo-para-desarrollo-no-usar-en-produccion"
)
app.config["BASE_DE_DATOS"] = os.environ.get(
    "BASE_DE_DATOS", os.path.join(app.root_path, "parqueadero.db")
)
database.crear_tablas(app.config["BASE_DE_DATOS"])


def registrar_entrada(placa, tipo, fecha_entrada):
    """Guarda la entrada. Devuelve un mensaje de error, o None si todo salió bien."""
    with closing(database.conectar(app.config["BASE_DE_DATOS"])) as conexion:
        try:
            with conexion:
                vehiculo = database.buscar_vehiculo_por_placa(conexion, placa)
                if vehiculo is None:
                    vehiculo_id = database.crear_vehiculo(conexion, placa, tipo)
                elif vehiculo["tipo_vehiculo"] != tipo:
                    return (
                        f"La placa {placa} ya está registrada como {vehiculo['tipo_vehiculo']}. "
                        f"No se puede registrar la entrada como {tipo} "
                        "y el tipo del vehículo no fue modificado."
                    )
                elif database.vehiculo_esta_dentro(conexion, vehiculo["id"]):
                    return f"El vehículo con placa {placa} ya se encuentra dentro del parqueadero."
                else:
                    vehiculo_id = vehiculo["id"]

                database.crear_movimiento_entrada(
                    conexion, vehiculo_id, fecha_entrada.strftime(FORMATO_FECHA_BD)
                )
        except sqlite3.IntegrityError:
            return "No se pudo registrar la entrada porque el vehículo ya está registrado. Intente de nuevo."
    return None


def formatear_fecha(fecha_bd):
    return datetime.strptime(fecha_bd, FORMATO_FECHA_BD).strftime(FORMATO_FECHA_PANTALLA)


def consultar_vehiculo_activo(placa):
    """Busca el vehículo y su entrada activa. Devuelve (datos, error); uno de los dos es None."""
    if not placa:
        return None, "La placa del vehículo es obligatoria."

    with closing(database.conectar(app.config["BASE_DE_DATOS"])) as conexion:
        vehiculo = database.buscar_vehiculo_por_placa(conexion, placa)
        if vehiculo is None:
            return None, f"No existe un vehículo registrado con la placa {placa}."

        movimiento = database.buscar_movimiento_activo(conexion, vehiculo["id"])
        if movimiento is None:
            return None, (
                f"El vehículo con placa {placa} no tiene una entrada activa: "
                "no se encuentra dentro del parqueadero."
            )

    datos = {
        "placa": vehiculo["placa"],
        "tipo": vehiculo["tipo_vehiculo"],
        "movimiento_id": movimiento["id_movimiento"],
        "fecha_entrada": formatear_fecha(movimiento["fecha_hora_entrada"]),
    }
    return datos, None


def registrar_salida(placa, movimiento_id_texto, fecha_salida):
    """Cierra el movimiento activo. Devuelve un mensaje de error, o None si todo salió bien."""
    if not placa:
        return "La placa del vehículo es obligatoria."
    try:
        movimiento_id = int(movimiento_id_texto)
    except ValueError:
        return "Primero debe consultar el vehículo con el botón Buscar."

    with closing(database.conectar(app.config["BASE_DE_DATOS"])) as conexion:
        with conexion:
            vehiculo = database.buscar_vehiculo_por_placa(conexion, placa)
            if vehiculo is None:
                return f"No existe un vehículo registrado con la placa {placa}."

            movimiento = database.buscar_movimiento(conexion, movimiento_id)
            if movimiento is None or movimiento["vehiculo_id"] != vehiculo["id"]:
                return (
                    f"El movimiento indicado no corresponde a la placa {placa}. "
                    "No se modificó ningún registro."
                )
            if movimiento["fecha_hora_salida"] is not None:
                return (
                    "La salida de este movimiento ya fue registrada el "
                    f"{formatear_fecha(movimiento['fecha_hora_salida'])}. "
                    "No se modificó ningún registro."
                )

            cerrado = database.registrar_fecha_salida(
                conexion,
                movimiento["id_movimiento"],
                vehiculo["id"],
                fecha_salida.strftime(FORMATO_FECHA_BD),
            )
            if not cerrado:
                return "Este movimiento ya fue cerrado. No se modificó ningún registro."
    return None


@app.route("/")
def inicio():
    return render_template("index.html")


@app.route("/entrada", methods=["GET", "POST"])
def entrada():
    placa = ""
    tipo = ""
    errores = []

    if request.method == "POST":
        placa = request.form.get("placa", "").strip().upper()
        tipo = request.form.get("tipo_vehiculo", "")

        if not placa:
            errores.append("La placa del vehículo es obligatoria.")
        if not tipo:
            errores.append("Debe seleccionar el tipo de vehículo.")
        elif tipo not in TIPOS_VEHICULO:
            errores.append("El tipo de vehículo seleccionado no es válido.")

        if not errores:
            fecha_entrada = datetime.now()
            error = registrar_entrada(placa, tipo, fecha_entrada)
            if error is None:
                flash(
                    f"Entrada registrada correctamente: {placa} ({tipo}) "
                    f"el {fecha_entrada.strftime('%d/%m/%Y a las %H:%M:%S')}.",
                    "success",
                )
                return redirect(url_for("entrada"))
            errores.append(error)

    return render_template(
        "entrada.html", tipos=TIPOS_VEHICULO, placa=placa, tipo=tipo, errores=errores
    )


@app.route("/salida", methods=["GET", "POST"])
def salida():
    placa = ""
    consulta = None
    errores = []

    if request.method == "POST":
        placa = request.form.get("placa", "").strip().upper()

        if request.form.get("accion") == "registrar":
            fecha_salida = datetime.now()
            error = registrar_salida(placa, request.form.get("movimiento_id", ""), fecha_salida)
            if error is None:
                flash(
                    f"Salida registrada correctamente: {placa} "
                    f"el {fecha_salida.strftime('%d/%m/%Y a las %H:%M:%S')}.",
                    "success",
                )
                return redirect(url_for("salida"))
            errores.append(error)
        else:
            consulta, error = consultar_vehiculo_activo(placa)
            if error is not None:
                errores.append(error)

    return render_template("salida.html", placa=placa, consulta=consulta, errores=errores)


@app.route("/historial")
def historial():
    placa = request.args.get("placa", "").strip().upper()
    estado = request.args.get("estado", "todos")
    if estado not in ESTADOS_FILTRO:
        estado = "todos"

    with closing(database.conectar(app.config["BASE_DE_DATOS"])) as conexion:
        filas = database.consultar_movimientos(conexion, placa, estado)
        hay_movimientos = database.contar_movimientos(conexion) > 0

    movimientos = [
        {
            "placa": fila["placa"],
            "tipo": fila["tipo_vehiculo"],
            "fecha_entrada": formatear_fecha(fila["fecha_hora_entrada"]),
            "fecha_salida": (
                formatear_fecha(fila["fecha_hora_salida"]) if fila["fecha_hora_salida"] else "-"
            ),
            "estado": "Salió" if fila["fecha_hora_salida"] else "Dentro",
        }
        for fila in filas
    ]
    return render_template(
        "historial.html",
        movimientos=movimientos,
        hay_movimientos=hay_movimientos,
        placa=placa,
        estado=estado,
        estados=ESTADOS_FILTRO,
    )


def validar_datos_usuario(nombre, documento, correo):
    """Devuelve la lista de errores de los campos (vacía si todo es válido)."""
    errores = []
    if not nombre:
        errores.append("El nombre completo es obligatorio.")
    if not documento:
        errores.append("El documento de identidad es obligatorio.")
    if not correo:
        errores.append("El correo electrónico es obligatorio.")
    elif not FORMATO_CORREO.match(correo):
        errores.append("El correo electrónico no tiene un formato válido (ejemplo: nombre@correo.com).")
    return errores


def guardar_usuario(nombre, documento, correo):
    """Guarda el usuario. Devuelve un mensaje de error, o None si todo salió bien."""
    with closing(database.conectar(app.config["BASE_DE_DATOS"])) as conexion:
        try:
            with conexion:
                if database.buscar_usuario_por_documento(conexion, documento) is not None:
                    return f"Ya existe un usuario registrado con el documento {documento}."
                database.crear_usuario(conexion, nombre, documento, correo)
        except sqlite3.IntegrityError:
            return f"Ya existe un usuario registrado con el documento {documento}."
    return None


def modificar_usuario(id_usuario, nombre, documento, correo):
    """Actualiza el usuario. Devuelve un mensaje de error, o None si todo salió bien."""
    mensaje_duplicado = f"Ya existe otro usuario registrado con el documento {documento}."
    with closing(database.conectar(app.config["BASE_DE_DATOS"])) as conexion:
        try:
            with conexion:
                otro = database.buscar_usuario_por_documento(conexion, documento)
                if otro is not None and otro["id_usuario"] != id_usuario:
                    return mensaje_duplicado
                database.actualizar_usuario(conexion, id_usuario, nombre, documento, correo)
        except sqlite3.IntegrityError:
            return mensaje_duplicado
    return None


@app.route("/usuarios/registrar", methods=["GET", "POST"])
def registrar_usuario():
    nombre = ""
    documento = ""
    correo = ""
    errores = []

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        documento = request.form.get("documento", "").strip()
        correo = request.form.get("correo", "").strip()

        errores = validar_datos_usuario(nombre, documento, correo)

        if not errores:
            error = guardar_usuario(nombre, documento, correo)
            if error is None:
                flash(f"Usuario registrado correctamente: {nombre} (documento {documento}).", "success")
                return redirect(url_for("registrar_usuario"))
            errores.append(error)

    return render_template(
        "registrar_usuario.html",
        nombre=nombre,
        documento=documento,
        correo=correo,
        errores=errores,
    )


@app.route("/usuarios/actualizar/<int:id_usuario>", methods=["GET", "POST"])
def actualizar_usuario(id_usuario):
    with closing(database.conectar(app.config["BASE_DE_DATOS"])) as conexion:
        usuario = database.buscar_usuario_por_id(conexion, id_usuario)
    if usuario is None:
        abort(404, description=f"No existe un usuario con el identificador {id_usuario}.")

    nombre = usuario["nombre"]
    documento = usuario["documento"]
    correo = usuario["correo"]
    errores = []

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        documento = request.form.get("documento", "").strip()
        correo = request.form.get("correo", "").strip()

        errores = validar_datos_usuario(nombre, documento, correo)

        if not errores:
            error = modificar_usuario(id_usuario, nombre, documento, correo)
            if error is None:
                flash(f"Usuario actualizado correctamente: {nombre} (documento {documento}).", "success")
                return redirect(url_for("usuarios"))
            errores.append(error)

    return render_template(
        "actualizar_usuario.html",
        id_usuario=id_usuario,
        nombre=nombre,
        documento=documento,
        correo=correo,
        errores=errores,
    )


@app.route("/celdas")
def celdas():
    tipo = request.args.get("tipo", "")
    if tipo not in TIPOS_VEHICULO:
        tipo = ""

    with closing(database.conectar(app.config["BASE_DE_DATOS"])) as conexion:
        lista_celdas = database.consultar_celdas(conexion, tipo)
        hay_celdas = database.contar_celdas(conexion) > 0

    hay_disponibles = any(celda["estado"] == "Disponible" for celda in lista_celdas)
    return render_template(
        "consultar_celdas.html",
        celdas=lista_celdas,
        hay_celdas=hay_celdas,
        hay_disponibles=hay_disponibles,
        tipo=tipo,
        tipos=TIPOS_VEHICULO,
    )


@app.errorhandler(404)
def pagina_no_encontrada(error):
    mensaje = "La página solicitada no existe."
    if error.description != NotFound.description:
        mensaje = error.description
    return render_template("error_404.html", mensaje=mensaje), 404


@app.route("/usuarios")
def usuarios():
    busqueda = request.args.get("q", "").strip()

    with closing(database.conectar(app.config["BASE_DE_DATOS"])) as conexion:
        lista_usuarios = database.consultar_usuarios(conexion, busqueda)
        hay_usuarios = database.contar_usuarios(conexion) > 0

    return render_template(
        "consultar_usuarios.html",
        usuarios=lista_usuarios,
        hay_usuarios=hay_usuarios,
        busqueda=busqueda,
    )


if __name__ == "__main__":
    # El modo debug solo se activa si se define FLASK_DEBUG=1
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")

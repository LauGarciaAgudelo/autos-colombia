# Autos Colombia

Aplicación web sencilla para gestionar las operaciones de un parqueadero.
Proyecto académico de la asignatura Ingeniería de Software.

## Objetivo de la Iteración 1

Permitir al personal del parqueadero registrar vehículos, controlar sus entradas y
salidas, saber qué vehículos están dentro y consultar el historial de movimientos.

## Tecnologías

Python 3, Flask, SQLite (módulo `sqlite3` de Python), HTML, CSS y Bootstrap.
Git y GitHub para el control de versiones.

## Requisitos

- Python 3.9 o superior
- Git
- Conexión a internet para ver los estilos (Bootstrap se carga desde un CDN)

## Instalación

1. Clonar el repositorio y entrar a la carpeta:

   ```bash
   git clone https://github.com/LauGarciaAgudelo/autos-colombia.git
   cd autos-colombia
   ```

2. Crear el entorno virtual:

   ```bash
   python -m venv venv
   ```

3. Activar el entorno virtual:

   - Windows (PowerShell): `venv\Scripts\Activate.ps1`
   - Windows (CMD): `venv\Scripts\activate.bat`
   - Linux / macOS: `source venv/bin/activate`

4. Instalar las dependencias:

   ```bash
   pip install -r requirements.txt
   ```

## Ejecución

```bash
python app.py
```

Abrir en el navegador: <http://127.0.0.1:5000>

Para detener la aplicación, presionar `Ctrl + C` en la terminal.

La base de datos `parqueadero.db` se crea automáticamente en la carpeta del proyecto
la primera vez que se inicia la aplicación. Si ya existe, se conservan sus datos.
Este archivo no se sube a Git. Si la base de datos viene de una versión anterior con otros
nombres de columnas, se actualiza automáticamente al iniciar y no se pierden datos.

### Configuración opcional

Se hace con variables de entorno; la aplicación funciona sin definirlas.

| Variable | Para qué sirve |
|---|---|
| `CLAVE_SECRETA` | Clave de Flask para los mensajes. Si no se define, se usa una clave de desarrollo que **no debe usarse en producción**. |
| `BASE_DE_DATOS` | Ruta de otro archivo SQLite (por ejemplo, para pruebas). |
| `FLASK_DEBUG` | Con el valor `1` activa el modo debug. Por defecto está desactivado. |

## Funcionalidades implementadas

### Registrar entrada (`/entrada`)
Se ingresa la placa y el tipo de vehículo (Automóvil o Motocicleta). La placa se guarda
sin espacios laterales y en mayúsculas, y la fecha y hora se registran automáticamente.
No se permite una segunda entrada mientras el vehículo siga dentro, ni cambiar el tipo
de una placa ya registrada.

### Registrar salida (`/salida`)
1. Escribir la placa y presionar **Buscar**: se muestran el tipo de vehículo y la fecha
   y hora de entrada. Si la placa no existe o el vehículo no está dentro del
   parqueadero, se muestra un mensaje.
2. Presionar **Registrar salida** (solo se habilita cuando hay una entrada activa).
   Se guarda la fecha y hora de salida en el mismo movimiento; los registros no se borran.

Un movimiento no puede cerrarse dos veces. Después de la salida, el vehículo puede volver
a ingresar.

### Historial (`/historial`)
Tabla con la placa, el tipo, la fecha y hora de entrada, la de salida (un guion si el
vehículo sigue dentro) y el estado (**Dentro** o **Salió**). Se muestran primero los
movimientos más recientes y un vehículo aparece una vez por cada ingreso.

Filtros (formulario GET, sin JavaScript):
- **Buscar por placa:** placa completa o parcial, sin distinguir mayúsculas ni espacios laterales.
- **Estado:** Todos, Dentro o Salió.
- **Limpiar filtros:** vuelve a mostrar todos los registros.

Los filtros pueden usarse por separado o combinados.

## Iteración 2 (en desarrollo)

La Iteración 2 agrega la gestión de usuarios y de celdas. Por ahora están implementadas la
gestión de usuarios (registrar, consultar y actualizar) y la consulta de celdas; la
asignación y liberación de celdas todavía no.

### Registrar usuario (`/usuarios/registrar`)
Se ingresan el nombre completo, el documento de identidad y el correo electrónico. Los
tres campos son obligatorios, se eliminan los espacios laterales, el correo debe tener un
formato válido y no se permiten documentos repetidos. El documento se guarda como texto,
por lo que se conservan los ceros iniciales. Si hay un error, se conservan los datos escritos.

### Consultar usuarios (`/usuarios`)
Tabla con el nombre completo, el documento y el correo electrónico. El campo **Búsqueda**
filtra por nombre o documento (coincidencia parcial, sin distinguir mayúsculas) y
**Limpiar búsqueda** vuelve a mostrar todos los usuarios. Desde esta pantalla se accede
a **Registrar usuario** y, con el botón **Actualizar** de cada fila, a la edición del usuario.

### Actualizar usuario (`/usuarios/actualizar/<id_usuario>`)
El formulario se abre con los datos actuales del usuario. Se aplican las mismas validaciones
del registro; se puede conservar el mismo documento o cambiarlo por uno que no pertenezca a
otro usuario. Si hay un error se conservan los datos escritos, y al guardar se vuelve al
listado con un mensaje de confirmación. El usuario se identifica por su `id_usuario`, no por
el documento, y si no existe se muestra una página de "No encontrado" (404).

### Consultar celdas (`/celdas`)
Tabla con la celda (`id_celda`), la ubicación y el estado (**Disponible** en verde u
**Ocupada** en rojo), con los datos reales de la base de datos. El filtro **Tipo de vehículo**
(Automóvil o Motocicleta) muestra solo las celdas compatibles, tanto disponibles como
ocupadas. Mensajes:
- Sin celdas registradas: "No hay celdas registradas en el parqueadero".
- Ninguna celda compatible con el tipo elegido: "No hay celdas compatibles con este vehículo".
- Hay celdas compatibles pero todas ocupadas: se muestran y se avisa que no hay disponibles.

La tabla `celdas` tiene `id_celda`, `ubicacion` y `estado` (solo `Disponible` u `Ocupada`),
como en el modelo relacional, más la columna `tipo_vehiculo` (extensión acordada al modelo,
necesaria para validar la compatibilidad). La aplicación no crea celdas por sí sola.

**Celdas de demostración (opcional):** para ver la pantalla con datos de ejemplo sin mezclarlos
con los reales, ejecute `python cargar_celdas_demo.py`. Crea `parqueadero_demo.db` con 4 celdas
de ejemplo (solo si no tiene celdas). Para usarla: en PowerShell,
`$env:BASE_DE_DATOS = "parqueadero_demo.db"; python app.py`.

## Pruebas

```bash
python -m unittest discover -v
```

Las pruebas usan una base de datos temporal y no modifican `parqueadero.db`.

## Estructura del proyecto

```
autos-colombia/
├── app.py              # Punto de entrada, rutas y validaciones
├── database.py         # Conexión y consultas SQLite
├── cargar_celdas_demo.py  # Carga opcional de celdas de demostración (no se ejecuta sola)
├── test_entrada.py     # Pruebas del registro de entrada
├── test_salida.py      # Pruebas del registro de salida
├── test_historial.py   # Pruebas del historial
├── test_usuarios.py    # Pruebas de registro, consulta y actualización de usuarios
├── test_celdas.py      # Pruebas de la consulta de celdas
├── requirements.txt    # Dependencias (solo Flask)
├── templates/
│   ├── base.html       # Encabezado y navegación
│   ├── index.html      # Página principal
│   ├── entrada.html    # Registrar entrada
│   ├── salida.html     # Registrar salida
│   ├── historial.html  # Historial de movimientos
│   ├── registrar_usuario.html   # Registrar usuario
│   ├── actualizar_usuario.html  # Actualizar usuario
│   ├── consultar_usuarios.html  # Consultar usuarios
│   ├── consultar_celdas.html    # Consultar celdas
│   └── error_404.html           # Página "No encontrado"
└── static/
    └── css/
        └── styles.css  # Estilos propios
```


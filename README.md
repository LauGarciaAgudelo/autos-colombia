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
├── test_entrada.py     # Pruebas del registro de entrada
├── test_salida.py      # Pruebas del registro de salida
├── test_historial.py   # Pruebas del historial
├── requirements.txt    # Dependencias (solo Flask)
├── templates/
│   ├── base.html       # Encabezado y navegación
│   ├── index.html      # Página principal
│   ├── entrada.html    # Registrar entrada
│   ├── salida.html     # Registrar salida
│   └── historial.html  # Historial de movimientos
└── static/
    └── css/
        └── styles.css  # Estilos propios
```


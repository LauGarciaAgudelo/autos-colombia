# Autos Colombia

Este proyecto se desarrolló para la asignatura Ingeniería de Software. Es una aplicación
web para llevar el registro de vehículos, usuarios y celdas de un parqueadero.

El trabajo se organizó en dos iteraciones. En la primera se desarrollaron las entradas,
salidas y el historial de movimientos. En la segunda se agregaron el registro, consulta
y actualización de usuarios, junto con la consulta, asignación y liberación de celdas.

## Funcionalidades

### Iteración 1: entradas y salidas
- **Registrar entrada:** placa y tipo de vehículo (Automóvil o Motocicleta). La placa se guarda
  sin espacios laterales y en mayúsculas, y la fecha y hora se registran automáticamente. No se
  permite una segunda entrada mientras el vehículo siga dentro, ni cambiar el tipo de una placa
  ya registrada.
- **Registrar salida:** se busca el vehículo por su placa, se muestran su tipo y la fecha de
  entrada, y se registra la salida. Un movimiento no puede cerrarse dos veces.
- **Historial:** tabla con placa, tipo, fecha de entrada, fecha de salida y estado (**Dentro** o
  **Salió**), con los movimientos más recientes primero. Se puede filtrar por placa (completa o
  parcial) y por estado.

### Iteración 2: usuarios y celdas
- **Registrar usuario:** nombre completo, documento de identidad (se guarda como texto, con sus
  ceros iniciales) y correo electrónico. Los tres campos son obligatorios, el correo debe tener
  un formato válido y no se permiten documentos repetidos.
- **Consultar usuarios:** tabla con búsqueda por nombre o documento (coincidencia parcial, sin
  distinguir mayúsculas).
- **Actualizar usuario:** edición de los datos de un usuario existente, identificado por su
  `id_usuario`. Se puede conservar el mismo documento o cambiarlo por uno que no pertenezca a otro
  usuario.
- **Consultar celdas:** tabla con la celda, la ubicación y su estado (**Disponible** u
  **Ocupada**). El filtro por tipo de vehículo muestra solo las celdas compatibles.
- **Asignar celda:** se elige un vehículo que esté dentro y sin celda, y una celda **Disponible**.
  El sistema valida que la celda esté disponible y sea compatible con el tipo del vehículo, y la
  marca como **Ocupada**. Una celda no puede asignarse a dos vehículos a la vez, ni un vehículo
  recibe una segunda celda.
- **Liberar celda:** al registrar la salida de un vehículo, su celda vuelve a **Disponible**. El
  historial conserva qué celda ocupó cada movimiento.

## Tecnologías

Python 3, Flask, SQLite (módulo `sqlite3` de Python), HTML, CSS y Bootstrap.
Git y GitHub para el control de versiones.

## Requisitos

- Python 3.9 o superior (con SQLite 3.25 o superior, que ya incluye Python en Windows y macOS)
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

4. Instalar las dependencias (solo Flask):

   ```bash
   pip install -r requirements.txt
   ```

## Ejecución

```bash
python app.py
```

Abrir en el navegador: <http://127.0.0.1:5000>

Para detener la aplicación, presionar `Ctrl + C` en la terminal.

### Configuración opcional

Se hace con variables de entorno; la aplicación funciona sin definirlas.

| Variable | Para qué sirve |
|---|---|
| `CLAVE_SECRETA` | Clave de Flask para los mensajes. Si no se define, se usa una clave de desarrollo que **no debe usarse en producción**. |
| `BASE_DE_DATOS` | Ruta de otro archivo SQLite (por ejemplo, para la demostración o las pruebas). |
| `FLASK_DEBUG` | Con el valor `1` activa el modo debug. Por defecto está desactivado. |

## Base de datos

La base de datos `parqueadero.db` se crea automáticamente en la carpeta del proyecto la primera
vez que se inicia la aplicación, con las tablas `vehiculos`, `movimientos`, `usuarios` y `celdas`.
El archivo no se sube a Git. Al volver a iniciar la aplicación se conserva la información
registrada.

- Si la base de datos ya existe, se conservan sus datos. Si viene de una versión anterior, se
  actualiza sola al iniciar (por ejemplo, agregando las columnas `id_celda` e `id_usuario` a
  `movimientos`, que pueden quedar vacías en los movimientos anteriores).
- Se recomienda copiar `parqueadero.db` antes de iniciar la aplicación con una versión nueva:
  `Copy-Item parqueadero.db parqueadero.respaldo.db` (PowerShell) o `cp parqueadero.db parqueadero.respaldo.db`.
- La aplicación no incluye una pantalla para crear celdas ni las registra automáticamente: la tabla `celdas`
  empieza vacía y las celdas deben registrarse en la base de datos (para probar, ver la sección
  siguiente).
- La tabla `celdas` tiene `id_celda`, `ubicacion` y `estado` (solo `Disponible` u `Ocupada`), más
  la columna `tipo_vehiculo` (Automóvil o Motocicleta), que se agregó al modelo para poder validar
  la compatibilidad entre celdas y vehículos.
- La tabla `movimientos` incluye `id_usuario` como campo opcional. Se dejó previsto para
  relacionar los movimientos con los usuarios registrados, pero esa relación aún no se
  utiliza en las operaciones actuales. Su uso queda pendiente para una etapa posterior.

## Datos de demostración (opcional)

Para ver las pantallas de celdas con datos de ejemplo **sin mezclarlos con los reales**:

```powershell
python cargar_celdas_demo.py
$env:BASE_DE_DATOS = "parqueadero_demo.db"
python app.py
```

El script se ejecuta únicamente cuando se necesitan datos de ejemplo y está preparado
para no modificar `parqueadero.db` (la base principal). Crea
`parqueadero_demo.db` (otro archivo, también ignorado por Git)
con 4 celdas de ejemplo, y solo las agrega si esa base de datos todavía no tiene celdas. Para usar
otro archivo: `python cargar_celdas_demo.py ruta.db`.

Las celdas de demostración marcadas como "Ocupada" no tienen un vehículo asociado, por lo que no
se liberan al registrar una salida. Para probar la asignación y la liberación, use las celdas
"Disponible" (registre antes la entrada de un vehículo).

## Rutas principales

| Ruta | Métodos | Pantalla |
|---|---|---|
| `/` | GET | Inicio |
| `/entrada` | GET, POST | Registrar entrada |
| `/salida` | GET, POST | Registrar salida (buscar y registrar) |
| `/historial` | GET | Historial (filtros `placa` y `estado`) |
| `/usuarios` | GET | Consultar usuarios (búsqueda `q`) |
| `/usuarios/registrar` | GET, POST | Registrar usuario |
| `/usuarios/actualizar/<id_usuario>` | GET, POST | Actualizar usuario |
| `/celdas` | GET | Consultar celdas (filtro `tipo`) |
| `/celdas/asignar` | GET, POST | Asignar celda a un vehículo |

## Pruebas

```bash
python -m unittest discover -v
```

Se desarrollaron pruebas automatizadas para las dos iteraciones. Verifican registros,
consultas, actualizaciones y validaciones, incluidas las asignaciones y liberaciones de celdas.
En la última revisión se ejecutaron 130 pruebas correctamente. Para repetir la ejecución,
utilizar el comando anterior desde la carpeta principal del proyecto.

Las pruebas usan una base de datos temporal y no modifican `parqueadero.db`.

## Estructura del proyecto

```
autos-colombia/
├── app.py                 # Punto de entrada, rutas y validaciones
├── database.py            # Conexión, tablas y consultas SQLite
├── cargar_celdas_demo.py  # Carga opcional de celdas de demostración (no se ejecuta sola)
├── requirements.txt       # Dependencias (solo Flask)
├── test_entrada.py        # Pruebas del registro de entrada
├── test_salida.py         # Pruebas del registro de salida
├── test_historial.py      # Pruebas del historial
├── test_usuarios.py       # Pruebas de registro, consulta y actualización de usuarios
├── test_celdas.py         # Pruebas de la consulta de celdas
├── test_asignacion.py     # Pruebas de la asignación y liberación de celdas
├── templates/
│   ├── base.html                # Encabezado y navegación
│   ├── index.html               # Inicio
│   ├── entrada.html             # Registrar entrada
│   ├── salida.html              # Registrar salida
│   ├── historial.html           # Historial de movimientos
│   ├── registrar_usuario.html   # Registrar usuario
│   ├── consultar_usuarios.html  # Consultar usuarios
│   ├── actualizar_usuario.html  # Actualizar usuario
│   ├── consultar_celdas.html    # Consultar celdas
│   ├── asignar_celda.html       # Asignar celda a un vehículo
│   └── error_404.html           # Página "No encontrado"
└── static/
    └── css/
        └── styles.css           # Estilos propios
```

## Limitaciones conocidas

- La aplicación no tiene autenticación: cualquier persona con acceso a la dirección puede usar
  todas las pantallas.
- Una celda ocupada no se puede liberar manualmente: solo se libera al registrar la salida del
  vehículo que la ocupa.

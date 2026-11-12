# Autos Colombia

Aplicación web sencilla para gestionar las operaciones de un parqueadero.
Proyecto académico de Ingeniería de Software.

**Tecnologías:** Python 3, Flask, SQLite, HTML, CSS y Bootstrap.

## Estado actual

Fase 1 de la Iteración 1: configuración inicial. Solo existe la página principal;
las demás opciones del menú aparecen deshabilitadas.

## Requisitos

- Python 3.9 o superior
- Git

## Instalación

```bash
git clone https://github.com/LauGarciaAgudelo/autos-colombia.git
cd autos-colombia

python -m venv venv
```

Activar el entorno virtual:

- Windows (PowerShell): `venv\Scripts\Activate.ps1`
- Windows (CMD): `venv\Scripts\activate.bat`
- Linux / macOS: `source venv/bin/activate`

Instalar las dependencias:

```bash
pip install -r requirements.txt
```

## Ejecución

```bash
python app.py
```

Abrir en el navegador: <http://127.0.0.1:5000>

Para detener la aplicación, presionar `Ctrl + C` en la terminal.

> Bootstrap se carga desde internet (CDN), por lo que se necesita conexión
> para ver los estilos.

## Estructura del proyecto

```
autos-colombia/
├── app.py              # Punto de entrada de la aplicación
├── requirements.txt    # Dependencias
├── templates/
│   └── index.html      # Página principal
└── static/
    └── css/
        └── styles.css  # Estilos propios
```

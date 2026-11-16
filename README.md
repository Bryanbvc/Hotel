# Hotel Ríos del Sur – Sistema de gestión hotelera

Prototipo funcional desarrollado para la **Evaluación 3 de Ingeniería de Software**. Permite administrar habitaciones, huéspedes y reservas de un hotel, con procesos de check-in y check-out, perfiles de usuario y medidas de seguridad basadas en OWASP.

## Funcionalidades

**Personal del hotel (administrador y recepcionista)**

- Registro y administración de habitaciones (crear y editar; eliminar solo el administrador).
- Registro de huéspedes, buscador por nombre, apellido o documento, e historial de reservas.
- Consulta de disponibilidad por fechas, personas y tipo de habitación.
- Reservas: crear, consultar, modificar, cancelar y marcar como «No presentado».
- Check-in y check-out, con control de estados de las habitaciones.
- Tablero de habitaciones ocupadas y disponibles, y pantalla de llegadas y salidas del día.
- Confirmación por correo electrónico de cada reserva.

**Cliente**

- Registro de cuenta propia, consulta de disponibilidad y reserva a su nombre.
- «Mis reservas»: ver y cancelar únicamente sus propias reservas.

## Tecnologías

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3.10 o superior |
| Framework | Django 5.2 |
| Base de datos | MySQL 8 (administrada con MySQL Workbench) |
| Conector | mysqlclient |
| Configuración | python-dotenv (archivo `.env`) |
| Interfaz | Plantillas de Django y Bootstrap 5.3 |

## Estructura del proyecto

```
hotel_rios_del_sur/
├── config/                  Configuración de Django (settings, urls)
├── hotel/                   Aplicación principal
│   ├── models.py            Tablas: habitaciones, huéspedes, reservas, etc.
│   ├── services.py          Reglas de negocio (reservar, check-in, check-out...)
│   ├── validators.py        Validación de RUT, pasaporte, nombres y teléfonos
│   ├── permisos.py          Roles y control de acceso
│   ├── notificaciones.py    Envío de correos
│   ├── forms.py, views.py, urls.py, admin.py, signals.py
│   ├── templates/           Pantallas HTML
│   ├── fixtures/            Datos de ejemplo (datos_ejemplo.json)
│   ├── migrations/          Historial de cambios de la base de datos
│   └── tests/               Pruebas automáticas
├── database/                Script SQL con la estructura de la base de datos
├── docs/                    Informe técnico y diagrama de la base de datos
├── manage.py
├── requirements.txt
├── .env.example             Plantilla de configuración
└── README.md
```

## Requisitos previos

- Python 3.10 o superior.
- MySQL Server 8 y MySQL Workbench.
- Git.
- En Linux, además: `sudo apt install build-essential pkg-config libmysqlclient-dev` (necesario para instalar `mysqlclient`).

## Instalación paso a paso

Los comandos están escritos para Windows (PowerShell). En Linux o macOS se indican las diferencias.

### 1. Obtener el código

```
git clone https://github.com/TU_USUARIO/hotel-rios-del-sur.git
cd hotel-rios-del-sur
```

### 2. Crear y activar el entorno virtual

```
python -m venv venv
venv\Scripts\activate
```

En Linux o macOS: `source venv/bin/activate`

### 3. Instalar las dependencias

```
pip install -r requirements.txt
```

### 4. Crear la base de datos en MySQL

Abre MySQL Workbench, conéctate como administrador y ejecuta:

```sql
CREATE DATABASE bd_hotel CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'hotel_user'@'localhost' IDENTIFIED BY 'elige-una-clave-segura';
GRANT ALL PRIVILEGES ON bd_hotel.* TO 'hotel_user'@'localhost';
GRANT ALL PRIVILEGES ON `test\_%`.* TO 'hotel_user'@'localhost';
FLUSH PRIVILEGES;
```

La última concesión permite ejecutar las pruebas automáticas, que usan una base temporal.

### 5. Configurar las variables de entorno

Copia la plantilla y edítala con tus datos:

```
copy .env.example .env
```

En Linux o macOS: `cp .env.example .env`

Contenido del archivo `.env`:

| Variable | Descripción |
|---|---|
| `SECRET_KEY` | Clave secreta de Django. Debe ser larga y aleatoria. |
| `DEBUG` | `True` en desarrollo. En producción debe ser `False`. |
| `ALLOWED_HOSTS` | Direcciones permitidas, separadas por coma. |
| `DB_NAME` | Nombre de la base de datos (`bd_hotel`). |
| `DB_USER` y `DB_PASSWORD` | Usuario y clave creados en el paso 4. |
| `DB_HOST` y `DB_PORT` | Servidor y puerto de MySQL. El puerto estándar es 3306; la plantilla usa 3307. Ajusta según tu instalación. |

Para generar una clave secreta:

```
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

El archivo `.env` contiene secretos y nunca debe subirse al repositorio (ya está en `.gitignore`).

### 6. Crear las tablas

```
python manage.py migrate
```

Este comando crea todas las tablas y los grupos de usuarios `Recepcionista` y `Cliente`.

Para comprobar que los grupos existen (si el panel de administración muestra la lista de grupos vacía), ejecuta este comando, que es seguro repetir:

```
python manage.py shell -c "from django.contrib.auth.models import Group; [Group.objects.get_or_create(name=n) for n in ['Recepcionista','Cliente']]"
```

### 7. Cargar los datos de ejemplo (opcional)

Carga 5 tipos de habitación, 6 servicios y 9 habitaciones. Hazlo solo sobre una base de datos nueva:

```
python manage.py loaddata datos_ejemplo
```

### 8. Crear el usuario administrador

```
python manage.py createsuperuser
```

### 9. Ejecutar el sistema

```
python manage.py runserver
```

Abre en el navegador: <http://127.0.0.1:8000/>

### 10. Crear el usuario recepcionista

1. Entra a <http://127.0.0.1:8000/admin/> con el administrador.
2. En **Usuarios**, pulsa «Añadir usuario» y crea uno nuevo.
3. En la pantalla de edición, en **Grupos**, elige `Recepcionista` y guarda.

Los clientes no necesitan que alguien los cree: se registran solos desde la pantalla de inicio de sesión («Regístrate aquí»).

## Perfiles de usuario

| Perfil | Cómo se identifica | Qué puede hacer |
|---|---|---|
| Administrador | Usuario con «Estado de superusuario» | Todo, incluido eliminar habitaciones y usar `/admin/`. |
| Recepcionista | Grupo `Recepcionista` | Operación completa del hotel, sin eliminar habitaciones. |
| Cliente | Grupo `Cliente` (se asigna al registrarse) | Consultar disponibilidad, reservar y gestionar sus propias reservas. |

## Correo electrónico

Por defecto los correos **se muestran en la consola** donde corre `runserver`, así no se necesita ningún servidor de correo para probar. Para enviarlos de verdad, agrega al `.env`:

```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.tu-proveedor.com
EMAIL_PORT=587
EMAIL_HOST_USER=usuario
EMAIL_HOST_PASSWORD=clave
EMAIL_USE_TLS=True
```

## Pruebas automáticas

```
python manage.py test hotel -v 2
```

Ejecuta 106 pruebas que cubren validaciones, reglas de negocio, funcionalidades, perfil cliente, notificaciones y seguridad.

## Base de datos

Las tablas principales son:

| Tabla | Contenido |
|---|---|
| `hotel_tipohabitacion` | Tipos de habitación: capacidad, camas y tarifa por noche. |
| `hotel_servicio` y `hotel_tipohabitacion_servicios` | Servicios del hotel y su relación con cada tipo. |
| `hotel_habitacion` | Habitaciones con su número, piso y estado. |
| `hotel_huesped` | Huéspedes, con vínculo opcional a su cuenta de usuario. |
| `hotel_reserva` | Reservas con fechas, número de huéspedes, total y estado. |
| `hotel_notificacion` | Registro de cada correo enviado. |

Además, Django crea sus tablas de usuarios, grupos, permisos y sesiones (`auth_*`, `django_*`).

El archivo `database/hotel_rios_del_sur_estructura.sql` contiene la estructura completa de las tablas y relaciones, como documentación y para revisarla en MySQL Workbench. La instalación recomendada usa `python manage.py migrate`, que deja la base de datos en el estado correcto.

## Seguridad

- Inicio de sesión obligatorio, contraseñas con hash y validación de su fortaleza.
- Control de acceso por roles y protección de los datos de cada cliente.
- Protección contra inyección SQL, XSS y CSRF.
- Secretos fuera del código, en el archivo `.env`.
- HTTPS, cookies seguras y HSTS cuando `DEBUG=False`.
- Registro de eventos de seguridad en `logs/seguridad.log` (se crea automáticamente).

## Solución de problemas

| Problema | Solución |
|---|---|
| Error al instalar `mysqlclient` | En Linux, instala `libmysqlclient-dev` y `pkg-config`. En Windows, actualiza pip (`python -m pip install --upgrade pip`) para obtener la versión precompilada. |
| `Access denied for user` | Revisa `DB_USER`, `DB_PASSWORD` y que el usuario tenga permisos sobre `bd_hotel`. |
| `Can't connect to MySQL server` | Revisa `DB_HOST` y `DB_PORT`: el puerto debe coincidir con el de tu MySQL (3306 o 3307). |
| `KeyError: 'SECRET_KEY'` | Falta el archivo `.env` o la variable `SECRET_KEY`. Repite el paso 5. |
| Acceso denegado al entrar | El usuario no pertenece a ningún grupo. Asígnale `Recepcionista` o `Cliente` en el panel de administración. |
| Las pruebas fallan con `Access denied ... test_bd_hotel` | Falta la concesión de permisos sobre las bases `test_%` (paso 4). |

## Documentación

- Informe técnico: `docs/informe_tecnico.pdf`
- Diagrama de la base de datos: `docs/diagrama_base_de_datos.png`

## Autor

- **Nombre:** [Tu nombre completo]
- **Asignatura:** Ingeniería de Software – Evaluación 3
- **Institución:** [Nombre de tu institución]
- **Docente:** [Nombre del docente]

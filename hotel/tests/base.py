import logging
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.utils import timezone

from hotel.models import Habitacion, Huesped, TipoHabitacion


# El hasher rápido solo acelera las pruebas; el sistema real usa el de Django
@override_settings(
    SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class BaseTest(TestCase):
    """Datos de ejemplo compartidos por todas las pruebas."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Las pruebas no escriben en logs/seguridad.log (es evidencia real del sistema).
        # assertLogs sigue funcionando porque reemplaza los handlers por su cuenta.
        logger = logging.getLogger('hotel.seguridad')
        anteriores = logger.handlers[:]
        logger.handlers = [logging.NullHandler()]
        cls.addClassCleanup(setattr, logger, 'handlers', anteriores)

    @classmethod
    def setUpTestData(cls):
        cls.hoy = timezone.localdate()

        cls.doble = TipoHabitacion.objects.create(
            nombre='Doble', capacidad=2, camas=2, tarifa_noche=50000
        )
        cls.simple = TipoHabitacion.objects.create(
            nombre='Simple', capacidad=1, camas=1, tarifa_noche=30000
        )
        cls.h101 = Habitacion.objects.create(numero='101', tipo=cls.doble, piso=1)
        cls.h102 = Habitacion.objects.create(numero='102', tipo=cls.doble, piso=1)
        cls.h201 = Habitacion.objects.create(numero='201', tipo=cls.simple, piso=2)

        cls.ana = Huesped.objects.create(
            documento='12345678-5', nombre='Ana', apellido='Paz', email='ana@test.cl'
        )
        cls.luis = Huesped.objects.create(
            documento='9876543-3', nombre='Luis', apellido='Soto', email=''
        )

        cls.admin = User.objects.create_superuser('admin', 'admin@test.cl', 'Clave-Segura-123')
        cls.recepcion = cls._usuario('recepcion', 'Recepcionista')
        cls.sin_rol = User.objects.create_user('sinrol', 'sinrol@test.cl', 'Clave-Segura-123')

    @staticmethod
    def _usuario(nombre, grupo):
        usuario = User.objects.create_user(nombre, f'{nombre}@test.cl', 'Clave-Segura-123')
        usuario.groups.add(Group.objects.get_or_create(name=grupo)[0])
        return usuario

    def dia(self, n):
        """Fecha relativa a hoy: dia(2) = pasado mañana."""
        return self.hoy + timedelta(days=n)

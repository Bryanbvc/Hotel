import logging

from django.contrib.auth.signals import (
    user_logged_in, user_logged_out, user_login_failed,
)
from django.dispatch import receiver

registro = logging.getLogger('hotel.seguridad')


@receiver(user_logged_in)
def inicio_sesion(sender, request, user, **kwargs):
    registro.info('Inicio de sesión: %r', user.get_username())


@receiver(user_logged_out)
def cierre_sesion(sender, request, user, **kwargs):
    registro.info('Cierre de sesión: %r', user.get_username() if user else '-')


@receiver(user_login_failed)
def login_fallido(sender, credentials, request=None, **kwargs):
    registro.warning(
        'Inicio de sesión fallido para el usuario %r', credentials.get('username', '-')
    )
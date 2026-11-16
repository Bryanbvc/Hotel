import logging
from functools import wraps

from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied

registro = logging.getLogger('hotel.seguridad')

GRUPO_RECEPCION = 'Recepcionista'


def es_administrador(usuario):
    return usuario.is_active and usuario.is_superuser


def es_recepcionista(usuario):
    """El administrador también puede hacer todo lo de recepción."""
    return es_administrador(usuario) or (
        usuario.is_active
        and usuario.groups.filter(name=GRUPO_RECEPCION).exists()
    )


def _denegar(request):
    registro.warning(
        'Acceso denegado a %s para %r',
        request.path, request.user.get_username(),
    )
    raise PermissionDenied


def solo_recepcion(vista):
    """Decorador para vistas basadas en funciones."""
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not es_recepcionista(request.user):
            _denegar(request)
        return vista(request, *args, **kwargs)
    return envoltura


class SoloRecepcionMixin(UserPassesTestMixin):
    """Para vistas basadas en clases: exige perfil recepcionista o admin."""
    def test_func(self):
        return es_recepcionista(self.request.user)

    def handle_no_permission(self):
        _denegar(self.request)


class SoloAdministradorMixin(UserPassesTestMixin):
    """Para vistas basadas en clases: exige perfil administrador."""
    def test_func(self):
        return es_administrador(self.request.user)

    def handle_no_permission(self):
        _denegar(self.request)

# ---------------------------------------------------------------
# Perfil Cliente
# ---------------------------------------------------------------

GRUPO_CLIENTE = 'Cliente'


def es_cliente(usuario):
    return usuario.is_active and usuario.groups.filter(name=GRUPO_CLIENTE).exists()


def _permitir_a(*pruebas):
    """Crea un decorador que deja pasar si se cumple AL MENOS una prueba."""
    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not any(prueba(request.user) for prueba in pruebas):
                _denegar(request)
            return vista(request, *args, **kwargs)
        return envoltura
    return decorador


solo_cliente = _permitir_a(es_cliente)
recepcion_o_cliente = _permitir_a(es_recepcionista, es_cliente)
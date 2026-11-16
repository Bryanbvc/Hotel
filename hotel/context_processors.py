from .permisos import es_administrador, es_cliente, es_recepcionista


def roles(request):
    return {
        'es_admin': es_administrador(request.user),
        'es_recepcion': es_recepcionista(request.user),
        'es_cliente': es_cliente(request.user),
    }
import logging

from django.conf import settings
from django.core.mail import send_mail

from .models import Notificacion

registro = logging.getLogger('hotel.seguridad')

ASUNTOS = {
    'creada': 'Confirmación de reserva',
    'modificada': 'Reserva modificada',
    'cancelada': 'Reserva cancelada',
}

INTRODUCCION = {
    'creada': 'Tu reserva fue registrada correctamente.',
    'modificada': 'Tu reserva fue modificada. Estos son los datos actualizados.',
    'cancelada': 'Tu reserva fue cancelada.',
}


def _pesos(valor):
    return '$' + f'{valor:,.0f}'.replace(',', '.')


def _mensaje(reserva, evento):
    habitacion = reserva.habitacion
    return '\n'.join([
        f'Hola {reserva.huesped.nombre},',
        '',
        INTRODUCCION[evento],
        '',
        f'Reserva N° {reserva.pk}',
        f'Habitación: {habitacion.numero} ({habitacion.tipo.nombre})',
        f'Entrada: {reserva.fecha_entrada:%d/%m/%Y}',
        f'Salida: {reserva.fecha_salida:%d/%m/%Y}',
        f'Personas: {reserva.numero_huespedes}',
        f'Total: {_pesos(reserva.total)}',
        '',
        'Hotel Ríos del Sur',
    ])


def notificar_reserva(reserva, evento):
    """Envía un correo al huésped y guarda el resultado en Notificacion.

    Nunca lanza errores por problemas de envío: la reserva ya quedó guardada
    y un fallo del correo no debe deshacerla ni mostrar un error al usuario.
    """
    destinatario = reserva.huesped.email
    if not destinatario:
        registro.info('Reserva #%s: el huésped no tiene correo, no se notifica', reserva.pk)
        return None

    asunto = f'{ASUNTOS[evento]} #{reserva.pk} - Hotel Ríos del Sur'
    mensaje = _mensaje(reserva, evento)
    try:
        send_mail(
            asunto, mensaje, settings.DEFAULT_FROM_EMAIL, [destinatario],
            fail_silently=False,
        )
        estado = Notificacion.Estado.ENVIADA
        registro.info('Notificación %r enviada (reserva #%s)', evento, reserva.pk)
    except Exception:
        estado = Notificacion.Estado.FALLIDA
        registro.exception('Falló el envío de la notificación %r (reserva #%s)', evento, reserva.pk)

    return Notificacion.objects.create(
        reserva=reserva, destinatario=destinatario,
        asunto=asunto, mensaje=mensaje, estado=estado,
    )
from django.db import transaction
from django.utils import timezone

from .models import Habitacion, Reserva

# Solo estas reservas ocupan la habitación en sus fechas
ESTADOS_QUE_BLOQUEAN = [Reserva.Estado.RESERVADA, Reserva.Estado.EN_ESTADIA]


class HabitacionNoDisponible(Exception):
    """La habitación no se puede reservar en esas fechas."""


class OperacionNoPermitida(Exception):
    """La acción no corresponde al estado actual de la reserva o la habitación."""


def calcular_noches(entrada, salida):
    return (salida - entrada).days


def calcular_total(habitacion, entrada, salida):
    return calcular_noches(entrada, salida) * habitacion.tipo.tarifa_noche


def _reservas_que_se_cruzan(entrada, salida):
    """Reservas vigentes que ocupan alguna noche del rango pedido."""
    return Reserva.objects.filter(
        estado__in=ESTADOS_QUE_BLOQUEAN,
        fecha_entrada__lt=salida,
        fecha_salida__gt=entrada,
    )


def habitaciones_disponibles(entrada, salida, personas=1):
    ocupadas = _reservas_que_se_cruzan(entrada, salida).values('habitacion_id')
    return (
        Habitacion.objects.select_related('tipo')
        .filter(tipo__capacidad__gte=personas)
        .exclude(estado=Habitacion.Estado.MANTENCION)
        .exclude(pk__in=ocupadas)
        .order_by('tipo__tarifa_noche', 'numero')
    )


def crear_reserva(huesped, habitacion, entrada, salida):
    with transaction.atomic():
        # Bloquea la fila de la habitación hasta terminar. Si otra persona
        # reserva la misma habitación a la vez, espera su turno.
        habitacion = Habitacion.objects.select_for_update().get(pk=habitacion.pk)

        if habitacion.estado == Habitacion.Estado.MANTENCION:
            raise HabitacionNoDisponible('La habitación está en mantención.')

        if _reservas_que_se_cruzan(entrada, salida).filter(habitacion=habitacion).exists():
            raise HabitacionNoDisponible(
                'La habitación ya está reservada en esas fechas.'
            )

        return Reserva.objects.create(
            huesped=huesped,
            habitacion=habitacion,
            fecha_entrada=entrada,
            fecha_salida=salida,
            total=calcular_total(habitacion, entrada, salida),
        )


# ---------------------------------------------------------------
# Cambios de estado: cancelación, check-in, check-out
# ---------------------------------------------------------------

def _bloquear_reserva_y_habitacion(reserva_id):
    """Trae la reserva y su habitación con las filas bloqueadas.

    Debe llamarse dentro de transaction.atomic(). Los datos que devuelve
    son los más recientes, así que el estado se puede comprobar con seguridad.
    """
    reserva = Reserva.objects.select_for_update().get(pk=reserva_id)
    habitacion = Habitacion.objects.select_for_update().get(pk=reserva.habitacion_id)
    return reserva, habitacion


def cancelar_reserva(reserva_id):
    with transaction.atomic():
        reserva = Reserva.objects.select_for_update().get(pk=reserva_id)
        if reserva.estado != Reserva.Estado.RESERVADA:
            raise OperacionNoPermitida(
                'Solo se pueden cancelar reservas en estado Reservada.'
            )
        reserva.estado = Reserva.Estado.CANCELADA
        reserva.save(update_fields=['estado'])
        return reserva


def hacer_checkin(reserva_id):
    with transaction.atomic():
        reserva, habitacion = _bloquear_reserva_y_habitacion(reserva_id)
        hoy = timezone.localdate()

        if reserva.estado != Reserva.Estado.RESERVADA:
            raise OperacionNoPermitida(
                'El check-in solo se puede hacer en reservas en estado Reservada.'
            )
        if hoy < reserva.fecha_entrada:
            raise OperacionNoPermitida(
                f'El check-in se habilita desde la fecha de entrada '
                f'({reserva.fecha_entrada:%d/%m/%Y}).'
            )
        if hoy >= reserva.fecha_salida:
            raise OperacionNoPermitida(
                'La fecha de salida de esta reserva ya pasó; no se puede hacer el check-in.'
            )
        if habitacion.estado != Habitacion.Estado.DISPONIBLE:
            raise OperacionNoPermitida(
                f'La habitación {habitacion.numero} no está disponible '
                f'(estado actual: {habitacion.get_estado_display()}).'
            )

        reserva.estado = Reserva.Estado.EN_ESTADIA
        habitacion.estado = Habitacion.Estado.OCUPADA
        reserva.save(update_fields=['estado'])
        habitacion.save(update_fields=['estado'])
        return reserva


def hacer_checkout(reserva_id):
    with transaction.atomic():
        reserva, habitacion = _bloquear_reserva_y_habitacion(reserva_id)

        if reserva.estado != Reserva.Estado.EN_ESTADIA:
            raise OperacionNoPermitida(
                'El check-out solo se puede hacer en reservas En estadía.'
            )

        reserva.estado = Reserva.Estado.FINALIZADA
        habitacion.estado = Habitacion.Estado.LIMPIEZA
        reserva.save(update_fields=['estado'])
        habitacion.save(update_fields=['estado'])
        return reserva


def marcar_disponible(habitacion_id):
    with transaction.atomic():
        habitacion = Habitacion.objects.select_for_update().get(pk=habitacion_id)
        if habitacion.estado != Habitacion.Estado.LIMPIEZA:
            raise OperacionNoPermitida(
                'Solo una habitación en limpieza se puede marcar como disponible.'
            )
        habitacion.estado = Habitacion.Estado.DISPONIBLE
        habitacion.save(update_fields=['estado'])
        return habitacion
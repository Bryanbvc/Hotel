from collections import Counter

from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import ProtectedError
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView, DeleteView, FormView, ListView, UpdateView,
)

from .forms import (
    DisponibilidadForm, HabitacionForm, HuespedForm,
    ReservaForm, SeleccionHabitacionForm,
)
from .models import Habitacion, Huesped, Reserva
from .services import (
    HabitacionNoDisponible, OperacionNoPermitida, calcular_noches,
    calcular_total, cancelar_reserva, crear_reserva, hacer_checkin,
    hacer_checkout, habitaciones_disponibles, marcar_disponible,
)
import logging

registro = logging.getLogger('hotel.seguridad')

class FiltroPorEstadoMixin:
    """Filtra un listado por ?estado=..., aceptando solo estados válidos."""

    def get_queryset(self):
        consulta = super().get_queryset()
        estado = self.request.GET.get('estado')
        if estado in self.model.Estado.values:
            consulta = consulta.filter(estado=estado)
        return consulta

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['estados'] = self.model.Estado.choices
        contexto['estado_actual'] = self.request.GET.get('estado', '')
        return contexto


# ---------------------------------------------------------------
# Habitaciones
# ---------------------------------------------------------------

class HabitacionListView(FiltroPorEstadoMixin, ListView):
    model = Habitacion
    queryset = Habitacion.objects.select_related('tipo')
    template_name = 'hotel/habitacion_list.html'
    context_object_name = 'habitaciones'


class HabitacionCreateView(SuccessMessageMixin, CreateView):
    model = Habitacion
    form_class = HabitacionForm
    template_name = 'hotel/form_generico.html'
    success_url = reverse_lazy('habitacion_lista')
    success_message = 'Habitación registrada correctamente.'
    extra_context = {
        'titulo': 'Nueva habitación',
        'url_volver': reverse_lazy('habitacion_lista'),
    }


class HabitacionUpdateView(SuccessMessageMixin, UpdateView):
    model = Habitacion
    form_class = HabitacionForm
    template_name = 'hotel/form_generico.html'
    success_url = reverse_lazy('habitacion_lista')
    success_message = 'Habitación actualizada correctamente.'
    extra_context = {
        'titulo': 'Editar habitación',
        'url_volver': reverse_lazy('habitacion_lista'),
    }


class HabitacionDeleteView(DeleteView):
    model = Habitacion
    template_name = 'hotel/habitacion_confirm_delete.html'
    success_url = reverse_lazy('habitacion_lista')

    def form_valid(self, form):
        try:
            respuesta = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                'No se puede eliminar: la habitación tiene reservas asociadas.',
            )
            return redirect('habitacion_lista')
        messages.success(self.request, 'Habitación eliminada correctamente.')
        return respuesta


# ---------------------------------------------------------------
# Huéspedes
# ---------------------------------------------------------------

class HuespedListView(ListView):
    model = Huesped
    template_name = 'hotel/huesped_list.html'
    context_object_name = 'huespedes'


class HuespedCreateView(SuccessMessageMixin, CreateView):
    model = Huesped
    form_class = HuespedForm
    template_name = 'hotel/form_generico.html'
    success_url = reverse_lazy('huesped_lista')
    success_message = 'Huésped registrado correctamente.'
    extra_context = {
        'titulo': 'Nuevo huésped',
        'url_volver': reverse_lazy('huesped_lista'),
    }


class HuespedUpdateView(SuccessMessageMixin, UpdateView):
    model = Huesped
    form_class = HuespedForm
    template_name = 'hotel/form_generico.html'
    success_url = reverse_lazy('huesped_lista')
    success_message = 'Huésped actualizado correctamente.'
    extra_context = {
        'titulo': 'Editar huésped',
        'url_volver': reverse_lazy('huesped_lista'),
    }


# ---------------------------------------------------------------
# Disponibilidad y reservas
# ---------------------------------------------------------------

def disponibilidad(request):
    form = DisponibilidadForm(request.GET or None)
    contexto = {'form': form, 'resultados': None}

    if form.is_valid():
        entrada = form.cleaned_data['fecha_entrada']
        salida = form.cleaned_data['fecha_salida']
        personas = form.cleaned_data['personas']
        contexto['resultados'] = [
            {'habitacion': h, 'total': calcular_total(h, entrada, salida)}
            for h in habitaciones_disponibles(entrada, salida, personas)
        ]
        contexto.update(
            entrada=entrada, salida=salida,
            noches=calcular_noches(entrada, salida),
        )

    return render(request, 'hotel/disponibilidad.html', contexto)


class ReservaListView(FiltroPorEstadoMixin, ListView):
    model = Reserva
    queryset = Reserva.objects.select_related('huesped', 'habitacion__tipo')
    template_name = 'hotel/reserva_list.html'
    context_object_name = 'reservas'


class ReservaCreateView(FormView):
    template_name = 'hotel/reserva_form.html'
    form_class = ReservaForm
    success_url = reverse_lazy('reserva_lista')
    extra_context = {
        'titulo': 'Nueva reserva',
        'url_volver': reverse_lazy('disponibilidad'),
    }

    def dispatch(self, request, *args, **kwargs):
        # La habitación y las fechas llegan por la URL: se validan siempre
        seleccion = SeleccionHabitacionForm(request.GET)
        if not seleccion.is_valid():
            messages.error(
                request,
                'Elige una habitación y fechas válidas desde la consulta de disponibilidad.',
            )
            return redirect('disponibilidad')
        self.habitacion = seleccion.cleaned_data['habitacion']
        self.entrada = seleccion.cleaned_data['fecha_entrada']
        self.salida = seleccion.cleaned_data['fecha_salida']
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            habitacion=self.habitacion,
            entrada=self.entrada,
            salida=self.salida,
            noches=calcular_noches(self.entrada, self.salida),
            total=calcular_total(self.habitacion, self.entrada, self.salida),
        )
        return contexto

    def form_valid(self, form):
        try:
            reserva = crear_reserva(
                form.cleaned_data['huesped'], self.habitacion,
                self.entrada, self.salida,
            )
        except HabitacionNoDisponible as error:
            form.add_error(None, str(error))
            return self.form_invalid(form)
            registro.info('Reserva #%s creada por %r', reserva.pk, self.request.user.get_username())
        messages.success(self.request, f'Reserva #{reserva.pk} creada correctamente.')
        return super().form_valid(form)

    # ---------------------------------------------------------------
# Tablero y acciones: cancelar, check-in, check-out
# ---------------------------------------------------------------

COLOR_ESTADO_HABITACION = {
    'disponible': 'success',
    'ocupada': 'danger',
    'limpieza': 'warning',
    'mantencion': 'secondary',
}


def tablero(request):
    habitaciones = list(Habitacion.objects.select_related('tipo'))
    en_estadia = {
        r.habitacion_id: r
        for r in Reserva.objects.filter(
            estado=Reserva.Estado.EN_ESTADIA
        ).select_related('huesped')
    }
    for h in habitaciones:
        h.color = COLOR_ESTADO_HABITACION.get(h.estado, 'secondary')
        h.reserva_actual = en_estadia.get(h.pk)

    conteo = Counter(h.estado for h in habitaciones)
    resumen = [
        (etiqueta, conteo[valor], COLOR_ESTADO_HABITACION[valor])
        for valor, etiqueta in Habitacion.Estado.choices
    ]
    return render(
        request, 'hotel/tablero.html',
        {'habitaciones': habitaciones, 'resumen': resumen},
    )


def _ejecutar(request, accion, objeto_id, mensaje_ok):
    """Ejecuta una acción de services.py y muestra el resultado como mensaje."""
    usuario = request.user.get_username()
    try:
        accion(objeto_id)
    except ObjectDoesNotExist:
        raise Http404
    except OperacionNoPermitida as error:
        registro.warning(
            '%s rechazada (id=%s) por %r: %s', accion.__name__, objeto_id, usuario, error
        )
        messages.error(request, str(error))
    else:
        registro.info('%s ejecutada (id=%s) por %r', accion.__name__, objeto_id, usuario)
        messages.success(request, mensaje_ok)


@require_POST
def reserva_cancelar(request, pk):
    _ejecutar(request, cancelar_reserva, pk, 'Reserva cancelada correctamente.')
    return redirect('reserva_lista')


@require_POST
def reserva_checkin(request, pk):
    _ejecutar(request, hacer_checkin, pk, 'Check-in realizado: la habitación quedó ocupada.')
    return redirect('reserva_lista')


@require_POST
def reserva_checkout(request, pk):
    _ejecutar(request, hacer_checkout, pk, 'Check-out realizado: la habitación quedó en limpieza.')
    return redirect('reserva_lista')


@require_POST
def habitacion_disponible(request, pk):
    _ejecutar(request, marcar_disponible, pk, 'La habitación quedó disponible.')
    return redirect('tablero')
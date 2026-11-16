from collections import Counter
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ObjectDoesNotExist,PermissionDenied
from django.contrib.auth import login
from django.db.models import ProtectedError,Q
from django.http import Http404
from django.shortcuts import redirect, render,get_object_or_404
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import (
    CreateView, DeleteView, FormView, ListView, UpdateView,DetailView,
)

from .forms import (
    DisponibilidadForm, HabitacionForm, HuespedForm,
    ReservaForm, SeleccionHabitacionForm,ModificarReservaForm,RegistroClienteForm,
)
from .models import Habitacion, Huesped, Reserva
from .services import (
    HabitacionNoDisponible, OperacionNoPermitida,RegistroNoPermitido, registrar_cliente,marcar_no_presentado, modificar_reserva, calcular_noches,
    calcular_total, cancelar_reserva, crear_reserva, hacer_checkin,
    hacer_checkout, habitaciones_disponibles, marcar_disponible,
)
import logging
registro = logging.getLogger('hotel.seguridad')
from .permisos import (
    SoloAdministradorMixin, SoloRecepcionMixin, es_recepcionista,
    solo_recepcion,
)
from .permisos import (
    SoloAdministradorMixin, SoloRecepcionMixin, es_cliente, es_recepcionista,
    recepcion_o_cliente, solo_cliente, solo_recepcion,
)

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

class HabitacionListView(SoloRecepcionMixin, FiltroPorEstadoMixin, ListView):
    model = Habitacion
    queryset = Habitacion.objects.select_related('tipo')
    template_name = 'hotel/habitacion_list.html'
    context_object_name = 'habitaciones'


class HabitacionCreateView(SoloRecepcionMixin, SuccessMessageMixin, CreateView):
    model = Habitacion
    form_class = HabitacionForm
    template_name = 'hotel/form_generico.html'
    success_url = reverse_lazy('habitacion_lista')
    success_message = 'Habitación registrada correctamente.'
    extra_context = {
        'titulo': 'Nueva habitación',
        'url_volver': reverse_lazy('habitacion_lista'),
    }


class HabitacionUpdateView(SoloRecepcionMixin, SuccessMessageMixin, UpdateView):
    model = Habitacion
    form_class = HabitacionForm
    template_name = 'hotel/form_generico.html'
    success_url = reverse_lazy('habitacion_lista')
    success_message = 'Habitación actualizada correctamente.'
    extra_context = {
        'titulo': 'Editar habitación',
        'url_volver': reverse_lazy('habitacion_lista'),
    }


class HabitacionDeleteView(SoloAdministradorMixin, DeleteView):
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

class HuespedListView(SoloRecepcionMixin, ListView):
    model = Huesped
    template_name = 'hotel/huesped_list.html'
    context_object_name = 'huespedes'

    def get_queryset(self):
        consulta = super().get_queryset()
        self.busqueda = self.request.GET.get('q', '').strip()[:100]
        # Cada palabra debe aparecer en el nombre, el apellido o el documento
        for palabra in self.busqueda.split():
            consulta = consulta.filter(
                Q(nombre__icontains=palabra)
                | Q(apellido__icontains=palabra)
                | Q(documento__icontains=palabra.replace('.', ''))
            )
        return consulta

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['busqueda'] = self.busqueda
        return contexto


class HuespedDetailView(SoloRecepcionMixin, DetailView):
    """Ficha del huésped con su historial de reservas."""
    model = Huesped
    template_name = 'hotel/huesped_detalle.html'
    context_object_name = 'huesped'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['reservas'] = self.object.reservas.select_related('habitacion__tipo')
        return contexto


class HuespedCreateView(SoloRecepcionMixin, SuccessMessageMixin, CreateView):
    model = Huesped
    form_class = HuespedForm
    template_name = 'hotel/form_generico.html'
    success_url = reverse_lazy('huesped_lista')
    success_message = 'Huésped registrado correctamente.'
    extra_context = {
        'titulo': 'Nuevo huésped',
        'url_volver': reverse_lazy('huesped_lista'),
    }


class HuespedUpdateView(SoloRecepcionMixin, SuccessMessageMixin, UpdateView):
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
@recepcion_o_cliente
def disponibilidad(request):
    form = DisponibilidadForm(request.GET or None)
    contexto = {'form': form, 'resultados': None}

    if form.is_valid():
        entrada = form.cleaned_data['fecha_entrada']
        salida = form.cleaned_data['fecha_salida']
        personas = form.cleaned_data['personas']
        tipo = form.cleaned_data['tipo']
        contexto['resultados'] = [
            {'habitacion': h, 'total': calcular_total(h, entrada, salida)}
            for h in habitaciones_disponibles(entrada, salida, personas, tipo)
        ]
        contexto.update(
            personas=personas, entrada=entrada, salida=salida,
            noches=calcular_noches(entrada, salida),
        )

    return render(request, 'hotel/disponibilidad.html', contexto)


class ReservaListView(SoloRecepcionMixin, FiltroPorEstadoMixin, ListView):
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
        if not es_recepcionista(request.user):
            return self.handle_no_permission()
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
        self.personas = seleccion.cleaned_data['personas']
        return super().dispatch(request, *args, **kwargs)

    def handle_no_permission(self):
      _denegar(self.request)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            habitacion=self.habitacion,
            entrada=self.entrada,
            salida=self.salida,
            personas=self.personas,
            noches=calcular_noches(self.entrada, self.salida),
            total=calcular_total(self.habitacion, self.entrada, self.salida),
        )
        return contexto

    def form_valid(self, form):
        try:
            reserva = crear_reserva(
                form.cleaned_data['huesped'], self.habitacion,
                self.entrada, self.salida,self.personas,
            )
        except HabitacionNoDisponible as error:
            form.add_error(None, str(error))
            return self.form_invalid(form)
        registro.info(
            'Reserva #%s creada por %r',
            reserva.pk, self.request.user.get_username(),
        )
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

@solo_recepcion
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

def _volver(request, destino_por_defecto):
    """Vuelve a la página de origen si es segura; si no, al destino por defecto."""
    siguiente = request.POST.get('next', '')
    if url_has_allowed_host_and_scheme(
        siguiente,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(siguiente)
    return redirect(destino_por_defecto)


@require_POST
@solo_recepcion
def reserva_cancelar(request, pk):
    _ejecutar(request, cancelar_reserva, pk, 'Reserva cancelada correctamente.')
    return _volver(request, 'reserva_lista')


@require_POST
@solo_recepcion
def reserva_checkin(request, pk):
    _ejecutar(request, hacer_checkin, pk, 'Check-in realizado: la habitación quedó ocupada.')
    return _volver(request, 'reserva_lista')


@require_POST
@solo_recepcion
def reserva_checkout(request, pk):
    _ejecutar(request, hacer_checkout, pk, 'Check-out realizado: la habitación quedó en limpieza.')
    return _volver(request, 'reserva_lista')


@require_POST
@solo_recepcion
def reserva_no_presentado(request, pk):
    _ejecutar(
        request, marcar_no_presentado, pk,
        'Reserva marcada como No presentado: la habitación quedó libre.',
    )
    return _volver(request, 'reserva_lista')


@require_POST
@solo_recepcion
def habitacion_disponible(request, pk):
    _ejecutar(request, marcar_disponible, pk, 'La habitación quedó disponible.')
    return _volver(request, 'tablero')


# ---------------------------------------------------------------
# Modificar reserva
# ---------------------------------------------------------------

class ReservaUpdateView(SoloRecepcionMixin, FormView):
    template_name = 'hotel/form_generico.html'
    form_class = ModificarReservaForm
    success_url = reverse_lazy('reserva_lista')

    @cached_property
    def reserva(self):
        # Se busca solo cuando se necesita, o sea, después de validar el permiso
        return get_object_or_404(
            Reserva.objects.select_related('huesped', 'habitacion__tipo'),
            pk=self.kwargs['pk'],
        )

    def get_initial(self):
        return {
            'fecha_entrada': self.reserva.fecha_entrada,
            'fecha_salida': self.reserva.fecha_salida,
            'habitacion': self.reserva.habitacion_id,
            'personas': self.reserva.numero_huespedes,
        }

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['titulo'] = (
            f'Modificar reserva #{self.reserva.pk} - {self.reserva.huesped}'
        )
        contexto['url_volver'] = reverse_lazy('reserva_lista')
        return contexto

    def form_valid(self, form):
        datos = form.cleaned_data
        usuario = self.request.user.get_username()
        try:
            modificar_reserva(
                self.reserva.pk, datos['habitacion'],
                datos['fecha_entrada'], datos['fecha_salida'], datos['personas'],
            )
        except ObjectDoesNotExist:
            raise Http404
        except (HabitacionNoDisponible, OperacionNoPermitida) as error:
            registro.warning(
                'modificar_reserva rechazada (id=%s) por %r: %s',
                self.reserva.pk, usuario, error,
            )
            form.add_error(None, str(error))
            return self.form_invalid(form)
        registro.info(
            'modificar_reserva ejecutada (id=%s) por %r', self.reserva.pk, usuario
        )
        messages.success(
            self.request, f'Reserva #{self.reserva.pk} modificada correctamente.'
        )
        return super().form_valid(form)


# ---------------------------------------------------------------
# Llegadas y salidas del día
# ---------------------------------------------------------------

@solo_recepcion
def llegadas_salidas(request):
    hoy = timezone.localdate()
    reservas = Reserva.objects.select_related('huesped', 'habitacion__tipo')
    contexto = {
        'hoy': hoy,
        'llegadas': reservas.filter(
            estado=Reserva.Estado.RESERVADA, fecha_entrada=hoy
        ),
        'salidas': reservas.filter(
            estado=Reserva.Estado.EN_ESTADIA, fecha_salida__lte=hoy
        ),
        # Debían llegar antes de hoy y no han hecho check-in
        'atrasadas': reservas.filter(
            estado=Reserva.Estado.RESERVADA, fecha_entrada__lt=hoy
        ),
    }
    return render(request, 'hotel/llegadas_salidas.html', contexto)
# ---------------------------------------------------------------
# Inicio según el rol
# ---------------------------------------------------------------

def inicio(request):
    """Cada perfil entra a su pantalla principal."""
    if es_recepcionista(request.user):
        return redirect('tablero')
    if es_cliente(request.user):
        return redirect('mis_reservas')
    raise PermissionDenied


# ---------------------------------------------------------------
# Perfil Cliente: registro, reservar y mis reservas
# ---------------------------------------------------------------

def _huesped_de(usuario):
    return Huesped.objects.filter(usuario=usuario).first()


class RegistroClienteView(FormView):
    template_name = 'hotel/registro.html'
    form_class = RegistroClienteForm
    success_url = reverse_lazy('inicio')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('inicio')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            usuario = registrar_cliente(form.cleaned_data)
        except RegistroNoPermitido as error:
            form.add_error(None, str(error))
            return self.form_invalid(form)
        registro.info('Cliente registrado: %r', usuario.get_username())
        login(self.request, usuario)
        messages.success(self.request, '¡Cuenta creada! Ya puedes reservar.')
        return super().form_valid(form)


@solo_cliente
def mis_reservas(request):
    huesped = _huesped_de(request.user)
    reservas = Reserva.objects.none()
    if huesped:
        # Solo las reservas del propio cliente
        reservas = Reserva.objects.filter(huesped=huesped).select_related(
            'habitacion__tipo'
        )
    return render(
        request, 'hotel/mis_reservas.html',
        {'huesped': huesped, 'reservas': reservas},
    )


@solo_cliente
def reserva_cliente_crear(request):
    """El cliente confirma una reserva a su propio nombre."""
    seleccion = SeleccionHabitacionForm(request.GET)
    if not seleccion.is_valid():
        messages.error(
            request,
            'Elige una habitación y fechas válidas desde la consulta de disponibilidad.',
        )
        return redirect('disponibilidad')
    habitacion = seleccion.cleaned_data['habitacion']
    entrada = seleccion.cleaned_data['fecha_entrada']
    salida = seleccion.cleaned_data['fecha_salida']
    personas = seleccion.cleaned_data['personas']

    # El huésped sale de la sesión, nunca de datos enviados por el navegador
    huesped = _huesped_de(request.user)
    if huesped is None:
        messages.error(request, 'Tu cuenta no tiene ficha de huésped. Contacta a recepción.')
        return redirect('mis_reservas')

    if request.method == 'POST':
        try:
            reserva = crear_reserva(huesped, habitacion, entrada, salida, personas)
        except HabitacionNoDisponible as error:
            messages.error(request, str(error))
            return redirect('disponibilidad')
        registro.info(
            'Reserva #%s creada por el cliente %r',
            reserva.pk, request.user.get_username(),
        )
        messages.success(request, f'Reserva #{reserva.pk} creada correctamente.')
        return redirect('mis_reservas')

    return render(request, 'hotel/reserva_cliente_confirmar.html', {
        'habitacion': habitacion, 'entrada': entrada, 'salida': salida,
        'personas': personas,
        'noches': calcular_noches(entrada, salida),
        'total': calcular_total(habitacion, entrada, salida),
    })


@require_POST
@solo_cliente
def mis_reservas_cancelar(request, pk):
    if not Reserva.objects.filter(pk=pk, huesped__usuario=request.user).exists():
        registro.warning(
            'Intento de cancelar una reserva ajena (id=%s) por %r',
            pk, request.user.get_username(),
        )
        raise Http404
    _ejecutar(request, cancelar_reserva, pk, 'Reserva cancelada correctamente.')
    return redirect('mis_reservas')
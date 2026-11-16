from django.contrib import admin

from .models import (
    Habitacion, Huesped, Notificacion, Reserva, Servicio, TipoHabitacion,
)


@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')


@admin.register(TipoHabitacion)
class TipoHabitacionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'capacidad', 'camas', 'tarifa_noche')
    filter_horizontal = ('servicios',)


@admin.register(Habitacion)
class HabitacionAdmin(admin.ModelAdmin):
    list_display = ('numero', 'tipo', 'piso', 'estado')
    list_filter = ('estado', 'tipo')
    search_fields = ('numero',)


@admin.register(Huesped)
class HuespedAdmin(admin.ModelAdmin):
    list_display = ('documento', 'tipo_documento', 'apellido', 'nombre', 'email', 'telefono')
    search_fields = ('documento', 'apellido', 'nombre')


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'huesped', 'habitacion',
        'fecha_entrada', 'fecha_salida', 'numero_huespedes', 'estado', 'total',
    )
    list_filter = ('estado',)
    date_hierarchy = 'fecha_entrada'


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ('asunto', 'destinatario', 'estado', 'creada_en')
    list_filter = ('estado',)
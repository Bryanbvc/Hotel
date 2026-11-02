from django.contrib import admin

from .models import Habitacion, Huesped, Reserva, TipoHabitacion


@admin.register(TipoHabitacion)
class TipoHabitacionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'capacidad', 'tarifa_noche')


@admin.register(Habitacion)
class HabitacionAdmin(admin.ModelAdmin):
    list_display = ('numero', 'tipo', 'estado')
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
        'fecha_entrada', 'fecha_salida', 'estado', 'total',
    )
    list_filter = ('estado',)
    date_hierarchy = 'fecha_entrada'
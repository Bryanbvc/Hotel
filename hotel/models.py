from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.conf import settings
from .validators import (
    normalizar_documento,
    validar_documento,
    validar_nombre,
    validar_telefono,
)
class Servicio(models.Model):
    """Servicio que ofrece el hotel (WiFi, desayuno, etc.)."""
    nombre = models.CharField(max_length=60, unique=True)
    descripcion = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

class TipoHabitacion(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True)
    capacidad = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    tarifa_noche = models.DecimalField(
        max_digits=10, decimal_places=0, validators=[MinValueValidator(1)]
    )
    camas = models.PositiveSmallIntegerField(
        'número de camas', default=1, validators=[MinValueValidator(1)]
    )
    servicios = models.ManyToManyField(
        Servicio, blank=True, related_name='tipos_habitacion'
    )

    class Meta:
        verbose_name = 'tipo de habitación'
        verbose_name_plural = 'tipos de habitación'

    def __str__(self):
        return self.nombre


class Habitacion(models.Model):
    class Estado(models.TextChoices):
        DISPONIBLE = 'disponible', 'Disponible'
        OCUPADA = 'ocupada', 'Ocupada'
        LIMPIEZA = 'limpieza', 'En limpieza'
        MANTENCION = 'mantencion', 'En mantención'

    numero = models.CharField(max_length=10, unique=True)
    tipo = models.ForeignKey(
        TipoHabitacion, on_delete=models.PROTECT, related_name='habitaciones'
    )
    piso = models.PositiveSmallIntegerField(default=1)
    estado = models.CharField(
        max_length=15, choices=Estado.choices, default=Estado.DISPONIBLE
    )

    class Meta:
        verbose_name = 'habitación'
        verbose_name_plural = 'habitaciones'
        ordering = ['numero']

    def __str__(self):
        return f'Habitación {self.numero}'


class Huesped(models.Model):
    class TipoDocumento(models.TextChoices):
        RUT = 'rut', 'RUT'
        PASAPORTE = 'pasaporte', 'Pasaporte'

    tipo_documento = models.CharField(
        'tipo de documento', max_length=10,
        choices=TipoDocumento.choices, default=TipoDocumento.RUT,
    )
    documento = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=100, validators=[validar_nombre])
    apellido = models.CharField(max_length=100, validators=[validar_nombre])
    email = models.EmailField('correo electrónico', blank=True)
    telefono = models.CharField(
        'teléfono', max_length=20, blank=True, validators=[validar_telefono]
    )
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='huesped',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'huésped'
        verbose_name_plural = 'huéspedes'
        ordering = ['apellido', 'nombre']

    def __str__(self):
        return f'{self.nombre} {self.apellido} ({self.documento})'

    def clean(self):
        super().clean()
        self.documento = normalizar_documento(self.tipo_documento, self.documento)
        if self.documento:
            try:
                validar_documento(self.tipo_documento, self.documento)
            except ValidationError as error:
                raise ValidationError({'documento': error.messages})


class Reserva(models.Model):
    class Estado(models.TextChoices):
        RESERVADA = 'reservada', 'Reservada'
        EN_ESTADIA = 'en_estadia', 'En estadía'
        FINALIZADA = 'finalizada', 'Finalizada'
        CANCELADA = 'cancelada', 'Cancelada'
        NO_PRESENTADO = 'no_presentado', 'No presentado'

    huesped = models.ForeignKey(
        Huesped, on_delete=models.PROTECT, related_name='reservas'
    )
    habitacion = models.ForeignKey(
        Habitacion, on_delete=models.PROTECT, related_name='reservas'
    )
    fecha_entrada = models.DateField()
    fecha_salida = models.DateField()
    estado = models.CharField(
        max_length=15, choices=Estado.choices, default=Estado.RESERVADA
    )
    numero_huespedes = models.PositiveSmallIntegerField(
        'número de huéspedes', default=1, validators=[MinValueValidator(1)]
    )
    total = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creada_en']
        constraints = [
            models.CheckConstraint(
                condition=Q(fecha_salida__gt=F('fecha_entrada')),
                name='salida_posterior_a_entrada',
            )
        ]

    def __str__(self):
        return f'Reserva #{self.pk} - {self.habitacion} ({self.fecha_entrada} a {self.fecha_salida})'

class Notificacion(models.Model):
    """Registro de cada correo enviado al huésped (confirmaciones, etc.)."""

    class Estado(models.TextChoices):
        ENVIADA = 'enviada', 'Enviada'
        FALLIDA = 'fallida', 'Fallida'

    reserva = models.ForeignKey(
        Reserva, on_delete=models.CASCADE, related_name='notificaciones'
    )
    destinatario = models.EmailField()
    asunto = models.CharField(max_length=150)
    mensaje = models.TextField()
    estado = models.CharField(max_length=10, choices=Estado.choices)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'notificación'
        verbose_name_plural = 'notificaciones'
        ordering = ['-creada_en']

    def __str__(self):
        return f'{self.asunto} -> {self.destinatario}'


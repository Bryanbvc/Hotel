from django import forms
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import Habitacion, Huesped, TipoHabitacion
from .validators import (
    normalizar_documento, validar_documento, validar_nombre, validar_telefono,
)
from .models import Habitacion, Huesped
from .models import Habitacion, Huesped, TipoHabitacion


class BootstrapFormMixin:
    """Aplica las clases de Bootstrap a todos los campos del formulario."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo.widget, forms.Select):
                campo.widget.attrs['class'] = 'form-select'
            else:
                campo.widget.attrs['class'] = 'form-control'


class HabitacionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Habitacion
        fields = ['numero', 'tipo', 'piso', 'estado']

    def clean_numero(self):
        numero = self.cleaned_data['numero']
        if not numero.isalnum():
            raise forms.ValidationError(
                'El número solo puede contener letras y dígitos.'
            )
        return numero


class HuespedForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Huesped
        fields = [
            'tipo_documento', 'documento', 'nombre',
            'apellido', 'email', 'telefono',
        ]
        help_texts = {
            'documento': 'RUT (con o sin puntos) o número de pasaporte.',
        }


class RangoFechasForm(BootstrapFormMixin, forms.Form):
    """Base para los formularios que trabajan con un rango de fechas."""

    fecha_entrada = forms.DateField(
        label='Fecha de entrada',
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )
    fecha_salida = forms.DateField(
        label='Fecha de salida',
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )

    def clean(self):
        datos = super().clean()
        entrada = datos.get('fecha_entrada')
        salida = datos.get('fecha_salida')
        if entrada and salida:
            if entrada < timezone.localdate():
                self.add_error(
                    'fecha_entrada', 'La fecha de entrada no puede ser anterior a hoy.'
                )
            if salida <= entrada:
                self.add_error(
                    'fecha_salida', 'La fecha de salida debe ser posterior a la de entrada.'
                )
        return datos


class DisponibilidadForm(RangoFechasForm):
    personas = forms.IntegerField(
        label='Personas', min_value=1, max_value=20, initial=1
    )
    tipo = forms.ModelChoiceField(
        queryset=TipoHabitacion.objects.all(),
        label='Tipo de habitación',
        required=False,
        empty_label='Todos los tipos',
    )


class SeleccionHabitacionForm(RangoFechasForm):
    """Valida los datos que llegan por la URL al elegir una habitación."""

    habitacion = forms.ModelChoiceField(
        queryset=Habitacion.objects.select_related('tipo')
    )
    personas = forms.IntegerField(min_value=1, max_value=20)

class ModificarReservaForm(RangoFechasForm):
    """Cambia fechas, habitación y número de personas de una reserva."""

    habitacion = forms.ModelChoiceField(
        queryset=Habitacion.objects.select_related('tipo'),
        label='Habitación',
    )
    personas = forms.IntegerField(label='Personas', min_value=1, max_value=20)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['habitacion'].label_from_instance = lambda h: (
            f'{h.numero} - {h.tipo.nombre} (hasta {h.tipo.capacidad} personas)'
        )

class ReservaForm(BootstrapFormMixin, forms.Form):
    huesped = forms.ModelChoiceField(
        queryset=Huesped.objects.all(),
        label='Huésped',
        empty_label='Selecciona un huésped',
    )

class LoginForm(BootstrapFormMixin, AuthenticationForm):
    """Formulario de inicio de sesión de Django, con estilo Bootstrap."""

class RegistroClienteForm(BootstrapFormMixin, UserCreationForm):
    """Registro público de clientes: crea la cuenta y su ficha de huésped."""

    first_name = forms.CharField(
        label='Nombre', max_length=100, validators=[validar_nombre]
    )
    last_name = forms.CharField(
        label='Apellido', max_length=100, validators=[validar_nombre]
    )
    email = forms.EmailField(label='Correo electrónico')
    tipo_documento = forms.ChoiceField(
        label='Tipo de documento', choices=Huesped.TipoDocumento.choices
    )
    documento = forms.CharField(
        label='Documento', max_length=20,
        help_text='RUT (con o sin puntos) o número de pasaporte.',
    )
    telefono = forms.CharField(
        label='Teléfono', max_length=20, required=False,
        validators=[validar_telefono],
    )

    field_order = [
        'username', 'first_name', 'last_name', 'email',
        'tipo_documento', 'documento', 'telefono',
        'password1', 'password2',
    ]

    def clean_email(self):
        email = self.cleaned_data['email']
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Ya existe una cuenta con ese correo.')
        return email

    def clean(self):
        datos = super().clean()
        tipo = datos.get('tipo_documento')
        documento = datos.get('documento')
        if tipo and documento:
            documento = normalizar_documento(tipo, documento)
            try:
                validar_documento(tipo, documento)
            except forms.ValidationError as error:
                self.add_error('documento', error)
            else:
                datos['documento'] = documento
        return datos    
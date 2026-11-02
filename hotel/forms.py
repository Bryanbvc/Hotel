from django import forms
from django.utils import timezone
from django.contrib.auth.forms import AuthenticationForm
from .models import Habitacion, Huesped


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
        fields = ['numero', 'tipo', 'estado']

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


class SeleccionHabitacionForm(RangoFechasForm):
    """Valida los datos que llegan por la URL al elegir una habitación."""

    habitacion = forms.ModelChoiceField(
        queryset=Habitacion.objects.select_related('tipo')
    )


class ReservaForm(BootstrapFormMixin, forms.Form):
    huesped = forms.ModelChoiceField(
        queryset=Huesped.objects.all(),
        label='Huésped',
        empty_label='Selecciona un huésped',
    )

class LoginForm(BootstrapFormMixin, AuthenticationForm):
    """Formulario de inicio de sesión de Django, con estilo Bootstrap."""
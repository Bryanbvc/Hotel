import re

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

# Nombres: solo letras, con espacios, guiones o apóstrofes entre palabras
validar_nombre = RegexValidator(
    regex=r"^[^\W\d_]+(?:[ '\-][^\W\d_]+)*$",
    message='Solo se permiten letras, espacios, guiones y apóstrofes.',
)

# Teléfono: "+" opcional, dígitos, espacios y guiones
validar_telefono = RegexValidator(
    regex=r'^\+?[0-9][0-9 \-]{6,18}[0-9]$',
    message='Ingresa un teléfono válido, por ejemplo +56 9 1234 5678.',
)


def normalizar_rut(valor):
    """Quita puntos y espacios, pone mayúscula y agrega el guion: 12345678-5."""
    rut = re.sub(r'[.\s]', '', valor or '').upper()
    if len(rut) > 1 and '-' not in rut:
        rut = f'{rut[:-1]}-{rut[-1]}'
    return rut


def calcular_dv(cuerpo):
    """Calcula el dígito verificador con el método módulo 11."""
    suma = 0
    multiplicador = 2
    for digito in reversed(cuerpo):
        suma += int(digito) * multiplicador
        multiplicador = 2 if multiplicador == 7 else multiplicador + 1
    resultado = 11 - (suma % 11)
    if resultado == 11:
        return '0'
    if resultado == 10:
        return 'K'
    return str(resultado)


def validar_rut(valor):
    rut = normalizar_rut(valor)
    if not re.fullmatch(r'[0-9]{7,8}-[0-9K]', rut):
        raise ValidationError('Ingresa un RUT válido, por ejemplo 12.345.678-5.')
    cuerpo, dv = rut.split('-')
    if calcular_dv(cuerpo) != dv:
        raise ValidationError('El dígito verificador del RUT no es correcto.')


def normalizar_documento(tipo, valor):
    valor = (valor or '').strip()
    if tipo == 'rut':
        return normalizar_rut(valor)
    return re.sub(r'\s', '', valor).upper()


def validar_documento(tipo, valor):
    if tipo == 'rut':
        validar_rut(valor)
    elif not re.fullmatch(r'[A-Z0-9]{5,20}', valor):
        raise ValidationError(
            'El pasaporte debe tener entre 5 y 20 letras o números, sin símbolos.'
        )
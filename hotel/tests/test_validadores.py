from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from hotel.validators import (
    calcular_dv, normalizar_documento, validar_documento, validar_nombre,
    validar_rut, validar_telefono,
)


class ValidadoresTest(SimpleTestCase):

    def test_v01_rut_valido_con_y_sin_formato(self):
        """V-01 Un RUT correcto se acepta con puntos, sin puntos y sin guion."""
        for rut in ['12.345.678-5', '12345678-5', '123456785']:
            validar_rut(rut)

    def test_v02_rut_con_digito_verificador_k(self):
        """V-02 El dígito verificador K se calcula y se acepta en minúscula."""
        self.assertEqual(calcular_dv('10000013'), 'K')
        validar_rut('10000013-K')
        validar_rut('10.000.013-k')

    def test_v03_rut_con_digito_incorrecto_se_rechaza(self):
        """V-03 Un RUT con dígito verificador equivocado se rechaza."""
        with self.assertRaises(ValidationError):
            validar_rut('12345678-9')

    def test_v04_rut_con_formato_invalido_se_rechaza(self):
        """V-04 Textos que no son RUT se rechazan."""
        for rut in ['', 'abc', '1-9', '123456789012-3', "12345678-5'; DROP TABLE"]:
            with self.assertRaises(ValidationError, msg=rut):
                validar_rut(rut)

    def test_v05_normaliza_rut(self):
        """V-05 El RUT se guarda siempre como 12345678-5."""
        self.assertEqual(normalizar_documento('rut', ' 12.345.678-5 '), '12345678-5')
        self.assertEqual(normalizar_documento('rut', '123456785'), '12345678-5')

    def test_v06_pasaporte(self):
        """V-06 El pasaporte acepta letras y números, y rechaza símbolos."""
        validar_documento('pasaporte', normalizar_documento('pasaporte', 'ab 123456'))
        with self.assertRaises(ValidationError):
            validar_documento('pasaporte', 'AB-123!')

    def test_v07_nombres(self):
        """V-07 Los nombres aceptan tildes y guiones, y rechazan números y etiquetas HTML."""
        for nombre in ['José', "O'Higgins", 'Ana María', 'Pérez-Soto']:
            validar_nombre(nombre)
        for nombre in ['<script>', 'Ana2', '', '--']:
            with self.assertRaises(ValidationError, msg=nombre):
                validar_nombre(nombre)

    def test_v08_telefonos(self):
        """V-08 Teléfonos válidos se aceptan y los inválidos se rechazan."""
        for telefono in ['+56 9 1234 5678', '912345678', '22-123-4567']:
            validar_telefono(telefono)
        for telefono in ['abc', '12', '+56 9 12; DROP']:
            with self.assertRaises(ValidationError, msg=telefono):
                validar_telefono(telefono)

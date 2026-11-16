from django.contrib.auth.hashers import check_password
from django.test import Client
from django.urls import reverse

from hotel.models import Habitacion, Huesped, Reserva

from .base import BaseTest

URLS_DE_PERSONAL = [
    'tablero', 'habitacion_lista', 'huesped_lista', 'reserva_lista',
    'disponibilidad', 'llegadas_salidas',
]


class AutenticacionTest(BaseTest):

    def test_a01_anonimo_es_enviado_al_login(self):
        """A-01 Sin sesión, cualquier página del sistema redirige al login."""
        for nombre in URLS_DE_PERSONAL + ['inicio', 'mis_reservas']:
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 302, nombre)
            self.assertIn('/login/', r.url, nombre)

    def test_a02_login_correcto(self):
        """A-02 Con credenciales correctas se inicia sesión."""
        r = self.client.post(reverse('login'), {'username': 'recepcion', 'password': 'Clave-Segura-123'})
        self.assertEqual(r.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)

    def test_a03_login_incorrecto_no_inicia_sesion(self):
        """A-03 Con contraseña incorrecta no se inicia sesión."""
        r = self.client.post(reverse('login'), {'username': 'recepcion', 'password': 'mala'})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_a04_login_incorrecto_queda_en_el_log(self):
        """A-04 Un intento de login fallido queda registrado en el log de seguridad."""
        with self.assertLogs('hotel.seguridad') as registro:
            self.client.post(reverse('login'), {'username': 'recepcion', 'password': 'mala'})
        self.assertTrue(any('recepcion' in linea for linea in registro.output))

    def test_a05_contrasena_guardada_con_hash(self):
        """A-05 Las contraseñas no se guardan en texto plano."""
        self.assertNotEqual(self.recepcion.password, 'Clave-Segura-123')
        self.assertTrue(check_password('Clave-Segura-123', self.recepcion.password))

    def test_a06_cookie_de_sesion_httponly(self):
        """A-06 La cookie de sesión no es accesible desde JavaScript (HttpOnly)."""
        r = self.client.post(reverse('login'), {'username': 'recepcion', 'password': 'Clave-Segura-123'})
        self.assertTrue(r.cookies['sessionid']['httponly'])

    def test_a07_logout_cierra_la_sesion(self):
        """A-07 Cerrar sesión elimina la sesión del usuario."""
        self.client.force_login(self.recepcion)
        self.client.post(reverse('logout'))
        self.assertNotIn('_auth_user_id', self.client.session)


class ControlDeAccesoTest(BaseTest):

    def test_c01_recepcionista_accede_a_sus_pantallas(self):
        """C-01 El recepcionista entra a todas las pantallas del personal."""
        self.client.force_login(self.recepcion)
        for nombre in URLS_DE_PERSONAL:
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 200, nombre)

    def test_c02_usuario_sin_rol_recibe_403(self):
        """C-02 Un usuario sin rol recibe acceso denegado en todo el sistema."""
        self.client.force_login(self.sin_rol)
        for nombre in URLS_DE_PERSONAL + ['inicio', 'mis_reservas']:
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 403, nombre)

    def test_c03_acceso_denegado_queda_en_el_log(self):
        """C-03 Cada acceso denegado queda registrado con el usuario y la ruta."""
        self.client.force_login(self.sin_rol)
        with self.assertLogs('hotel.seguridad', 'WARNING') as registro:
            self.client.get(reverse('tablero'))
        self.assertIn('sinrol', registro.output[0])
        self.assertIn('/tablero/', registro.output[0])

    def test_c04_recepcionista_no_elimina_habitaciones(self):
        """C-04 El recepcionista no puede eliminar habitaciones (solo el administrador)."""
        self.client.force_login(self.recepcion)
        r = self.client.post(reverse('habitacion_eliminar', args=[self.h102.pk]))
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Habitacion.objects.filter(pk=self.h102.pk).exists())

    def test_c05_administrador_elimina_habitacion_sin_reservas(self):
        """C-05 El administrador puede eliminar una habitación sin reservas."""
        self.client.force_login(self.admin)
        self.client.post(reverse('habitacion_eliminar', args=[self.h102.pk]))
        self.assertFalse(Habitacion.objects.filter(pk=self.h102.pk).exists())

    def test_c06_no_se_elimina_habitacion_con_reservas(self):
        """C-06 Una habitación con reservas no se puede eliminar (integridad de datos)."""
        Reserva.objects.create(huesped=self.ana, habitacion=self.h101,
                               fecha_entrada=self.dia(1), fecha_salida=self.dia(2), total=1)
        self.client.force_login(self.admin)
        self.client.post(reverse('habitacion_eliminar', args=[self.h101.pk]))
        self.assertTrue(Habitacion.objects.filter(pk=self.h101.pk).exists())

    def test_c07_inicio_segun_el_rol(self):
        """C-07 Cada perfil entra a su pantalla principal."""
        self.client.force_login(self.recepcion)
        self.assertRedirects(self.client.get(reverse('inicio')), reverse('tablero'),
                             fetch_redirect_response=False)
        otro = Client(); otro.force_login(self._usuario('cli', 'Cliente'))
        self.assertRedirects(otro.get(reverse('inicio')), reverse('mis_reservas'),
                             fetch_redirect_response=False)

    def test_c08_menu_no_muestra_opciones_de_otros_roles(self):
        """C-08 El recepcionista no ve el botón Eliminar y el administrador sí."""
        self.client.force_login(self.recepcion)
        self.assertNotContains(self.client.get(reverse('habitacion_lista')), 'Eliminar')
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('habitacion_lista')), 'Eliminar')


class ProteccionesWebTest(BaseTest):

    def setUp(self):
        self.client.force_login(self.recepcion)
        self.reserva = Reserva.objects.create(
            huesped=self.ana, habitacion=self.h101,
            fecha_entrada=self.dia(0), fecha_salida=self.dia(2), total=1)

    def test_w01_acciones_de_cambio_solo_por_post(self):
        """W-01 Check-in, cancelar y no presentado no se ejecutan por GET."""
        for nombre in ['reserva_checkin', 'reserva_cancelar', 'reserva_checkout', 'reserva_no_presentado']:
            r = self.client.get(reverse(nombre, args=[self.reserva.pk]))
            self.assertEqual(r.status_code, 405, nombre)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, 'reservada')

    def test_w02_csrf_bloquea_post_sin_token(self):
        """W-02 Un POST sin token CSRF es rechazado."""
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.recepcion)
        with self.assertLogs('django.security.csrf', 'WARNING'):
            r = cliente.post(reverse('reserva_cancelar', args=[self.reserva.pk]))
        self.assertEqual(r.status_code, 403)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, 'reservada')

    def test_w03_buscador_resiste_inyeccion_sql(self):
        """W-03 Un intento de inyección SQL en el buscador no devuelve datos."""
        r = self.client.get(reverse('huesped_lista'), {'q': "' OR 1=1 --"})
        self.assertEqual(len(r.context['huespedes']), 0)
        self.assertEqual(Huesped.objects.count(), 2)

    def test_w04_texto_html_se_escapa_en_pantalla(self):
        """W-04 El texto con etiquetas HTML se muestra escapado (protección XSS)."""
        Huesped.objects.create(documento='ZZ12345', tipo_documento='pasaporte',
                               nombre='<script>alert(1)</script>', apellido='X')
        r = self.client.get(reverse('huesped_lista'))
        self.assertNotContains(r, '<script>alert(1)</script>')
        self.assertContains(r, '&lt;script&gt;')

    def test_w05_no_hay_redireccion_abierta(self):
        """W-05 El parámetro next solo acepta direcciones del propio sitio."""
        for destino in ['https://sitio-malo.com/', '//sitio-malo.com']:
            r = self.client.post(reverse('reserva_no_presentado', args=[self.reserva.pk]), {'next': destino})
            self.assertEqual(r.url, reverse('reserva_lista'), destino)
        r = self.client.post(reverse('reserva_checkin', args=[self.reserva.pk]), {'next': reverse('llegadas_salidas')})
        self.assertEqual(r.url, reverse('llegadas_salidas'))

    def test_w06_cabeceras_de_seguridad(self):
        """W-06 Las respuestas incluyen cabeceras contra clickjacking y sniffing."""
        r = self.client.get(reverse('tablero'))
        self.assertIn(r['X-Frame-Options'], ('DENY', 'SAMEORIGIN'))
        self.assertEqual(r['X-Content-Type-Options'], 'nosniff')

    def test_w07_pagina_403_no_revela_detalles_internos(self):
        """W-07 La página de acceso denegado no muestra rutas ni código del sistema."""
        self.client.force_login(self.sin_rol)
        r = self.client.get(reverse('tablero'))
        self.assertContains(r, 'Acceso denegado', status_code=403)
        self.assertNotContains(r, 'Traceback', status_code=403)

    def test_w08_parametros_manipulados_no_causan_error_500(self):
        """W-08 Parámetros inválidos en la URL se rechazan sin errores del servidor."""
        for url in [reverse('reserva_crear') + '?habitacion=abc',
                    reverse('reserva_crear') + '?habitacion=99999&fecha_entrada=x',
                    reverse('disponibilidad') + '?fecha_entrada=2020-02-30']:
            self.assertLess(self.client.get(url).status_code, 500, url)
        self.assertEqual(self.client.get(reverse('reserva_modificar', args=[99999])).status_code, 404)

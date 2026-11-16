from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from hotel.models import Huesped, Reserva

from .base import BaseTest

CLAVE = 'Contr4sena!Fuerte'


def datos_registro(**cambios):
    datos = dict(
        username='cliente1', first_name='Carla', last_name='Rojas',
        email='carla@test.cl', tipo_documento='rut', documento='11.111.111-1',
        telefono='+56 9 1234 5678', password1=CLAVE, password2=CLAVE,
    )
    datos.update(cambios)
    return datos


class RegistroTest(BaseTest):

    def registrar(self, **cambios):
        return self.client.post(reverse('registro'), datos_registro(**cambios))

    def test_r01_registro_valido(self):
        """R-01 Un registro válido crea usuario, grupo Cliente y ficha de huésped vinculada."""
        r = self.registrar()
        usuario = User.objects.get(username='cliente1')
        self.assertEqual(r.status_code, 302)
        self.assertTrue(usuario.groups.filter(name='Cliente').exists())
        self.assertFalse(usuario.is_staff or usuario.is_superuser)
        self.assertEqual(Huesped.objects.get(documento='11111111-1').usuario, usuario)
        self.assertIn('_auth_user_id', self.client.session)

    def test_r02_contrasena_debil_se_rechaza(self):
        """R-02 Una contraseña débil no permite crear la cuenta."""
        r = self.registrar(password1='12345678', password2='12345678')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username='cliente1').exists())

    def test_r03_contrasenas_distintas_se_rechazan(self):
        """R-03 Si las dos contraseñas no coinciden no se crea la cuenta."""
        self.registrar(password2='otra-distinta')
        self.assertFalse(User.objects.filter(username='cliente1').exists())

    def test_r04_rut_invalido_se_rechaza(self):
        """R-04 Un RUT con dígito verificador incorrecto se rechaza."""
        r = self.registrar(documento='11.111.111-9')
        self.assertIn('documento', r.context['form'].errors)

    def test_r05_nombre_con_html_se_rechaza(self):
        """R-05 Un nombre con etiquetas HTML se rechaza."""
        r = self.registrar(first_name='<b>Carla</b>')
        self.assertIn('first_name', r.context['form'].errors)

    def test_r06_correo_duplicado_ignora_mayusculas(self):
        """R-06 No se permiten dos cuentas con el mismo correo (sin distinguir mayúsculas)."""
        self.registrar()
        otro = Client()
        r = otro.post(reverse('registro'), datos_registro(
            username='otra', email='CARLA@test.cl', documento='7.654.321-6'))
        self.assertIn('email', r.context['form'].errors)

    def test_r07_documento_ya_registrado_no_se_vincula_sin_correo_igual(self):
        """R-07 Un documento ya existente con otro correo no se puede reclamar."""
        r = self.registrar(documento='12345678-5', email='otro@test.cl')
        self.assertContains(r, 'Ya existe un huésped')
        self.assertFalse(User.objects.filter(username='cliente1').exists())
        self.assertIsNone(Huesped.objects.get(documento='12345678-5').usuario)

    def test_r08_vincula_ficha_de_recepcion_si_el_correo_coincide(self):
        """R-08 Si el correo coincide, la ficha creada por recepción se vincula a la cuenta."""
        self.registrar(documento='12345678-5', email='ANA@test.cl', first_name='Ana', last_name='Paz')
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.usuario.username, 'cliente1')

    def test_r09_usuario_con_sesion_no_ve_el_registro(self):
        """R-09 Quien ya inició sesión es redirigido fuera de la pantalla de registro."""
        self.client.force_login(self.recepcion)
        self.assertEqual(self.client.get(reverse('registro')).status_code, 302)


class PerfilClienteTest(BaseTest):

    def setUp(self):
        self.usuario = self._usuario('cliente1', 'Cliente')
        self.mia = Huesped.objects.create(
            documento='11111111-1', nombre='Carla', apellido='Rojas',
            email='carla@test.cl', usuario=self.usuario)
        self.client.force_login(self.usuario)

    def consulta(self, habitacion, entrada=3, salida=5, personas=1):
        return (f"?habitacion={habitacion.pk}&fecha_entrada={self.dia(entrada)}"
                f"&fecha_salida={self.dia(salida)}&personas={personas}")

    def test_p01_cliente_no_accede_a_pantallas_del_personal(self):
        """P-01 El cliente recibe acceso denegado en todas las pantallas de recepción."""
        for nombre in ['tablero', 'habitacion_lista', 'huesped_lista', 'reserva_lista', 'llegadas_salidas']:
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 403, nombre)

    def test_p02_cliente_no_usa_las_acciones_del_personal(self):
        """P-02 El cliente no puede ejecutar acciones de recepción por POST."""
        r = Reserva.objects.create(huesped=self.ana, habitacion=self.h101,
                                   fecha_entrada=self.dia(1), fecha_salida=self.dia(2), total=1)
        self.assertEqual(self.client.post(reverse('reserva_cancelar', args=[r.pk])).status_code, 403)
        r.refresh_from_db()
        self.assertEqual(r.estado, 'reservada')

    def test_p03_cliente_ve_la_disponibilidad_con_su_propio_enlace(self):
        """P-03 El cliente consulta disponibilidad y el botón Reservar usa su flujo propio."""
        r = self.client.get(reverse('disponibilidad'), {
            'fecha_entrada': self.dia(3), 'fecha_salida': self.dia(5), 'personas': 1})
        self.assertContains(r, '/reservar/?habitacion=')
        self.assertNotContains(r, '/reservas/nueva/')

    def test_p04_cliente_reserva_a_su_nombre_ignorando_otros_huespedes(self):
        """P-04 La reserva del cliente queda a su nombre aunque envíe otro huésped."""
        self.client.post(reverse('reserva_cliente') + self.consulta(self.h101), {'huesped': self.ana.pk})
        r = Reserva.objects.get()
        self.assertEqual(r.huesped, self.mia)

    def test_p05_cliente_no_supera_la_capacidad(self):
        """P-05 El cliente no puede reservar para más personas que la capacidad."""
        self.client.post(reverse('reserva_cliente') + self.consulta(self.h201, personas=2))
        self.assertEqual(Reserva.objects.count(), 0)

    def test_p06_datos_invalidos_en_la_url_vuelven_a_disponibilidad(self):
        """P-06 Parámetros inválidos al reservar redirigen sin crear nada."""
        r = self.client.get(reverse('reserva_cliente') + '?habitacion=99999')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Reserva.objects.count(), 0)

    def test_p07_mis_reservas_muestra_solo_las_propias(self):
        """P-07 Mis reservas no muestra reservas de otros huéspedes."""
        propia = Reserva.objects.create(huesped=self.mia, habitacion=self.h101,
                                        fecha_entrada=self.dia(1), fecha_salida=self.dia(2), total=1)
        ajena = Reserva.objects.create(huesped=self.ana, habitacion=self.h102,
                                       fecha_entrada=self.dia(1), fecha_salida=self.dia(2), total=1)
        ids = [r.pk for r in self.client.get(reverse('mis_reservas')).context['reservas']]
        self.assertEqual(ids, [propia.pk])
        self.assertNotIn(ajena.pk, ids)

    def test_p08_cliente_cancela_su_reserva(self):
        """P-08 El cliente puede cancelar su propia reserva."""
        r = Reserva.objects.create(huesped=self.mia, habitacion=self.h101,
                                   fecha_entrada=self.dia(1), fecha_salida=self.dia(2), total=1)
        self.client.post(reverse('mis_reservas_cancelar', args=[r.pk]))
        r.refresh_from_db()
        self.assertEqual(r.estado, 'cancelada')

    def test_p09_no_puede_cancelar_reservas_ajenas(self):
        """P-09 Cancelar la reserva de otro cliente da 404, no cambia nada y queda en el log."""
        ajena = Reserva.objects.create(huesped=self.ana, habitacion=self.h102,
                                       fecha_entrada=self.dia(1), fecha_salida=self.dia(2), total=1)
        with self.assertLogs('hotel.seguridad', 'WARNING') as registro:
            r = self.client.post(reverse('mis_reservas_cancelar', args=[ajena.pk]))
        self.assertEqual(r.status_code, 404)
        ajena.refresh_from_db()
        self.assertEqual(ajena.estado, 'reservada')
        self.assertIn('ajena', registro.output[0])

    def test_p10_cuenta_sin_ficha_de_huesped_no_puede_reservar(self):
        """P-10 Un cliente sin ficha de huésped recibe un aviso y no se crea la reserva."""
        self.mia.usuario = None
        self.mia.save()
        r = self.client.post(reverse('reserva_cliente') + self.consulta(self.h101))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Reserva.objects.count(), 0)

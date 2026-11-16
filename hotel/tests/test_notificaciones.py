from smtplib import SMTPException
from unittest import mock

from django.core import mail
from django.urls import reverse

from hotel import services as s
from hotel.models import Notificacion

from .base import BaseTest


class NotificacionesTest(BaseTest):
    """Los correos se envían al confirmar la transacción (on_commit)."""

    def crear(self, huesped=None):
        with self.captureOnCommitCallbacks(execute=True):
            return s.crear_reserva(huesped or self.ana, self.h101, self.dia(1), self.dia(3), 2)

    def test_n01_crear_reserva_envia_correo_y_lo_registra(self):
        """N-01 Al crear una reserva se envía un correo y se guarda como Enviada."""
        r = self.crear()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['ana@test.cl'])
        n = Notificacion.objects.get()
        self.assertEqual((n.reserva, n.estado), (r, 'enviada'))

    def test_n02_contenido_del_correo(self):
        """N-02 El correo trae habitación, fechas y total, pero no el documento del huésped."""
        self.crear()
        cuerpo = mail.outbox[0].body
        self.assertIn('101', cuerpo)
        self.assertIn('$100.000', cuerpo)
        self.assertNotIn('12345678', cuerpo)

    def test_n03_modificar_y_cancelar_tambien_notifican(self):
        """N-03 Modificar y cancelar una reserva envían su propio correo."""
        r = self.crear()
        with self.captureOnCommitCallbacks(execute=True):
            s.modificar_reserva(r.pk, self.h101, self.dia(1), self.dia(4), 2)
        with self.captureOnCommitCallbacks(execute=True):
            s.cancelar_reserva(r.pk)
        asuntos = [m.subject.lower() for m in mail.outbox]
        self.assertEqual(len(asuntos), 3)
        self.assertIn('modificada', asuntos[1])
        self.assertIn('cancelada', asuntos[2])

    def test_n04_huesped_sin_correo_no_bloquea_la_reserva(self):
        """N-04 Si el huésped no tiene correo, la reserva se crea y no se envía nada."""
        r = self.crear(huesped=self.luis)
        self.assertIsNotNone(r.pk)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Notificacion.objects.count(), 0)

    def test_n05_reserva_rechazada_no_envia_correo(self):
        """N-05 Si la reserva se rechaza por conflicto, no se envía ningún correo."""
        self.crear()
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(s.HabitacionNoDisponible):
                s.crear_reserva(self.luis, self.h101, self.dia(2), self.dia(4), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_n06_fallo_del_servidor_de_correo_no_rompe_la_reserva(self):
        """N-06 Si el servidor de correo falla, la reserva queda creada y el envío como Fallida."""
        with mock.patch('hotel.notificaciones.send_mail', side_effect=SMTPException('caído')):
            with self.assertLogs('hotel.seguridad', 'ERROR'):
                r = self.crear()
        self.assertIsNotNone(r.pk)
        self.assertEqual(Notificacion.objects.get().estado, 'fallida')

    def test_n07_crear_reserva_desde_pantalla_notifica(self):
        """N-07 Una reserva creada desde la pantalla de recepción también envía correo."""
        self.client.force_login(self.recepcion)
        url = (reverse('reserva_crear') + f'?habitacion={self.h102.pk}'
               f'&fecha_entrada={self.dia(1)}&fecha_salida={self.dia(2)}&personas=1')
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post(url, {'huesped': self.ana.pk})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

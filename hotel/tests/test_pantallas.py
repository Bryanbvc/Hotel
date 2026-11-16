from django.urls import reverse

from hotel.models import Habitacion, Huesped, Reserva

from .base import BaseTest


class _PantallasBase(BaseTest):
    def setUp(self):
        self.client.force_login(self.recepcion)

    def reserva(self, entrada, salida, habitacion=None, huesped=None, **extra):
        return Reserva.objects.create(
            huesped=huesped or self.ana, habitacion=habitacion or self.h101,
            fecha_entrada=self.dia(entrada), fecha_salida=self.dia(salida),
            total=100000, **extra)


class HabitacionesYHuespedesTest(_PantallasBase):

    def test_h01_registrar_habitacion(self):
        """H-01 Recepción registra una habitación nueva desde la pantalla."""
        r = self.client.post(reverse('habitacion_crear'), {
            'numero': '301', 'tipo': self.doble.pk, 'piso': 3, 'estado': 'disponible'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Habitacion.objects.filter(numero='301', piso=3).exists())

    def test_h02_numero_de_habitacion_duplicado_se_rechaza(self):
        """H-02 No se puede registrar dos veces el mismo número de habitación."""
        r = self.client.post(reverse('habitacion_crear'), {
            'numero': '101', 'tipo': self.doble.pk, 'piso': 1, 'estado': 'disponible'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Habitacion.objects.filter(numero='101').count(), 1)

    def test_h03_editar_habitacion(self):
        """H-03 Recepción edita el piso y el estado de una habitación."""
        self.client.post(reverse('habitacion_editar', args=[self.h102.pk]), {
            'numero': '102', 'tipo': self.doble.pk, 'piso': 4, 'estado': 'mantencion'})
        self.h102.refresh_from_db()
        self.assertEqual((self.h102.piso, self.h102.estado), (4, 'mantencion'))

    def test_g01_registrar_huesped_valido(self):
        """G-01 Recepción registra un huésped con RUT válido y se guarda normalizado."""
        r = self.client.post(reverse('huesped_crear'), {
            'tipo_documento': 'rut', 'documento': '11.111.111-1', 'nombre': 'Carla',
            'apellido': 'Rojas', 'email': 'carla@test.cl', 'telefono': '+56 9 1234 5678'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Huesped.objects.filter(documento='11111111-1').exists())

    def test_g02_huesped_con_rut_invalido_se_rechaza(self):
        """G-02 Un huésped con RUT inválido no se guarda."""
        r = self.client.post(reverse('huesped_crear'), {
            'tipo_documento': 'rut', 'documento': '11.111.111-9', 'nombre': 'Carla',
            'apellido': 'Rojas', 'email': '', 'telefono': ''})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Huesped.objects.filter(nombre='Carla').exists())

    def test_g03_huesped_duplicado_se_rechaza(self):
        """G-03 No se puede registrar dos veces el mismo documento."""
        r = self.client.post(reverse('huesped_crear'), {
            'tipo_documento': 'rut', 'documento': '12.345.678-5', 'nombre': 'Otra',
            'apellido': 'Persona', 'email': '', 'telefono': ''})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Huesped.objects.filter(documento='12345678-5').count(), 1)

    def test_g04_buscador_por_nombre_apellido_y_rut(self):
        """G-04 El buscador encuentra por nombre y apellido juntos, y por RUT con puntos."""
        r = self.client.get(reverse('huesped_lista'), {'q': 'ana paz'})
        self.assertEqual([h.nombre for h in r.context['huespedes']], ['Ana'])
        r = self.client.get(reverse('huesped_lista'), {'q': '9.876.543-3'})
        self.assertEqual([h.nombre for h in r.context['huespedes']], ['Luis'])

    def test_g05_buscador_sin_resultados(self):
        """G-05 Una búsqueda sin coincidencias muestra un aviso."""
        r = self.client.get(reverse('huesped_lista'), {'q': 'zzzz'})
        self.assertContains(r, 'Sin resultados')

    def test_g06_historial_del_huesped(self):
        """G-06 La ficha del huésped lista todas sus reservas."""
        self.reserva(1, 2); self.reserva(5, 6, estado='cancelada')
        self.reserva(1, 2, habitacion=self.h102, huesped=self.luis)
        r = self.client.get(reverse('huesped_detalle', args=[self.ana.pk]))
        self.assertEqual(len(r.context['reservas']), 2)


class OperacionDiariaTest(_PantallasBase):

    def test_o01_tablero_muestra_las_habitaciones(self):
        """O-01 El tablero muestra todas las habitaciones con su estado."""
        r = self.client.get(reverse('tablero'))
        for numero in ['101', '102', '201']:
            self.assertContains(r, numero)

    def test_o02_disponibilidad_por_pantalla(self):
        """O-02 La consulta de disponibilidad muestra habitaciones libres y oculta ocupadas."""
        self.reserva(1, 4, habitacion=self.h101)
        r = self.client.get(reverse('disponibilidad'), {
            'fecha_entrada': self.dia(2), 'fecha_salida': self.dia(3), 'personas': 1})
        numeros = [x['habitacion'].numero for x in r.context['resultados']]
        self.assertNotIn('101', numeros)
        self.assertIn('102', numeros)

    def test_o03_fechas_pasadas_se_rechazan_en_disponibilidad(self):
        """O-03 La consulta rechaza fechas anteriores a hoy y salidas antes de la entrada."""
        r = self.client.get(reverse('disponibilidad'), {
            'fecha_entrada': self.dia(-2), 'fecha_salida': self.dia(1), 'personas': 1})
        self.assertIsNone(r.context.get('resultados'))
        r = self.client.get(reverse('disponibilidad'), {
            'fecha_entrada': self.dia(3), 'fecha_salida': self.dia(2), 'personas': 1})
        self.assertIsNone(r.context.get('resultados'))

    def test_o04_crear_reserva_por_pantalla(self):
        """O-04 Recepción crea una reserva desde la consulta de disponibilidad."""
        url = (reverse('reserva_crear') + f'?habitacion={self.h101.pk}'
               f'&fecha_entrada={self.dia(1)}&fecha_salida={self.dia(3)}&personas=2')
        r = self.client.post(url, {'huesped': self.ana.pk})
        self.assertEqual(r.status_code, 302)
        reserva = Reserva.objects.get()
        self.assertEqual((reserva.total, reserva.numero_huespedes), (100000, 2))

    def test_o05_crear_reserva_en_fechas_ocupadas_muestra_error(self):
        """O-05 Reservar fechas ya ocupadas muestra el error y no crea nada."""
        self.reserva(1, 4)
        url = (reverse('reserva_crear') + f'?habitacion={self.h101.pk}'
               f'&fecha_entrada={self.dia(2)}&fecha_salida={self.dia(3)}&personas=1')
        r = self.client.post(url, {'huesped': self.luis.pk})
        self.assertContains(r, 'ya está reservada')
        self.assertEqual(Reserva.objects.count(), 1)

    def test_o06_modificar_reserva_por_pantalla(self):
        """O-06 Recepción modifica fechas y habitación de una reserva desde la pantalla."""
        r = self.reserva(1, 3)
        self.client.post(reverse('reserva_modificar', args=[r.pk]), {
            'fecha_entrada': self.dia(2), 'fecha_salida': self.dia(5),
            'habitacion': self.h102.pk, 'personas': 1})
        r.refresh_from_db()
        self.assertEqual((r.habitacion, r.total), (self.h102, 150000))

    def test_o07_modificar_con_conflicto_muestra_error(self):
        """O-07 Modificar hacia una habitación ocupada muestra el error y no cambia nada."""
        self.reserva(1, 3, habitacion=self.h102, huesped=self.luis)
        r = self.reserva(1, 3)
        resp = self.client.post(reverse('reserva_modificar', args=[r.pk]), {
            'fecha_entrada': self.dia(1), 'fecha_salida': self.dia(3),
            'habitacion': self.h102.pk, 'personas': 1})
        self.assertContains(resp, 'ya está reservada')
        r.refresh_from_db()
        self.assertEqual(r.habitacion, self.h101)

    def test_o08_pantalla_llegadas_y_salidas(self):
        """O-08 La pantalla Hoy separa llegadas de hoy, salidas de hoy y reservas vencidas."""
        self.reserva(0, 2)
        self.reserva(-3, 0, habitacion=self.h102, huesped=self.luis, estado='en_estadia')
        self.reserva(-2, 2, habitacion=self.h201, huesped=self.luis)
        r = self.client.get(reverse('llegadas_salidas'))
        self.assertEqual((len(r.context['llegadas']), len(r.context['salidas']),
                          len(r.context['atrasadas'])), (1, 1, 1))

    def test_o09_checkin_y_checkout_desde_la_pantalla_hoy(self):
        """O-09 Check-in y check-out desde Hoy funcionan y vuelven a esa pantalla."""
        r = self.reserva(0, 1)
        resp = self.client.post(reverse('reserva_checkin', args=[r.pk]), {'next': reverse('llegadas_salidas')})
        self.assertEqual(resp.url, reverse('llegadas_salidas'))
        self.h101.refresh_from_db()
        self.assertEqual(self.h101.estado, 'ocupada')
        self.client.post(reverse('reserva_checkout', args=[r.pk]))
        self.h101.refresh_from_db(); r.refresh_from_db()
        self.assertEqual((r.estado, self.h101.estado), ('finalizada', 'limpieza'))

    def test_o10_checkin_fuera_de_fecha_muestra_error_sin_cambios(self):
        """O-10 Un check-in no permitido muestra el motivo y no cambia ningún estado."""
        r = self.reserva(3, 5)
        resp = self.client.post(reverse('reserva_checkin', args=[r.pk]), follow=True)
        self.assertContains(resp, 'check-in se habilita')
        r.refresh_from_db(); self.h101.refresh_from_db()
        self.assertEqual((r.estado, self.h101.estado), ('reservada', 'disponible'))

    def test_o11_no_presentado_por_pantalla(self):
        """O-11 Recepción marca No presentado una reserva vencida y la habitación queda libre."""
        r = self.reserva(-1, 2)
        self.client.post(reverse('reserva_no_presentado', args=[r.pk]))
        r.refresh_from_db()
        self.assertEqual(r.estado, 'no_presentado')

    def test_o12_marcar_habitacion_disponible_tras_limpieza(self):
        """O-12 Una habitación En limpieza vuelve a Disponible desde el tablero."""
        Habitacion.objects.filter(pk=self.h101.pk).update(estado='limpieza')
        self.client.post(reverse('habitacion_disponible', args=[self.h101.pk]))
        self.h101.refresh_from_db()
        self.assertEqual(self.h101.estado, 'disponible')

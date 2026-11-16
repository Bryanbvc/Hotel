from hotel import services as s
from hotel.models import Habitacion, Reserva

from .base import BaseTest


class _Ayuda:
    def reserva(self, habitacion=None, entrada=1, salida=3, huesped=None, **extra):
        return Reserva.objects.create(
            huesped=huesped or self.ana,
            habitacion=habitacion or self.h101,
            fecha_entrada=self.dia(entrada),
            fecha_salida=self.dia(salida),
            total=extra.pop('total', 100000),
            **extra,
        )


class DisponibilidadTest(_Ayuda, BaseTest):

    def numeros(self, entrada, salida, **filtros):
        return [h.numero for h in s.habitaciones_disponibles(
            self.dia(entrada), self.dia(salida), **filtros)]

    def test_s01_habitacion_libre_aparece(self):
        """S-01 Sin reservas, todas las habitaciones aparecen disponibles."""
        self.assertEqual(sorted(self.numeros(1, 3)), ['101', '102', '201'])

    def test_s02_excluye_reserva_que_se_cruza(self):
        """S-02 Una habitación con reserva en esas fechas no aparece."""
        self.reserva(self.h101, 1, 4)
        self.assertNotIn('101', self.numeros(2, 3))

    def test_s03_salida_y_entrada_el_mismo_dia_no_chocan(self):
        """S-03 Si una reserva sale el día 3, otra puede entrar ese mismo día 3."""
        self.reserva(self.h101, 1, 3)
        self.assertIn('101', self.numeros(3, 5))

    def test_s04_filtra_por_capacidad(self):
        """S-04 Para 2 personas no se ofrece la habitación simple."""
        self.assertNotIn('201', self.numeros(1, 3, personas=2))

    def test_s05_filtra_por_tipo(self):
        """S-05 El filtro por tipo solo muestra habitaciones de ese tipo."""
        self.assertEqual(self.numeros(1, 3, tipo=self.simple), ['201'])

    def test_s06_excluye_mantencion(self):
        """S-06 Una habitación en mantención nunca se ofrece."""
        Habitacion.objects.filter(pk=self.h101.pk).update(estado='mantencion')
        self.assertNotIn('101', self.numeros(1, 3))

    def test_s07_canceladas_y_no_presentadas_no_bloquean(self):
        """S-07 Las reservas canceladas o no presentadas liberan la habitación."""
        self.reserva(self.h101, 1, 3, estado='cancelada')
        self.reserva(self.h102, 1, 3, estado='no_presentado')
        self.assertIn('101', self.numeros(1, 3))
        self.assertIn('102', self.numeros(1, 3))


class CrearReservaTest(_Ayuda, BaseTest):

    def crear(self, habitacion=None, entrada=1, salida=3, personas=1):
        return s.crear_reserva(self.ana, habitacion or self.h101,
                               self.dia(entrada), self.dia(salida), personas)

    def test_s08_calcula_total_y_guarda_datos(self):
        """S-08 La reserva guarda el total (noches x tarifa) y el número de huéspedes."""
        r = self.crear(entrada=1, salida=3, personas=2)
        self.assertEqual(r.total, 100000)
        self.assertEqual(r.numero_huespedes, 2)
        self.assertEqual(r.estado, 'reservada')

    def test_s09_rechaza_fechas_ocupadas(self):
        """S-09 No se puede reservar una habitación ya reservada en esas fechas."""
        self.crear(entrada=1, salida=4)
        with self.assertRaises(s.HabitacionNoDisponible):
            self.crear(entrada=3, salida=5)
        self.assertEqual(Reserva.objects.count(), 1)

    def test_s10_rechaza_mas_personas_que_la_capacidad(self):
        """S-10 No se aceptan más personas que la capacidad del tipo."""
        with self.assertRaises(s.HabitacionNoDisponible):
            self.crear(self.h201, personas=2)

    def test_s11_rechaza_habitacion_en_mantencion(self):
        """S-11 No se puede reservar una habitación en mantención."""
        Habitacion.objects.filter(pk=self.h101.pk).update(estado='mantencion')
        with self.assertRaises(s.HabitacionNoDisponible):
            self.crear()


class CancelarTest(_Ayuda, BaseTest):

    def test_s12_cancela_reserva_reservada(self):
        """S-12 Una reserva en estado Reservada se puede cancelar."""
        r = self.reserva()
        s.cancelar_reserva(r.pk)
        r.refresh_from_db()
        self.assertEqual(r.estado, 'cancelada')

    def test_s13_no_cancela_si_ya_esta_en_estadia(self):
        """S-13 Una reserva En estadía no se puede cancelar."""
        r = self.reserva(estado='en_estadia')
        with self.assertRaises(s.OperacionNoPermitida):
            s.cancelar_reserva(r.pk)


class CheckInOutTest(_Ayuda, BaseTest):

    def test_s14_checkin_ocupa_la_habitacion(self):
        """S-14 El check-in deja la reserva En estadía y la habitación Ocupada."""
        r = self.reserva(entrada=0, salida=2)
        s.hacer_checkin(r.pk)
        r.refresh_from_db(); self.h101.refresh_from_db()
        self.assertEqual((r.estado, self.h101.estado), ('en_estadia', 'ocupada'))

    def test_s15_checkin_antes_de_la_fecha_se_rechaza(self):
        """S-15 No se puede hacer check-in antes de la fecha de entrada."""
        r = self.reserva(entrada=2, salida=4)
        with self.assertRaises(s.OperacionNoPermitida):
            s.hacer_checkin(r.pk)

    def test_s16_checkin_con_fecha_de_salida_vencida_se_rechaza(self):
        """S-16 No se puede hacer check-in si la fecha de salida ya pasó."""
        r = self.reserva(entrada=-3, salida=-1)
        with self.assertRaises(s.OperacionNoPermitida):
            s.hacer_checkin(r.pk)

    def test_s17_checkin_con_habitacion_ocupada_se_rechaza(self):
        """S-17 No se puede hacer check-in si la habitación aún está ocupada."""
        Habitacion.objects.filter(pk=self.h101.pk).update(estado='ocupada')
        r = self.reserva(entrada=0, salida=2)
        with self.assertRaises(s.OperacionNoPermitida):
            s.hacer_checkin(r.pk)

    def test_s18_checkin_no_se_repite(self):
        """S-18 El check-in no se puede hacer dos veces sobre la misma reserva."""
        r = self.reserva(entrada=0, salida=2)
        s.hacer_checkin(r.pk)
        with self.assertRaises(s.OperacionNoPermitida):
            s.hacer_checkin(r.pk)

    def test_s19_checkout_deja_habitacion_en_limpieza(self):
        """S-19 El check-out finaliza la reserva y deja la habitación En limpieza."""
        r = self.reserva(entrada=-1, salida=1)
        Habitacion.objects.filter(pk=self.h101.pk).update(estado='ocupada')
        Reserva.objects.filter(pk=r.pk).update(estado='en_estadia')
        s.hacer_checkout(r.pk)
        r.refresh_from_db(); self.h101.refresh_from_db()
        self.assertEqual((r.estado, self.h101.estado), ('finalizada', 'limpieza'))

    def test_s20_checkout_sin_checkin_se_rechaza(self):
        """S-20 No se puede hacer check-out de una reserva sin check-in."""
        r = self.reserva(entrada=0, salida=2)
        with self.assertRaises(s.OperacionNoPermitida):
            s.hacer_checkout(r.pk)

    def test_s21_marcar_disponible_solo_desde_limpieza(self):
        """S-21 Una habitación solo vuelve a Disponible desde En limpieza."""
        with self.assertRaises(s.OperacionNoPermitida):
            s.marcar_disponible(self.h101.pk)
        Habitacion.objects.filter(pk=self.h101.pk).update(estado='limpieza')
        s.marcar_disponible(self.h101.pk)
        self.h101.refresh_from_db()
        self.assertEqual(self.h101.estado, 'disponible')

    def test_s22_ciclo_completo(self):
        """S-22 Ciclo completo: reservar, check-in, check-out y volver a disponible."""
        r = s.crear_reserva(self.ana, self.h101, self.dia(0), self.dia(2), 1)
        s.hacer_checkin(r.pk)
        s.hacer_checkout(r.pk)
        s.marcar_disponible(self.h101.pk)
        r.refresh_from_db(); self.h101.refresh_from_db()
        self.assertEqual((r.estado, self.h101.estado), ('finalizada', 'disponible'))


class ModificarYNoPresentadoTest(_Ayuda, BaseTest):

    def test_s23_modificar_cambia_fechas_y_recalcula_total(self):
        """S-23 Al modificar fechas el total se recalcula."""
        r = self.reserva(entrada=1, salida=3)
        s.modificar_reserva(r.pk, self.h101, self.dia(1), self.dia(4), 2)
        r.refresh_from_db()
        self.assertEqual((r.total, r.numero_huespedes), (150000, 2))

    def test_s24_modificar_no_choca_consigo_misma(self):
        """S-24 Mover una reserva un día no se bloquea por sí misma."""
        r = self.reserva(entrada=1, salida=3)
        s.modificar_reserva(r.pk, self.h101, self.dia(2), self.dia(4), 1)
        r.refresh_from_db()
        self.assertEqual(r.fecha_entrada, self.dia(2))

    def test_s25_modificar_rechaza_choque_con_otra_reserva(self):
        """S-25 No se puede mover a una habitación ocupada por otra reserva."""
        self.reserva(self.h102, 1, 3, huesped=self.luis)
        r = self.reserva(self.h101, 1, 3)
        with self.assertRaises(s.HabitacionNoDisponible):
            s.modificar_reserva(r.pk, self.h102, self.dia(1), self.dia(3), 1)

    def test_s26_modificar_solo_reservadas(self):
        """S-26 Solo las reservas en estado Reservada se pueden modificar."""
        r = self.reserva(estado='cancelada')
        with self.assertRaises(s.OperacionNoPermitida):
            s.modificar_reserva(r.pk, self.h101, self.dia(1), self.dia(3), 1)

    def test_s27_no_presentado_libera_la_habitacion(self):
        """S-27 Una reserva vencida se marca No presentado y libera la habitación."""
        r = self.reserva(entrada=-1, salida=2)
        s.marcar_no_presentado(r.pk)
        r.refresh_from_db()
        self.assertEqual(r.estado, 'no_presentado')
        self.assertIn(self.h101, s.habitaciones_disponibles(self.dia(0), self.dia(2)))

    def test_s28_no_presentado_antes_de_la_fecha_se_rechaza(self):
        """S-28 No se puede marcar No presentado antes de la fecha de entrada."""
        r = self.reserva(entrada=2, salida=4)
        with self.assertRaises(s.OperacionNoPermitida):
            s.marcar_no_presentado(r.pk)

"""Prueba de extremo a extremo del Anexo B (módulos nuevos).

Ejecuta, contra la base de datos de desarrollo y **dentro de una transacción que
se revierte**, el recorrido del Anexo B del documento
`backend/manual/prueba_extremo_a_extremo.html`:

  B1  Dos hojas del vehículo (Editar / Publicar)
  B2  Reserva de 1.000 € con su movimiento y asiento
  B3  Venta de 11.500 € descontando la señal (un solo cobro de 10.500)
  B4  Trabajador sin acceso + fichaje por PIN
  B5  Nómina quincenal automática (750 / 47,62 / 45,00 / 657,38)
  B6  Generador del periodo sin duplicar

Uso:
    python prueba_anexo_b.py

No deja datos: todo se revierte al terminar. Requiere los usuarios de prueba
(`python create_test_users.py`) y la base migrada.
"""
import os
import sys
from datetime import date
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

import django  # noqa: E402

django.setup()

from django.db import transaction  # noqa: E402
from django.test import Client  # noqa: E402
from django.urls import reverse  # noqa: E402

OK = 0
FAIL = 0


def check(descripcion, condicion, detalle=''):
    global OK, FAIL
    if condicion:
        OK += 1
        print(f'  [OK] {descripcion}' + (f' - {detalle}' if detalle else ''))
    else:
        FAIL += 1
        print(f'  [FALLA] {descripcion}' + (f' - {detalle}' if detalle else ''))


def importes_banco(vehiculo):
    from apps.bank.models import BancoMovimiento

    from django.db.models import Q

    movimientos = BancoMovimiento.objects.filter(tipo='INGRESO').filter(
        Q(vehiculo_asociado=vehiculo) | Q(concepto__icontains=vehiculo.matricula)
    )
    return sorted(m.importe for m in movimientos)


def main():
    from apps.accounts.models import User
    from apps.accounting.models import PlanContableDefault
    from apps.bank.models import BancoCuenta, BancoMovimiento, Reserva
    from apps.payroll.models import NominaEstructura
    from apps.payroll.services import generar_nominas_del_periodo
    from apps.vehicles.models import Vehiculo

    PlanContableDefault.crear_plan_base()

    admin = User.objects.filter(username='admin').first()
    if admin is None:
        print('Falta el usuario admin. Ejecute: python create_test_users.py')
        return 1

    cliente = Client()
    cliente.force_login(admin)

    with transaction.atomic():
        from apps.accounting.models import CuentaContable

        if not BancoCuenta.objects.filter(activa=True).exists():
            BancoCuenta.objects.create(
                nombre='Santander prueba',
                iban='ES9121000418450200051332',
                cuenta_contable=CuentaContable.objects.get(codigo='572'),
            )

        vehiculo = Vehiculo.objects.create(
            matricula='TST001', bastidor='WVWZZZ3CZWE000001',
            marca='Volkswagen', modelo='Golf 1.6 TDI', anio=2020,
            combustible='DIESEL', kilometraje=90000, tipo_dano='ACCIDENTAL',
            etiqueta_ambiental='C', estado='ACONDICIONADO',
            fecha_adquisicion=date(2026, 10, 1),
            precio_subasta=Decimal('7500.00'), tasas_sala=Decimal('400.00'),
            logistica_grua=Decimal('250.00'), tipo_iva=Decimal('136.50'),
            created_by=admin,
        )

        print('\n[B1] Dos hojas del vehículo')
        resp = cliente.get(reverse('vehicles:update', args=[vehiculo.pk]))
        html = resp.content.decode()
        check('Editar responde', resp.status_code == 200)
        check('Editar tiene costes de compra', 'name="precio_subasta"' in html)
        check('Editar NO tiene precio de venta', 'name="precio_venta"' not in html)
        check('Editar NO tiene fotos', 'imagenes-TOTAL_FORMS' not in html)

        resp = cliente.get(reverse('vehicles:publicar', args=[vehiculo.pk]))
        html = resp.content.decode()
        check('Publicar responde', resp.status_code == 200)
        check('Publicar tiene precio de venta', 'name="precio_venta"' in html)
        check('Publicar tiene fecha de publicación', 'name="fecha_publicacion"' in html)
        check('Publicar NO tiene costes', 'name="precio_subasta"' not in html)

        resp = cliente.post(reverse('vehicles:publicar', args=[vehiculo.pk]), {
            'estado': 'EN_VENTA',
            'precio_venta': '11.500,00',
            'descripcion_dano': 'Buen estado',
            'imagenes-TOTAL_FORMS': '0', 'imagenes-INITIAL_FORMS': '0',
            'imagenes-MIN_NUM_FORMS': '0', 'imagenes-MAX_NUM_FORMS': '15',
        })
        vehiculo.refresh_from_db()
        check('Publicar guarda precio y estado', resp.status_code == 302)
        check('Precio de venta 11.500', vehiculo.precio_venta == Decimal('11500.00'))
        check('Fecha de publicación automática',
              vehiculo.fecha_publicacion is not None,
              str(vehiculo.fecha_publicacion))

        print('\n[B2] Reserva de 1.000 €')
        resp = cliente.post(reverse('bank:reserva_create'), {
            'vehiculo': vehiculo.pk,
            'tipo_cliente': 'PARTICULAR',
            'cliente_nombre': 'Carlos Ruiz',
            'cliente_dni': '12345678A',
            'cliente_direccion': 'Calle Mayor 1',
            'cliente_poblacion': 'Madrid',
            'cliente_provincia': 'Madrid',
            'cliente_cp': '28001',
            'cliente_telefono': '612345678',
            'cliente_email': 'carlos@example.com',
            'fecha_reserva': '2026-11-20',
            'importe_reserva': '1000.00',
            'metodo_pago': 'TRANSFERENCIA',
            'notas': '',
        })
        reserva = Reserva.objects.filter(vehiculo=vehiculo).first()
        check('Reserva creada', resp.status_code == 302 and reserva is not None)
        check('Reserva ACTIVA', reserva.estado == 'ACTIVA')
        check('Ingreso de la señal 1.000',
              importes_banco(vehiculo) == [Decimal('1000.00')],
              str(importes_banco(vehiculo)))

        asiento_reserva = reserva.banco_movimiento.asiento_asociado
        saldos = {
            m.cuenta.codigo: m.debe - m.haber
            for m in asiento_reserva.movimientos.all()
        }
        check('Asiento anticipo cuadrado', asiento_reserva.esta_cuadrado)
        check('Asiento anticipo POSTEADO', asiento_reserva.estado == 'POSTEADO')
        check('Movimiento enlazado con su asiento',
              reserva.banco_movimiento.asiento_asociado_id == asiento_reserva.pk)
        check('DEBE 572 1.000', saldos.get('572') == Decimal('1000.00'))
        check('HABER 438 1.000 (entrega a cuenta REBU, sin IVA)',
              saldos.get('438') == Decimal('-1000.00'), str(saldos.get('438')))
        check('Sin IVA propio en el anticipo',
              '477' not in saldos, str(saldos.get('477')))

        print('\n[B3] Venta de 11.500 descontando la señal')
        resp = cliente.post(reverse('sales:create'), {
            'vehiculo': vehiculo.pk,
            'reserva': reserva.pk,
            'tipo_cliente': 'PARTICULAR',
            'cliente_nombre': 'Carlos Ruiz',
            'cliente_dni': '12345678A',
            'cliente_direccion': 'Calle Mayor 1',
            'cliente_poblacion': 'Madrid',
            'cliente_provincia': 'Madrid',
            'cliente_cp': '28001',
            'cliente_telefono': '612345678',
            'cliente_email': 'carlos@example.com',
            'fecha_venta': '2026-11-25',
            'metodo_pago': 'TRANSFERENCIA',
            'precio_venta': '11500.00',
        })
        check('Venta registrada', resp.status_code == 302)

        vehiculo.refresh_from_db()
        reserva.refresh_from_db()
        venta = vehiculo.venta

        check('Un solo cobro nuevo de 10.500',
              importes_banco(vehiculo) == [Decimal('1000.00'), Decimal('10500.00')],
              str(importes_banco(vehiculo)))
        check('Total en banco 11.500',
              sum(importes_banco(vehiculo)) == Decimal('11500.00'))
        check('Reserva CONVERTIDA', reserva.estado == 'CONVERTIDA')
        check('Reserva enlazada con la venta', reserva.venta_id == venta.pk)
        check('Asiento de venta cuadrado', venta.asiento_contable.esta_cuadrado)

        saldos_venta = {
            m.cuenta.codigo: m.debe - m.haber
            for m in venta.asiento_contable.movimientos.all()
        }
        check('Venta: DEBE 572 10.500',
              saldos_venta.get('572') == Decimal('10500.00'),
              str(saldos_venta.get('572')))
        check('Venta: 438 cancelado (1.000)',
              saldos_venta.get('438') == Decimal('1000.00'), str(saldos_venta.get('438')))
        check('Venta: sin 477 del anticipo',
              saldos_venta.get('477', Decimal('0')) == Decimal('0'),
              str(saldos_venta.get('477')))

        print('\n[B4] Trabajador sin acceso y fichaje por PIN')
        resp = cliente.post(reverse('usuarios:create'), {
            'first_name': 'Manuel', 'last_name': 'García',
            'rol': 'OPERARIO', 'sin_acceso': 'on', 'pin_kiosco': '7777',
            'is_active': 'on', 'puede_eliminar': 'on',
            'salario_base_mensual': '1500', 'porcentaje_ss_patronal': '31.50',
            'periodicidad_pago': 'QUINCENAL',
            'porcentaje_irpf': '6', 'porcentaje_ss_obrera': '6.35',
        })
        trabajador = User.objects.filter(
            first_name='Manuel', last_name='García'
        ).first()
        check('Trabajador creado sin usuario ni contraseña',
              resp.status_code == 302 and trabajador is not None)
        check('Marcado como sin acceso', trabajador.sin_acceso)
        check('Contraseña inservible', not trabajador.has_usable_password())
        check('PIN guardado', trabajador.pin_kiosco == '7777')

        tablet = Client()
        resp = tablet.post(reverse('attendance:kiosco'), {'pin': '7777'})
        desde = trabajador.marcajes.count()
        check('Ficha en el kiosco sin sesión', resp.status_code == 200)
        check('Marcaje registrado', desde == 1, f'{desde} marcajes')
        check('Sale su nombre en el kiosco', 'Manuel' in resp.content.decode())

        print('\n[B5] Nómina quincenal automática')
        resp = cliente.post(reverse('payroll:create'), {
            'empleado': trabajador.pk,
            'periodo': 'QUINCENAL',
            'fecha_nomina': '2026-11-16',
            'calcular_automaticamente': 'on',
        })
        nomina = NominaEstructura.objects.filter(empleado=trabajador).first()
        check('Nómina creada', resp.status_code == 302 and nomina is not None)
        check('Bruto 750,00', nomina.salario_bruto == Decimal('750.00'))
        check('SS patronal 236,25', nomina.ss_patronal == Decimal('236.25'))
        check('SS obrera 47,62', nomina.ss_obrera == Decimal('47.62'))
        check('IRPF 45,00', nomina.retencion_irpf == Decimal('45.00'))
        check('Líquido 657,38', nomina.liquido_percibir == Decimal('657.38'))
        check('Asiento de nómina cuadrado', nomina.asiento_contable.esta_cuadrado)

        print('\n[B6] Generador del periodo sin duplicar')
        resultado = generar_nominas_del_periodo(fecha=date(2026, 11, 20))
        check('Generador termina bien', resultado['status'] == 'ok')
        check('No duplica la nómina quincenal de Manuel',
              NominaEstructura.objects.filter(
                  empleado=trabajador, periodo='QUINCENAL'
              ).count() == 1,
              f'{resultado["generadas"]} generadas, {resultado["saltadas"]} saltadas')

        print('\n[Cuadre] Contabilidad')
        from apps.accounting.models import AsientoContable

        descuadrados = [
            a.numero for a in AsientoContable.objects.all()
            if a.estado == 'POSTEADO' and not a.esta_cuadrado
        ]
        check('Todos los asientos posteados cuadran', not descuadrados, str(descuadrados))

        transaction.set_rollback(True)

    print('\n' + '=' * 60)
    print(f'  Total: {OK + FAIL} | OK: {OK} | FALLA: {FAIL}')
    print('=' * 60)
    print('  (datos revertidos: la base queda como estaba)')
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

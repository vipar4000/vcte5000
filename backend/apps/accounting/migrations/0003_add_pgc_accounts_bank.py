"""
Migración de datos: añade cuentas PGC necesarias para el módulo bancario.
"""
from django.db import migrations


CUENTAS_NUEVAS = [
    ('438', 'Anticipos de Clientes', 'A'),
    ('477', 'Hacienda Pública, IVA repercutido (otros)', 'P'),
    ('477001', 'HP IVA Repercutido REBU', 'P'),
    ('622', 'Notaría y Registro', 'G'),
    ('626', 'Comisiones bancarias', 'G'),
]


def forwards(apps, schema_editor):
    CuentaContable = apps.get_model('accounting', 'CuentaContable')
    for codigo, nombre, tipo in CUENTAS_NUEVAS:
        CuentaContable.objects.get_or_create(
            codigo=codigo,
            defaults={'nombre': nombre, 'tipo': tipo}
        )


def backwards(apps, schema_editor):
    CuentaContable = apps.get_model('accounting', 'CuentaContable')
    codigos = [c[0] for c in CUENTAS_NUEVAS]
    CuentaContable.objects.filter(codigo__in=codigos).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0002_initial'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

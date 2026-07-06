from django.db import migrations
import os


def apply_trigger_sql(apps, schema_editor):
    """Aplica trigger de inmutabilidad para facturas."""
    sql_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..', 'sql', '0001_factura_inmutabilidad.sql'
    )
    with open(sql_path, 'r') as f:
        sql = f.read()
    schema_editor.execute(sql)


def reverse_trigger_sql(apps, schema_editor):
    schema_editor.execute("DROP TRIGGER IF EXISTS trg_factura_inmutabilidad ON sales_facturaventa;")
    schema_editor.execute("DROP FUNCTION IF EXISTS prevent_factura_modificacion();")


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0002_ventavehiculo_asiento_contable'),
    ]

    operations = [
        migrations.RunPython(apply_trigger_sql, reverse_trigger_sql),
    ]

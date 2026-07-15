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
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(sql)


def reverse_trigger_sql(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP TRIGGER IF EXISTS trg_factura_inmutabilidad ON sales_facturaventa;")
        cursor.execute("DROP FUNCTION IF EXISTS prevent_factura_modificacion();")


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0003_nuevos_modelos_fase2'),
    ]

    operations = [
        migrations.RunPython(apply_trigger_sql, reverse_trigger_sql),
    ]

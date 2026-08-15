from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_alter_user_rol'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='rol',
            field=models.CharField(choices=[('ADMIN', 'Administrador'), ('OPERARIO', 'Operario de Taller'), ('VENDEDOR', 'Vendedor'), ('GESTORIA', 'Gestoría Externa')], default='OPERARIO', max_length=20, verbose_name='rol'),
        ),
    ]

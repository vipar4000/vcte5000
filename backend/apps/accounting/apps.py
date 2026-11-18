"""Configuración de la app de contabilidad.

Al terminar cualquier `migrate` se asegura de que el Plan General Contable base
exista. Sin él, formularios como «Banco → Nueva cuenta» muestran el desplegable
de cuentas vacío y el usuario no puede guardar, lo que parece un error del
formulario cuando en realidad falta la inicialización del PGC.
"""
from django.apps import AppConfig
from django.db.models.signals import post_migrate


def inicializar_pgc(sender=None, **kwargs):
    """Crea el plan contable base si falta. Es idempotente (get_or_create)."""
    from apps.accounting.models import PlanContableDefault

    PlanContableDefault.crear_plan_base()


class AccountingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounting'
    verbose_name = 'Contabilidad'

    def ready(self):
        # sender=self: se ejecuta una sola vez, al migrar esta app.
        post_migrate.connect(
            inicializar_pgc,
            sender=self,
            dispatch_uid='accounting.inicializar_pgc',
        )

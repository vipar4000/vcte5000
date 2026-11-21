"""Vacía los datos de prueba de la base de datos conservando los usuarios.

Pensado para **staging**: deja el sistema limpio para empezar a trabajar de
verdad, sin borrar las cuentas con las que se entra al ERP.

Qué se conserva:
  - Usuarios (`accounts.User`) y sus grupos/permisos.
  - Plan contable (`CuentaContable` y `PlanContableDefault`): es configuración.
  - Tareas programadas de Celery Beat (configuración).

Qué se borra: vehículos, fotos, OTs, materiales y compras, ventas, reservas,
facturas, garantías, gastos, inversión y activos, nóminas, marcajes, cuentas y
movimientos bancarios, y todos los asientos contables.

Uso:
    python manage.py limpiar_datos_prueba               # simulación (no borra)
    python manage.py limpiar_datos_prueba --confirmar   # borra de verdad
    python manage.py limpiar_datos_prueba --confirmar --conservar-usuarios

Nota: el plan contable se mantiene a propósito. Si además quiere vaciarlo, borre
las cuentas y vuelva a ejecutar `migrate` (el post_migrate lo recrea).
"""
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models.deletion import ProtectedError

# Etiquetas que NO se tocan nunca
CONSERVAR_EXACTOS = {
    'accounts.User',
    'accounting.CuentaContable',
    'accounting.PlanContableDefault',
    'auth.Group',
    'auth.Permission',
    'contenttypes.ContentType',
    'sessions.Session',
}

# Prefijos de apps de infraestructura que se conservan
CONSERVAR_PREFIJOS = (
    'django_celery_beat.',
)

# Registros transitorios que se limpian siempre
TRANSITORIOS = (
    'axes.AccessAttempt',
    'axes.AccessFailureLog',
    'axes.AccessLog',
    'axes.AccessAttemptExpiration',
    'admin.LogEntry',
)


class Command(BaseCommand):
    help = 'Borra los datos de prueba conservando los usuarios (para staging).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar', action='store_true',
            help='Ejecuta el borrado. Sin esta opción solo muestra lo que haría.',
        )
        parser.add_argument(
            '--forzar', action='store_true',
            help='Permite ejecutarlo con los ajustes de producción.',
        )

    def handle(self, *args, **opciones):
        from django.conf import settings

        if settings.SETTINGS_MODULE.endswith('production') and not opciones['forzar']:
            raise CommandError(
                'Los ajustes son de PRODUCCIÓN. Si de verdad quiere limpiar esa '
                'base, repita con --forzar (haga antes una copia de seguridad).'
            )

        usuarios = apps.get_model('accounts', 'User')
        total_usuarios = usuarios.objects.count()

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Usuarios que se conservan: {total_usuarios}'
        ))

        candidatos = self._modelos_a_borrar()

        if not opciones['confirmar']:
            self.stdout.write('')
            self.stdout.write('SIMULACIÓN: no se ha borrado nada. Detalle:')
            filas = self._contar(candidatos)
            for modelo, cantidad in filas:
                if cantidad:
                    self.stdout.write(f'  {modelo}: {cantidad}')
            total = sum(c for _, c in filas)
            self.stdout.write(self.style.WARNING(f'  Total de filas a borrar: {total}'))
            self.stdout.write('')
            self.stdout.write(
                'Para borrar de verdad: python manage.py limpiar_datos_prueba --confirmar'
            )
            return

        borradas = 0
        modelo_borrado = {}

        with transaction.atomic():
            # 0) Anular FKs que apuntan al mismo modelo (factura rectificada)
            self._liberar_autoreferencias(candidatos)

            # 1) Registros transitorios (accesos, bloqueos, historial del admin)
            for etiqueta in TRANSITORIOS:
                try:
                    modelo = apps.get_model(etiqueta)
                except LookupError:
                    continue
                cantidad, _ = modelo.objects.all().delete()
                borradas += cantidad

            # 2) Datos de negocio: se reintenta hasta que no quede nada.
            #    Así se resuelven las protecciones (PROTECT) sin orden manual.
            pendientes = list(candidatos)
            while pendientes:
                progreso = False
                for modelo in list(pendientes):
                    etiqueta = modelo._meta.label
                    try:
                        with transaction.atomic():
                            cantidad, _ = modelo.objects.all().delete()
                    except ProtectedError:
                        continue
                    pendientes.remove(modelo)
                    progreso = True
                    if cantidad:
                        modelo_borrado[etiqueta] = modelo_borrado.get(etiqueta, 0) + cantidad
                        borradas += cantidad
                if not progreso:
                    bloqueados = ', '.join(m._meta.label for m in pendientes)
                    raise CommandError(
                        f'No se pudo borrar por dependencias: {bloqueados}'
                    )

        self.stdout.write('')
        for etiqueta in sorted(modelo_borrado):
            self.stdout.write(f'  {etiqueta}: {modelo_borrado[etiqueta]}')

        self.stdout.write(self.style.SUCCESS(
            f'\nLimpieza terminada: {borradas} fila(s) borradas. '
            f'Usuarios conservados: {usuarios.objects.count()}'
        ))
        self.stdout.write(
            'El plan contable y las tareas programadas siguen en su sitio. '
            'Los usuarios pueden entrar con su misma contraseña.'
        )

    # ------------------------------------------------------------------ utils

    def _modelos_a_borrar(self):
        """Todos los modelos del proyecto menos los que se conservan."""
        modelos = []
        for modelo in apps.get_models():
            etiqueta = modelo._meta.label
            if etiqueta in CONSERVAR_EXACTOS:
                continue
            if etiqueta.startswith(CONSERVAR_PREFIJOS):
                continue
            if modelo._meta.app_label in ('migrations',):
                continue
            modelos.append(modelo)
        return modelos

    def _liberar_autoreferencias(self, modelos):
        """Anula FKs que apuntan al mismo modelo (p. ej. factura rectificada)."""
        for modelo in modelos:
            for campo in modelo._meta.get_fields():
                if campo.auto_created or not campo.is_relation:
                    continue
                if campo.related_model is not modelo or not campo.null:
                    continue
                try:
                    modelo.objects.filter(
                        **{f'{campo.name}__isnull': False}
                    ).update(**{campo.name: None})
                except Exception:
                    # Si el modelo ya no existe en esta base, se ignora.
                    pass

    def _contar(self, modelos):
        filas = []
        for modelo in modelos:
            try:
                filas.append((modelo._meta.label, modelo.objects.count()))
            except Exception:
                continue
        return sorted(filas, key=lambda par: -par[1])

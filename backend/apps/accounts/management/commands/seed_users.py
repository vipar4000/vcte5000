from django.core.management.base import BaseCommand
from apps.accounts.models import User


USERS = [
    {
        'username': 'admin',
        'email': 'admin@eurocar.local',
        'first_name': 'Admin',
        'last_name': 'Rogil',
        'rol': 'ADMIN',
        'password': 'admin123!',
        'is_staff': True,
        'is_superuser': True,
    },
    {
        'username': 'mecanico1',
        'email': 'mecanico1@eurocar.local',
        'first_name': 'Carlos',
        'last_name': 'García',
        'rol': 'OPERARIO',
        'pin_kiosco': '1234',
        'salario_base_mensual': 1800,
        'password': 'mecanico123!',
    },
    {
        'username': 'mecanico2',
        'email': 'mecanico2@eurocar.local',
        'first_name': 'Ana',
        'last_name': 'López',
        'rol': 'OPERARIO',
        'pin_kiosco': '5678',
        'salario_base_mensual': 1800,
        'password': 'mecanico123!',
    },
    {
        'username': 'vendedor1',
        'email': 'vendedor1@eurocar.local',
        'first_name': 'Pedro',
        'last_name': 'Martínez',
        'rol': 'VENDEDOR',
        'password': 'vendedor123!',
    },
    {
        'username': 'gestoria1',
        'email': 'gestoria1@eurocar.local',
        'first_name': 'Laura',
        'last_name': 'Fernández',
        'rol': 'GESTORIA',
        'password': 'gestoria123!',
    },
]


class Command(BaseCommand):
    help = 'Crea los usuarios de prueba si no existen (idempotente).'

    def handle(self, *args, **options):
        for data in USERS:
            password = data.pop('password')
            is_staff = data.pop('is_staff', False)
            is_superuser = data.pop('is_superuser', False)
            user, created = User.objects.get_or_create(
                username=data['username'],
                defaults=data,
            )
            if created:
                user.set_password(password)
                user.is_staff = is_staff
                user.is_superuser = is_superuser
                user.save()
                self.stdout.write(self.style.SUCCESS(
                    f'[OK] Creado: {user.username} ({user.get_rol_display()})'
                ))
            else:
                self.stdout.write(f'[SKIP] Ya existe: {user.username}')
        self.stdout.write(self.style.SUCCESS('--- Usuarios en BD ---'))
        for u in User.objects.all():
            self.stdout.write(f'  {u.username}: {u.get_rol_display()}')

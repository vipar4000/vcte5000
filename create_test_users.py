import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))
django.setup()

from apps.accounts.models import User

users = [
    {
        'username': 'admin',
        'email': 'admin@eurocar.local',
        'first_name': 'Admin',
        'last_name': 'Rogil',
        'rol': 'ADMIN',
        'password': 'admin123!',
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

for data in users:
    password = data.pop('password')
    user, created = User.objects.update_or_create(
        username=data['username'],
        defaults=data
    )
    user.set_password(password)
    # Ensure active, in case an old/broken test account was disabled
    if not user.is_active:
        user.is_active = True
    user.save()
    action = 'Created' if created else 'Updated'
    print(f'[OK] {action}: {user.username} ({user.get_rol_display()})')

print('\n--- Users list ---')
for u in User.objects.all():
    print(f'  {u.username}: {u.get_rol_display()} (PIN: {u.pin_kiosco or "N/A"})')

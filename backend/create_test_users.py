import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Use SQLite for this script
os.environ['DATABASE_URL'] = 'sqlite:///C:/eurocar/backend/test.db'

django.setup()

from apps.accounts.models import User

# Create superuser
if not User.objects.filter(username='admin').exists():
    user = User.objects.create_superuser(
        username='admin',
        email='admin@eurocar.local',
        password='admin123!',
        first_name='Administrador',
        last_name='Rogil',
        rol='ADMIN',
        is_staff=True,
        is_superuser=True,
    )
    print(f'Superuser created: {user.username}')
else:
    print('Superuser already exists')

# Create test users
test_users = [
    {
        'username': 'mecanico1',
        'email': 'mecanico1@eurocar.local',
        'password': 'mecanico123!',
        'first_name': 'Juan',
        'last_name': 'García',
        'rol': 'OPERARIO',
        'salario_base_mensual': 1800.00,
    },
    {
        'username': 'vendedor1',
        'email': 'vendedor1@eurocar.local',
        'password': 'vendedor123!',
        'first_name': 'María',
        'last_name': 'López',
        'rol': 'VENDEDOR',
    },
    {
        'username': 'gestoria1',
        'email': 'gestoria1@eurocar.local',
        'password': 'gestoria123!',
        'first_name': 'Carlos',
        'last_name': 'Martínez',
        'rol': 'GESTORIA',
    },
]

for userData in test_users:
    if not User.objects.filter(username=userData['username']).exists():
        user = User.objects.create_user(**userData)
        print(f'User created: {user.username}')
    else:
        print(f'User {userData["username"]} already exists')

print('\n--- Test Users Summary ---')
for user in User.objects.all():
    print(f'{user.username}: {user.get_rol_display()} - Email: {user.email}')

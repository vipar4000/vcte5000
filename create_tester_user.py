#!/usr/bin/env python
"""
Crea/actualiza el usuario tester ADMIN para entornos de staging o produccion.
Ejecutar desde Render Shell:
    python create_tester_user.py

Para eliminar tras las pruebas:
    python create_tester_user.py --delete

Para restablecer contrasena:
    python create_tester_user.py --reset-password
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))
django.setup()

from apps.accounts.models import User

DELETE_MODE = '--delete' in sys.argv
RESET_MODE = '--reset-password' in sys.argv

if DELETE_MODE:
    try:
        tester = User.objects.get(username='tester')
        tester.delete()
        print('[OK] Usuario tester eliminado.')
    except User.DoesNotExist:
        print('[OK] El usuario tester no existia.')
    sys.exit(0)

tester, created = User.objects.get_or_create(
    username='tester',
    defaults={
        'email': 'tester@eurocar.local',
        'first_name': 'Tester',
        'last_name': 'Madrid',
        'rol': 'ADMIN',
        'is_staff': True,
        'is_superuser': True,
        'puede_eliminar': True,
    }
)

if created or RESET_MODE:
    tester.set_password('TestMadrid2024!')
    tester.rol = 'ADMIN'
    tester.is_staff = True
    tester.is_superuser = True
    tester.puede_eliminar = True
    tester.save()
    action = 'creado' if created else 'contrasena restablecida'
    print(f'[OK] Usuario tester {action}: tester / TestMadrid2024!')
else:
    print('[OK] El usuario tester ya existe.')
    print('     Si necesitas restablecer la contrasena, ejecuta:')
    print('     python create_tester_user.py --reset-password')

#!/usr/bin/env python
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))
django.setup()

from apps.accounts.models import User

tester, created = User.objects.get_or_create(
    username='tester',
    defaults={
        'email': 'tester@eurocar.local',
        'first_name': 'Tester',
        'last_name': 'Sistema',
        'rol': 'ADMIN',
        'is_staff': True,
        'is_superuser': True,
        'puede_eliminar': True,
    }
)
tester.set_password('TestMadrid2024!')
tester.rol = 'ADMIN'
tester.is_staff = True
tester.is_superuser = True
tester.puede_eliminar = True
tester.save()

action = 'creado' if created else 'actualizado'
print(f'[OK] Usuario tester {action}: tester / TestMadrid2024!')

#!/usr/bin/env python
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))
django.setup()

from apps.accounts.models import User

print("Creating test users...")

users_data = [
    {
        "username": "admin",
        "email": "admin@eurocar.local",
        "first_name": "Administrador",
        "last_name": "Rogil",
        "rol": "ADMIN",
        "is_staff": True,
        "is_superuser": True,
        "password": "admin123!",
    },
    {
        "username": "mecanico1",
        "email": "mecanico1@eurocar.local",
        "first_name": "Carlos",
        "last_name": "Garcia",
        "rol": "OPERARIO",
        "pin_kiosco": "1234",
        "salario_base_mensual": "1800",
        "password": "mecanico123!",
    },
    {
        "username": "mecanico2",
        "email": "mecanico2@eurocar.local",
        "first_name": "Ana",
        "last_name": "Lopez",
        "rol": "OPERARIO",
        "pin_kiosco": "5678",
        "salario_base_mensual": "1800",
        "password": "mecanico123!",
    },
    {
        "username": "vendedor1",
        "email": "vendedor1@eurocar.local",
        "first_name": "Pedro",
        "last_name": "Martinez",
        "rol": "VENDEDOR",
        "password": "vendedor123!",
    },
    {
        "username": "gestoria1",
        "email": "gestoria1@eurocar.local",
        "first_name": "Laura",
        "last_name": "Fernandez",
        "rol": "GESTORIA",
        "password": "gestoria123!",
    },
    {
        "username": "roger",
        "email": "roger@eurocar.local",
        "first_name": "Roger",
        "last_name": "Admin",
        "rol": "ADMIN",
        "is_staff": True,
        "is_superuser": False,
        "puede_eliminar": False,
        "password": "roger123!",
    },
]

for data in users_data:
    password = data.pop("password")
    puede_eliminar = data.pop("puede_eliminar", None)
    defaults = data.copy()
    if puede_eliminar is not None:
        defaults["puede_eliminar"] = puede_eliminar

    u, created = User.objects.update_or_create(
        username=defaults["username"],
        defaults=defaults,
    )
    u.set_password(password)
    if not u.is_active:
        u.is_active = True
    u.save()
    action = "Created" if created else "Updated"
    print(f"  {action}: {u.username} ({u.rol})")

print("Done!")

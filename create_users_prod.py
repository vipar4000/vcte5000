#!/usr/bin/env python
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from apps.accounts.models import User

print("Creating test users...")

users_data = [
    {"username": "admin", "email": "admin@eurocar.local", "rol": "ADMIN", "is_staff": True, "is_superuser": True, "password": "admin123!"},
    {"username": "mecanico1", "email": "mecanico1@eurocar.local", "rol": "OPERARIO", "pin_kiosco": "1234", "salario_base_mensual": "1800", "password": "mecanico123!"},
    {"username": "mecanico2", "email": "mecanico2@eurocar.local", "rol": "OPERARIO", "pin_kiosco": "5678", "salario_base_mensual": "1800", "password": "mecanico123!"},
    {"username": "vendedor1", "email": "vendedor1@eurocar.local", "rol": "VENDEDOR", "password": "vendedor123!"},
    {"username": "gestoria1", "email": "gestoria1@eurocar.local", "rol": "GESTORIA", "password": "vendedor123!"},
    {"username": "roger", "email": "roger@eurocar.local", "rol": "ADMIN", "is_staff": True, "is_superuser": False, "puede_eliminar": False, "password": "roger123!"},
]

for data in users_data:
    if not User.objects.filter(username=data["username"]).exists():
        kwargs = {
            "username": data["username"],
            "email": data["email"],
            "rol": data["rol"],
        }
        if data.get("is_staff"):
            kwargs["is_staff"] = True
            kwargs["is_superuser"] = data.get("is_superuser", True)
        if data.get("pin_kiosco"):
            kwargs["pin_kiosco"] = data["pin_kiosco"]
        if data.get("salario_base_mensual"):
            kwargs["salario_base_mensual"] = data["salario_base_mensual"]
        if "puede_eliminar" in data:
            kwargs["puede_eliminar"] = data["puede_eliminar"]

        puede_eliminar = kwargs.pop("puede_eliminar", None)
        u = User.objects.create_user(password=data["password"], **kwargs)
        if puede_eliminar is not None:
            u.puede_eliminar = puede_eliminar
            u.save(update_fields=["puede_eliminar"])
        print("  Created: " + u.username + " (" + u.rol + ")")
    else:
        print("  Exists: " + data["username"])

print("Done!")

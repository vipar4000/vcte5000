# R Car Rogil ERP

Sistema ERP para la gestión integral de vehículos de ocasión en Madrid.

## Características Principales

- **Módulo de Adquisición**: Gestión de compra de vehículos en subasta
- **Módulo de Taller**: Órdenes de trabajo y control de inventario
- **Módulo de Venta**: Comercialización y contratos
- **Módulo de Asistencia**: Control de jornada laboral
- **Módulo de Contabilidad**: Asientos automáticos y estados financieros
- **Módulo de Postventa**: Garantías según Real Decreto-ley 7/2021

## Requisitos Previos

- Docker y Docker Compose instalados
- Git

## Instalación Rápida

```bash
# Clonar el repositorio
git clone <url-del-repositorio>
cd eurocar

# Copiar archivo de entorno
cp .env.example .env

# Levantar servicios
docker-compose up -d

# Crear superusuario
docker-compose exec backend python manage.py createsuperuser

# Acceder al sistema
# ERP: http://localhost
# Admin: http://localhost/admin
```

## Estructura del Proyecto

```
eurocar/
├── backend/                    # Django Backend
│   ├── apps/                   # Aplicaciones Django
│   │   ├── core/              # Funcionalidad compartida
│   │   ├── accounts/          # Autenticación y usuarios
│   │   ├── vehicles/          # Gestión de vehículos
│   │   ├── workshop/          # Taller e inventario
│   │   ├── sales/             # Ventas
│   │   ├── warranty/          # Garantías
│   │   ├── accounting/        # Contabilidad
│   │   └── attendance/        # Asistencia
│   ├── config/                 # Configuración Django
│   ├── templates/              # Templates HTML
│   └── static/                 # Archivos estáticos
├── frontend/                   # Vue.js Frontend (web pública)
├── docker/                     # Configuración Docker
├── docker-compose.yml
└── README.md
```

## Roles de Usuario

| Rol | Descripción | Permisos |
|-----|-------------|----------|
| ADMIN | Administrador | Control total |
| OPERARIO | Operario de Taller | Asistencia y OTs |
| VENDEDOR | Vendedor | Catálogo y ventas |
| GESTORIA | Gestoría Externa | Solo lectura contable |

## Tecnologías

- **Backend**: Python 3.11 + Django 4.2
- **Base de Datos**: PostgreSQL 15
- **Frontend ERP**: Django Templates + HTMX
- **Frontend Web**: Vue.js 3 + Nuxt 3
- **Cache**: Redis
- **Tareas**: Celery
- **PDFs**: WeasyPrint

## Desarrollo

```bash
# Ver logs
docker-compose logs -f backend

# Ejecutar comandos Django
docker-compose exec backend python manage.py <comando>

# Acceder a shell de Python
docker-compose exec backend python manage.py shell

# Crear migraciones
docker-compose exec backend python manage.py makemigrations

# Aplicar migraciones
docker-compose exec backend python manage.py migrate
```

## Producción

Para despliegue en producción:

1. Configurar variables de entorno en `.env`
2. Usar `docker-compose.prod.yml`
3. Configurar Nginx con SSL (Let's Encrypt)
4. Configurar backups automáticos

## Licencia

Privado - R Car Rogil © 2024

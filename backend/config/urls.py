from django.contrib import admin
from django.http import Http404
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as serve_static
from apps.core.views import spa_index


def _servir_media(request, path):
    """Sirve /media/ solo en desarrollo o si el entorno lo autoriza.

    En staging y producción los archivos subidos deben vivir en S3/R2 (con
    `MEDIA_URL` apuntando al bucket). Cuando no hay bucket, staging activa
    `SERVE_MEDIA_LOCAL` para que los PDFs se puedan abrir durante las pruebas;
    en producción esta ruta responde 404 porque el disco es efímero.
    """
    if not (settings.DEBUG or getattr(settings, 'SERVE_MEDIA_LOCAL', False)):
        raise Http404('La aplicación no sirve archivos de media')
    return serve_static(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('erp/', include('apps.core.urls')),
    path('erp/accounts/', include('apps.accounts.urls')),
    path('erp/usuarios/', include('apps.accounts.urls_usuarios')),
    path('erp/vehiculos/', include('apps.vehicles.urls')),
    path('erp/taller/', include('apps.workshop.urls')),
    path('erp/ventas/', include('apps.sales.urls')),
    path('erp/asistencia/', include('apps.attendance.urls')),
    path('erp/garantias/', include('apps.warranty.urls')),
    path('erp/contabilidad/', include('apps.accounting.urls')),
    path('erp/gastos/', include('apps.expenses.urls')),
    path('erp/nominas/', include('apps.payroll.urls')),
    path('erp/banco/', include('apps.bank.urls')),
    path('api/', include('apps.api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Media (/media/...): la vista decide si se sirve o no (ver _servir_media).
urlpatterns += [re_path(r'^media/(?P<path>.*)$', _servir_media)]

# Web pública (SPA Vue) - catch-all SIEMPRE al final
urlpatterns += [re_path(r'^(?!(?:admin|erp|api|media|static)/).*$', spa_index)]

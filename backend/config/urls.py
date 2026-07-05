from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('vehiculos/', include('apps.vehicles.urls')),
    path('taller/', include('apps.workshop.urls')),
    path('ventas/', include('apps.sales.urls')),
    path('asistencia/', include('apps.attendance.urls')),
    path('garantias/', include('apps.warranty.urls')),
    path('contabilidad/', include('apps.accounting.urls')),
    path('gastos/', include('apps.expenses.urls')),
    path('api/', include('apps.api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from apps.core.views import spa_index

urlpatterns = [
    path('admin/', admin.site.urls),
    path('erp/', include('apps.core.urls')),
    path('erp/accounts/', include('apps.accounts.urls')),
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
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Web pública (SPA Vue) - catch-all SIEMPRE al final
urlpatterns += [re_path(r'^(?!(?:admin|erp|api|media|static)/).*$', spa_index)]

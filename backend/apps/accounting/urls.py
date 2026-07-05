from django.urls import path
from . import views

app_name = 'accounting'

urlpatterns = [
    # Asientos contables
    path('', views.asiento_list, name='asientos'),
    path('nuevo/', views.asiento_create, name='asiento_create'),
    path('<int:pk>/', views.asiento_detail, name='detail'),
    path('<int:pk>/editar/', views.asiento_update, name='asiento_update'),
    path('<int:pk>/postear/', views.asiento_postear, name='asiento_postear'),
    path('<int:pk>/anular/', views.asiento_anular, name='asiento_anular'),
    
    # Cuentas contables
    path('cuentas/', views.cuenta_contable_list, name='cuentas'),
    path('cuentas/nueva/', views.cuenta_contable_create, name='cuenta_create'),
    path('cuentas/inicializar/', views.inicializar_plan_contable, name='inicializar_plan'),
]

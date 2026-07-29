from django.urls import path
from . import views

app_name = 'bank'

urlpatterns = [
    # Cuentas bancarias
    path('cuentas/', views.cuenta_list, name='cuenta_list'),
    path('cuentas/nueva/', views.cuenta_create, name='cuenta_create'),
    path('cuentas/<int:pk>/', views.cuenta_detail, name='cuenta_detail'),
    path('cuentas/<int:pk>/editar/', views.cuenta_edit, name='cuenta_edit'),
    path('cuentas/<int:cuenta_pk>/deposito/', views.deposito_create, name='deposito_create'),

    # Movimientos
    path('movimientos/', views.movimiento_list, name='movimiento_list'),
    path('movimientos/<int:pk>/', views.movimiento_detail, name='movimiento_detail'),

    # Conciliación
    path('conciliacion/', views.conciliacion_upload, name='conciliacion_upload'),
    path('conciliacion/confirmar/', views.conciliacion_confirmar, name='conciliacion_confirmar'),

    # Reservas
    path('reservas/', views.reserva_list, name='reserva_list'),
    path('reservas/nueva/', views.reserva_create, name='reserva_create'),
    path('reservas/<int:pk>/', views.reserva_detail, name='reserva_detail'),
    path('reservas/<int:pk>/convertir/', views.reserva_convertir, name='reserva_convertir'),
    path('reservas/<int:pk>/cancelar/', views.reserva_cancelar, name='reserva_cancelar'),

    # Guía
    path('guia/', views.banco_guia, name='guia'),
]

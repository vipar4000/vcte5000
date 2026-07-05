from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    # Marcajes
    path('', views.marcaje_list, name='marcajes'),
    path('nuevo/', views.marcaje_create, name='marcaje_create'),
    
    # Kiosco
    path('kiosco/', views.kiosco_view, name='kiosco'),
    
    # Nómina
    path('nomina/', views.configuracion_nomina_list, name='nomina_list'),
    path('nomina/nueva/', views.configuracion_nomina_create, name='nomina_create'),
    path('nomina/<int:pk>/editar/', views.configuracion_nomina_update, name='nomina_update'),
    
    # Reportes
    path('reporte/<int:operario_id>/', views.reporte_jornada, name='reporte_jornada'),
]

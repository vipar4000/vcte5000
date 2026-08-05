from django.urls import path
from . import views

app_name = 'payroll'

urlpatterns = [
    path('', views.nomina_list, name='list'),
    path('nueva/', views.nomina_create, name='create'),
    path('<int:pk>/', views.nomina_detail, name='detail'),
    path('generar-mensual/', views.nomina_generar_mensual, name='generar_mensual'),
]

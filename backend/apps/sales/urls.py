from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    path('', views.venta_list, name='list'),
    path('nueva/', views.venta_create, name='create'),
    path('<int:pk>/', views.venta_detail, name='detail'),
    path('<int:pk>/eliminar/', views.venta_delete, name='delete'),
    path('<int:pk>/contrato/', views.venta_generar_contrato, name='generar_contrato'),
    path('<int:pk>/mandato/', views.venta_generar_mandato, name='generar_mandato'),
]

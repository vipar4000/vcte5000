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
    
    # Facturación REBU
    path('facturas/', views.factura_list, name='factura_list'),
    path('facturas/<int:pk>/', views.factura_detail, name='factura_detail'),
    path('facturas/<int:pk>/pdf/', views.factura_generar_pdf, name='factura_pdf'),
    path('facturas/<int:pk>/rectificativa/', views.factura_rectificativa, name='factura_rectificativa'),
    path('<int:pk>/factura/', views.factura_generar, name='factura_generar'),
    
    # Costos de acondicionamiento
    path('vehiculo/<int:vehiculo_pk>/costos/', views.costo_acondicionamiento_list, name='costos_list'),
    path('vehiculo/<int:vehiculo_pk>/costos/nuevo/', views.costo_acondicionamiento_create, name='costos_create'),
]

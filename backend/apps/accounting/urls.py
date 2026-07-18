from django.urls import path
from . import views
from . import report_views
from . import export_views

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
    
    # Informes financieros
    path('informes/', report_views.informes_list, name='informes'),
    path('informes/pyg/', report_views.pyg_view, name='pyg'),
    path('informes/balance/', report_views.balance_view, name='balance'),
    path('informes/iva/', report_views.iva_view, name='iva'),
    path('informes/comparativa/', report_views.comparativa_view, name='comparativa'),
    path('informes/facturas-compras/', report_views.facturas_compra_view, name='facturas_compras'),
    path('exportar/facturas-compra-csv/', export_views.exportar_facturas_compra_csv, name='export_facturas_compra_csv'),
    
    # Exportación fiscal
    path('exportar/390/', export_views.exportar_modelo_390, name='export_390'),
    path('exportar/303/', export_views.exportar_csv_303, name='export_303'),
    path('exportar/sii/', export_views.exportar_sii_xml, name='export_sii'),
    
    # Tareas programadas
    path('tareas/', export_views.tareas_programadas, name='tareas'),
    path('tareas/crear/', export_views.crear_tareas_por_defecto, name='tareas_crear'),
]

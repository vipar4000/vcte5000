from django.urls import path
from . import views
from . import views_material

app_name = 'workshop'

urlpatterns = [
    # Órdenes de Trabajo
    path('', views.orden_trabajo_list, name='list'),
    path('nueva/', views.orden_trabajo_create, name='create_ot'),
    path('ot/<int:pk>/', views.orden_trabajo_detail, name='detail_ot'),
    path('ot/<int:pk>/editar/', views.orden_trabajo_update, name='update_ot'),
    path('ot/<int:pk>/eliminar/', views.orden_trabajo_delete, name='delete_ot'),
    path('ot/<int:pk>/cambiar-estado/', views.orden_trabajo_cambiar_estado, name='change_status_ot'),
    
    # Materiales / Inventario
    path('materiales/', views_material.material_list, name='material_list'),
    path('compras/', views_material.compra_list, name='compra_list'),
    path('compras/<str:grupo>/', views_material.compra_detail, name='compra_detail'),
    path('compras/<str:grupo>/editar/', views_material.compra_edit, name='compra_edit'),
    path('compras/<str:grupo>/anular/', views_material.compra_anular, name='compra_anular'),
    path('materiales/nuevo/', views_material.material_create, name='material_create'),
    path('materiales/comprar/', views_material.compra_material_create, name='compra_material_create'),
    path('materiales/compra/<int:pk>/pagar/', views_material.compra_pagar, name='compra_pagar'),
    path('materiales/compra/<int:pk>/deshacer-pago/', views_material.compra_deshacer_pago, name='compra_deshacer_pago'),
    path('materiales/<int:pk>/', views_material.material_detail, name='material_detail'),
    path('materiales/<int:pk>/editar/', views_material.material_update, name='material_update'),
    path('materiales/<int:pk>/eliminar/', views_material.material_delete, name='material_delete'),
    path('materiales/alertas/', views_material.alertas_stock, name='alertas_stock'),
]

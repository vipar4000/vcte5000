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
    path('materiales/nuevo/', views_material.material_create, name='material_create'),
    path('materiales/comprar/', views_material.compra_material_create, name='compra_material_create'),
    path('materiales/<int:pk>/', views_material.material_detail, name='material_detail'),
    path('materiales/<int:pk>/editar/', views_material.material_update, name='material_update'),
    path('materiales/<int:pk>/eliminar/', views_material.material_delete, name='material_delete'),
    path('materiales/alertas/', views_material.alertas_stock, name='alertas_stock'),
]

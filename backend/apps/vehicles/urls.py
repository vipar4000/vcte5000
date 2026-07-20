from django.urls import path
from . import views

app_name = 'vehicles'

urlpatterns = [
    path('', views.vehiculo_list, name='list'),
    path('nuevo/', views.vehiculo_create, name='create'),
    path('<int:pk>/', views.vehiculo_detail, name='detail'),
    path('<int:pk>/editar/', views.vehiculo_update, name='update'),
    path('<int:pk>/eliminar/', views.vehiculo_delete, name='delete'),
    path('<int:pk>/cambiar-estado/', views.vehiculo_cambiar_estado, name='change_status'),
    path('trazabilidad/<str:bastidor>/', views.vehiculo_costes_report, name='costes_report'),
]

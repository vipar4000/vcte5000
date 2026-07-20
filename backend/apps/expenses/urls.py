from django.urls import path
from . import views

app_name = 'expenses'

urlpatterns = [
    path('', views.gasto_list, name='list'),
    path('nuevo/', views.gasto_create, name='create'),
    path('<int:pk>/', views.gasto_detail, name='detail'),
    path('<int:pk>/editar/', views.gasto_update, name='update'),
    path('<int:pk>/eliminar/', views.gasto_delete, name='delete'),
    path('exportar/', views.gasto_export_csv, name='export_csv'),
    path('inversion/', views.inversion_list, name='inversion_list'),
    path('inversion/nueva/', views.inversion_create, name='inversion_create'),
    path('inversion/<int:pk>/', views.inversion_detail, name='inversion_detail'),
]

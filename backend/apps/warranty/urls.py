from django.urls import path
from . import views

app_name = 'warranty'

urlpatterns = [
    # Garantías
    path('', views.garantia_list, name='list'),
    path('<int:pk>/', views.garantia_detail, name='detail'),
    
    # Reparaciones
    path('<int:garantia_pk>/reparacion/', views.reparacion_create, name='reparacion_create'),
    path('reparacion/<int:pk>/editar/', views.reparacion_update, name='reparacion_update'),
    
    # API
    path('api/stats/', views.garantia_stats, name='stats'),
]

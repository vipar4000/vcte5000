from django.urls import path

from . import views_usuarios

app_name = 'usuarios'

urlpatterns = [
    path('', views_usuarios.usuario_list, name='list'),
    path('nuevo/', views_usuarios.usuario_create, name='create'),
    path('<int:pk>/editar/', views_usuarios.usuario_update, name='update'),
    path('<int:pk>/activar/', views_usuarios.usuario_toggle, name='toggle'),
    path('<int:pk>/desbloquear/', views_usuarios.usuario_unlock, name='unlock'),
]

from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('operario/', views.operario_redirect, name='operario'),
    path('vendedor/', views.vendedor_redirect, name='vendedor'),
    path('gestoria/', views.gestoria_redirect, name='gestoria'),
]

from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('search/', views.global_search, name='global_search'),
    path('help/', views.help_center, name='help_center'),
    path('healthz/', views.healthz, name='healthz'),
    path('ping/', views.healthz, name='ping'),
]

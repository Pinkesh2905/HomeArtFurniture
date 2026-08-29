from django.urls import path
from . import views

urlpatterns = [
    path('', views.material_list, name='material_list'),
    path('new/', views.material_create, name='material_create'),
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/new/', views.supplier_create, name='supplier_create'),
    path('suppliers/<int:supplier_id>/edit/', views.supplier_edit, name='supplier_edit'),
    path('suppliers/<int:supplier_id>/delete/', views.supplier_delete, name='supplier_delete'),
    path('print/', views.inventory_print, name='inventory_print'),
    path('<int:material_id>/', views.material_detail, name='material_detail'),
    path('<int:material_id>/edit/', views.material_edit, name='material_edit'),
    path('<int:material_id>/delete/', views.material_delete, name='material_delete'),
    path('<int:material_id>/transaction/', views.stock_transaction, name='stock_transaction'),
]

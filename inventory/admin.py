from django.contrib import admin
from .models import Material, Supplier, StockTransaction


class StockTransactionInline(admin.TabularInline):
    model = StockTransaction
    extra = 0
    readonly_fields = ('total_cost', 'created_at')
    fields = ('date', 'transaction_type', 'quantity', 'unit_cost', 'total_cost', 'supplier', 'reference', 'notes')


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('sku', 'name', 'category', 'current_stock', 'unit', 'cost_per_unit', 'min_stock', 'supplier', 'is_active')
    list_filter = ('category', 'is_active', 'unit')
    search_fields = ('name', 'sku', 'supplier__name')
    readonly_fields = ('sku', 'current_stock', 'created_at', 'updated_at')
    inlines = [StockTransactionInline]


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'phone', 'city', 'gst_number', 'is_active')
    list_filter = ('is_active', 'city')
    search_fields = ('name', 'phone', 'contact_person')


@admin.register(StockTransaction)
class StockTransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'material', 'transaction_type', 'quantity', 'unit_cost', 'total_cost', 'supplier', 'reference')
    list_filter = ('transaction_type', 'date')
    search_fields = ('material__name', 'material__sku', 'reference')
    readonly_fields = ('total_cost', 'created_at')

from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('total_amount',)
    fields = ('furniture_type', 'dimension', 'description', 'quantity', 'rate', 'total_amount')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number',
        'customer',
        'status',
        'is_red_flagged',
        'is_urgent',
        'date',
        'final_amount',
        'advance_paid',
        'grand_total',
    )
    list_filter = ('status', 'is_red_flagged', 'is_urgent', 'order_type', 'date')
    search_fields = ('order_number', 'customer__full_name', 'customer__phone')
    readonly_fields = ('order_number', 'subtotal', 'final_amount', 'grand_total', 'created_at', 'updated_at')
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'description', 'furniture_type', 'quantity', 'rate', 'total_amount')
    search_fields = ('order__order_number', 'description', 'order__customer__full_name')
    list_filter = ('furniture_type',)

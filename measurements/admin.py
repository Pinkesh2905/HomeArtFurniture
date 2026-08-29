from django.contrib import admin
from .models import FurnitureDimension


@admin.register(FurnitureDimension)
class FurnitureDimensionAdmin(admin.ModelAdmin):
    list_display = ('customer', 'furniture_type', 'updated_at')
    search_fields = ('customer__full_name', 'customer__phone', 'furniture_type', 'notes')
    list_filter = ('furniture_type', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')

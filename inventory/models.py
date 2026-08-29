from django.db import models
from django.utils import timezone


class MaterialCategory(models.TextChoices):
    WOOD = 'wood', 'Wood / Timber'
    FABRIC = 'fabric', 'Fabric / Upholstery'
    HARDWARE = 'hardware', 'Hardware (Screws, Nails, Hinges)'
    PAINT = 'paint', 'Paint / Polish / Finish'
    ADHESIVE = 'adhesive', 'Adhesive / Glue'
    FOAM = 'foam', 'Foam / Cushion'
    GLASS = 'glass', 'Glass / Mirror'
    PLYWOOD = 'plywood', 'Plywood / MDF / Particle Board'
    METAL = 'metal', 'Metal (Rods, Pipes, Frames)'
    OTHER = 'other', 'Other'


CATEGORY_SKU_PREFIX = {
    'wood': 'WD',
    'fabric': 'FB',
    'hardware': 'HW',
    'paint': 'PT',
    'adhesive': 'AD',
    'foam': 'FM',
    'glass': 'GL',
    'plywood': 'PW',
    'metal': 'MT',
    'other': 'OT',
}


class UnitOfMeasure(models.TextChoices):
    PIECES = 'pcs', 'Pieces'
    KG = 'kg', 'Kilograms'
    METERS = 'm', 'Meters'
    SQ_FT = 'sqft', 'Square Feet'
    SQ_M = 'sqm', 'Square Meters'
    LITERS = 'l', 'Liters'
    SHEETS = 'sheets', 'Sheets'
    CUBIC_FT = 'cuft', 'Cubic Feet'


class TransactionType(models.TextChoices):
    STOCK_IN = 'in', 'Stock In'
    STOCK_OUT = 'out', 'Stock Out'
    ADJUSTMENT = 'adj', 'Adjustment'
    DAMAGED = 'dmg', 'Damaged / Wastage'


class Supplier(models.Model):
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=15, db_index=True)
    alt_phone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    gst_number = models.CharField(max_length=20, blank=True, verbose_name='GST Number')
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Material(models.Model):
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, unique=True, blank=True, default='', verbose_name='SKU')
    category = models.CharField(max_length=20, choices=MaterialCategory.choices, default=MaterialCategory.OTHER)
    unit = models.CharField(max_length=10, choices=UnitOfMeasure.choices, default=UnitOfMeasure.PIECES)
    current_stock = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    min_stock = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Low-stock alert threshold. Alert shows when current stock is at or below this value.'
    )
    cost_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='materials'
    )
    location = models.CharField(max_length=100, blank=True, help_text='Warehouse shelf, zone, or rack identifier.')
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    @property
    def is_low_stock(self):
        return self.current_stock <= self.min_stock

    @property
    def is_out_of_stock(self):
        return self.current_stock <= 0

    @property
    def stock_value(self):
        return self.current_stock * self.cost_per_unit

    def assign_sku(self):
        """Auto-generate SKU on first save: HAF-{PREFIX}-{PK:04d}"""
        if not self.pk:
            raise ValueError('Material must be saved before assigning a SKU.')
        if self.sku and not self.sku.startswith('TMP-'):
            return
        prefix = CATEGORY_SKU_PREFIX.get(self.category, 'OT')
        self.sku = f"HAF-{prefix}-{self.pk:04d}"
        self.save(update_fields=['sku'])

    def __str__(self):
        return f"{self.name} ({self.sku})"


class StockTransaction(models.Model):
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=5, choices=TransactionType.choices)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reference = models.CharField(max_length=100, blank=True, help_text='Invoice or PO number')
    supplier = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions'
    )
    notes = models.TextField(blank=True)
    date = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def save(self, *args, **kwargs):
        from decimal import Decimal
        self.total_cost = Decimal(str(self.quantity)) * Decimal(str(self.unit_cost))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_transaction_type_display()} — {self.material.name} × {self.quantity}"

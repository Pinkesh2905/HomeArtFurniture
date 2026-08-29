import uuid
from django.db import models
from django.utils import timezone
from customers.models import Customer
from measurements.models import FurnitureType, FurnitureDimension

class OrderType(models.TextChoices):
    CUSTOM_BUILD = 'custom_build', 'Custom Build'
    RENTAL = 'rental', 'Rental'

class OrderStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    IN_PROGRESS = 'in_progress', 'In Progress'
    DELIVERED = 'delivered', 'Delivered'
    CANCELLED = 'cancelled', 'Cancelled'

class PaymentMethod(models.TextChoices):
    CASH = 'cash', 'Cash'
    UPI = 'upi', 'UPI / QR Code'
    CARD = 'card', 'Credit / Debit Card'
    BANK_TRANSFER = 'bank_transfer', 'Bank Transfer'

class Order(models.Model):
    order_number = models.CharField(max_length=30, unique=True, editable=False, blank=True, default='')
    access_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='orders')
    order_type = models.CharField(max_length=20, choices=OrderType.choices, default=OrderType.CUSTOM_BUILD)
    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    
    date = models.DateField(default=timezone.localdate)
    notes = models.TextField(blank=True)

    is_red_flagged = models.BooleanField(
        default=False,
        verbose_name="Red Flag (Outsource Required)",
        help_text="Mark if the item/catalog is unavailable in-store and must be ordered from a 3rd party."
    )
    is_urgent = models.BooleanField(
        default=False,
        verbose_name="Urgent",
        help_text="Mark if this outsourced order requires urgent processing."
    )
    # Billing Totals
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    final_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    advance_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # GST Placeholder
    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def balance_due(self):
        return max(self.final_amount - self.advance_paid, 0)

    def assign_order_number(self):
        if not self.pk:
            raise ValueError('Order must be saved before assigning an order number.')
        if self.order_number and not self.order_number.startswith('TMP-'):
            return
        date_value = self.date or timezone.localdate()
        self.order_number = f"HAF-{date_value:%Y%m%d}-{self.pk:03d}"
        self.save(update_fields=['order_number'])

    def __str__(self):
        return f"{self.order_number} - {self.customer.full_name}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    furniture_type = models.CharField(max_length=50, null=True, blank=True)
    dimension = models.ForeignKey(FurnitureDimension, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total_amount = self.quantity * self.rate
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} ({self.quantity})"

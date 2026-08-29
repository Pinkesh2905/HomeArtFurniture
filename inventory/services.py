from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import Material, Supplier, StockTransaction, TransactionType

MONEY = Decimal('0.01')


def decimal_val(value, default='0', field_name='value'):
    """Parse a decimal from form input."""
    if value in (None, ''):
        value = default
    try:
        amount = Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise ValidationError(f'Enter a valid number for {field_name}.')
    return amount


def positive_decimal(value, default='0', field_name='value'):
    """Parse a non-negative decimal."""
    amount = decimal_val(value, default, field_name)
    if amount < 0:
        raise ValidationError(f'{field_name} cannot be negative.')
    return amount


# ── Stock Transaction Functions ──

@transaction.atomic
def record_stock_in(material, quantity, unit_cost=0, supplier=None, reference='', notes='', date=None):
    """Record incoming stock and increment current_stock."""
    quantity = positive_decimal(quantity, field_name='Quantity')
    unit_cost = positive_decimal(unit_cost, field_name='Unit cost')
    if quantity <= 0:
        raise ValidationError('Quantity must be greater than zero.')

    txn = StockTransaction.objects.create(
        material=material,
        transaction_type=TransactionType.STOCK_IN,
        quantity=quantity,
        unit_cost=unit_cost,
        supplier=supplier,
        reference=reference,
        notes=notes,
        date=date or timezone.localdate(),
    )
    material.current_stock += quantity
    if unit_cost > 0:
        material.cost_per_unit = unit_cost
    material.save(update_fields=['current_stock', 'cost_per_unit', 'updated_at'])
    return txn


@transaction.atomic
def record_stock_out(material, quantity, reference='', notes='', date=None):
    """Record outgoing stock and decrement current_stock."""
    quantity = positive_decimal(quantity, field_name='Quantity')
    if quantity <= 0:
        raise ValidationError('Quantity must be greater than zero.')
    if material.current_stock < quantity:
        raise ValidationError(
            f'Insufficient stock. Available: {material.current_stock} {material.get_unit_display()}, '
            f'requested: {quantity}.'
        )

    txn = StockTransaction.objects.create(
        material=material,
        transaction_type=TransactionType.STOCK_OUT,
        quantity=quantity,
        unit_cost=material.cost_per_unit,
        reference=reference,
        notes=notes,
        date=date or timezone.localdate(),
    )
    material.current_stock -= quantity
    material.save(update_fields=['current_stock', 'updated_at'])
    return txn


@transaction.atomic
def record_adjustment(material, new_quantity, notes='', date=None):
    """Set stock to an absolute value and record the delta as an adjustment."""
    new_quantity = positive_decimal(new_quantity, field_name='New quantity')
    delta = new_quantity - material.current_stock

    txn = StockTransaction.objects.create(
        material=material,
        transaction_type=TransactionType.ADJUSTMENT,
        quantity=delta,
        unit_cost=material.cost_per_unit,
        notes=notes or f'Adjusted from {material.current_stock} to {new_quantity}',
        date=date or timezone.localdate(),
    )
    material.current_stock = new_quantity
    material.save(update_fields=['current_stock', 'updated_at'])
    return txn


@transaction.atomic
def record_damage(material, quantity, notes='', date=None):
    """Record damaged/wasted stock and decrement current_stock."""
    quantity = positive_decimal(quantity, field_name='Quantity')
    if quantity <= 0:
        raise ValidationError('Quantity must be greater than zero.')
    if material.current_stock < quantity:
        raise ValidationError(
            f'Insufficient stock. Available: {material.current_stock} {material.get_unit_display()}, '
            f'reported damaged: {quantity}.'
        )

    txn = StockTransaction.objects.create(
        material=material,
        transaction_type=TransactionType.DAMAGED,
        quantity=quantity,
        unit_cost=material.cost_per_unit,
        notes=notes,
        date=date or timezone.localdate(),
    )
    material.current_stock -= quantity
    material.save(update_fields=['current_stock', 'updated_at'])
    return txn


# ── CRUD Helpers ──

def create_material_from_post(post_data):
    """Create a Material from form POST data."""
    name = (post_data.get('name') or '').strip()
    if not name:
        raise ValidationError('Material name is required.')

    category = post_data.get('category', 'other')
    unit = post_data.get('unit', 'pcs')
    min_stock = positive_decimal(post_data.get('min_stock'), '0', 'Min stock')
    cost_per_unit = positive_decimal(post_data.get('cost_per_unit'), '0', 'Cost per unit')
    location = (post_data.get('location') or '').strip()
    notes = (post_data.get('notes') or '').strip()

    supplier_id = post_data.get('supplier')
    supplier = None
    if supplier_id:
        try:
            supplier = Supplier.objects.get(pk=int(supplier_id))
        except (Supplier.DoesNotExist, ValueError):
            pass

    material = Material.objects.create(
        name=name,
        sku='TMP-new',
        category=category,
        unit=unit,
        min_stock=min_stock,
        cost_per_unit=cost_per_unit,
        supplier=supplier,
        location=location,
        notes=notes,
    )
    material.assign_sku()
    return material


def update_material_from_post(material, post_data):
    """Update an existing Material from form POST data."""
    name = (post_data.get('name') or '').strip()
    if not name:
        raise ValidationError('Material name is required.')

    material.name = name
    material.category = post_data.get('category', material.category)
    material.unit = post_data.get('unit', material.unit)
    material.min_stock = positive_decimal(post_data.get('min_stock'), '0', 'Min stock')
    material.cost_per_unit = positive_decimal(post_data.get('cost_per_unit'), '0', 'Cost per unit')
    material.location = (post_data.get('location') or '').strip()
    material.notes = (post_data.get('notes') or '').strip()

    supplier_id = post_data.get('supplier')
    if supplier_id:
        try:
            material.supplier = Supplier.objects.get(pk=int(supplier_id))
        except (Supplier.DoesNotExist, ValueError):
            material.supplier = None
    else:
        material.supplier = None

    material.save()
    return material


def create_supplier_from_post(post_data):
    """Create a Supplier from form POST data."""
    name = (post_data.get('name') or '').strip()
    if not name:
        raise ValidationError('Supplier name is required.')

    return Supplier.objects.create(
        name=name,
        contact_person=(post_data.get('contact_person') or '').strip(),
        phone=(post_data.get('phone') or '').strip(),
        alt_phone=(post_data.get('alt_phone') or '').strip(),
        email=(post_data.get('email') or '').strip(),
        address=(post_data.get('address') or '').strip(),
        city=(post_data.get('city') or '').strip(),
        gst_number=(post_data.get('gst_number') or '').strip(),
        notes=(post_data.get('notes') or '').strip(),
    )


def update_supplier_from_post(supplier, post_data):
    """Update a Supplier from form POST data."""
    name = (post_data.get('name') or '').strip()
    if not name:
        raise ValidationError('Supplier name is required.')

    supplier.name = name
    supplier.contact_person = (post_data.get('contact_person') or '').strip()
    supplier.phone = (post_data.get('phone') or '').strip()
    supplier.alt_phone = (post_data.get('alt_phone') or '').strip()
    supplier.email = (post_data.get('email') or '').strip()
    supplier.address = (post_data.get('address') or '').strip()
    supplier.city = (post_data.get('city') or '').strip()
    supplier.gst_number = (post_data.get('gst_number') or '').strip()
    supplier.notes = (post_data.get('notes') or '').strip()
    supplier.save()
    return supplier

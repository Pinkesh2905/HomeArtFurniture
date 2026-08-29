from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Material, Supplier, StockTransaction, MaterialCategory, UnitOfMeasure, TransactionType
from .services import (
    create_material_from_post, update_material_from_post,
    create_supplier_from_post, update_supplier_from_post,
    record_stock_in, record_stock_out, record_adjustment, record_damage,
)


# ── Material Views ──

@login_required
def material_list(request):
    materials = Material.objects.filter(is_active=True).select_related('supplier')

    # Search
    q = request.GET.get('q', '').strip()
    if q:
        materials = materials.filter(
            Q(name__icontains=q) | Q(sku__icontains=q) | Q(supplier__name__icontains=q)
        )

    # Category filter
    category = request.GET.get('category', '')
    if category:
        materials = materials.filter(category=category)

    # Stock status filter
    stock_filter = request.GET.get('stock', '')
    if stock_filter == 'low':
        materials = [m for m in materials if m.is_low_stock and not m.is_out_of_stock]
    elif stock_filter == 'out':
        materials = [m for m in materials if m.is_out_of_stock]
    else:
        materials = list(materials)

    # Summary metrics
    all_materials = Material.objects.filter(is_active=True)
    total_count = all_materials.count()
    low_stock_count = sum(1 for m in all_materials if m.is_low_stock and m.current_stock > 0)
    out_of_stock_count = sum(1 for m in all_materials if m.is_out_of_stock)
    total_value = sum(m.stock_value for m in all_materials)

    context = {
        'materials': materials,
        'categories': MaterialCategory.choices,
        'q': q,
        'category': category,
        'stock_filter': stock_filter,
        'total_count': total_count,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'total_value': total_value,
    }
    return render(request, 'inventory/material_list.html', context)


@login_required
def material_detail(request, material_id):
    material = get_object_or_404(Material, pk=material_id)
    transactions = material.transactions.select_related('supplier').order_by('-date', '-created_at')[:50]

    context = {
        'material': material,
        'transactions': transactions,
        'transaction_types': TransactionType.choices,
    }
    return render(request, 'inventory/material_detail.html', context)


@login_required
def material_create(request):
    if request.method == 'POST':
        try:
            material = create_material_from_post(request.POST)
            messages.success(request, f'Material "{material.name}" created with SKU {material.sku}.')
            return redirect('material_detail', material_id=material.pk)
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))

    context = {
        'categories': MaterialCategory.choices,
        'units': UnitOfMeasure.choices,
        'suppliers': Supplier.objects.filter(is_active=True),
        'editing': False,
    }
    return render(request, 'inventory/material_form.html', context)


@login_required
def material_edit(request, material_id):
    material = get_object_or_404(Material, pk=material_id)

    if request.method == 'POST':
        try:
            update_material_from_post(material, request.POST)
            messages.success(request, f'Material "{material.name}" updated.')
            return redirect('material_detail', material_id=material.pk)
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))

    context = {
        'material': material,
        'categories': MaterialCategory.choices,
        'units': UnitOfMeasure.choices,
        'suppliers': Supplier.objects.filter(is_active=True),
        'editing': True,
    }
    return render(request, 'inventory/material_form.html', context)


@login_required
@require_POST
def material_delete(request, material_id):
    material = get_object_or_404(Material, pk=material_id)
    material.is_active = False
    material.save(update_fields=['is_active', 'updated_at'])
    messages.success(request, f'Material "{material.name}" archived.')
    return redirect('material_list')


@login_required
def stock_transaction(request, material_id):
    material = get_object_or_404(Material, pk=material_id)

    if request.method == 'POST':
        txn_type = request.POST.get('transaction_type', '')
        quantity = request.POST.get('quantity', '0')
        unit_cost = request.POST.get('unit_cost', '0')
        reference = (request.POST.get('reference') or '').strip()
        notes = (request.POST.get('notes') or '').strip()
        date_str = request.POST.get('date', '')
        from django.utils.dateparse import parse_date
        date = parse_date(date_str) if date_str else timezone.localdate()

        supplier_id = request.POST.get('supplier')
        supplier = None
        if supplier_id:
            try:
                supplier = Supplier.objects.get(pk=int(supplier_id))
            except (Supplier.DoesNotExist, ValueError):
                pass

        try:
            if txn_type == TransactionType.STOCK_IN:
                record_stock_in(material, quantity, unit_cost, supplier, reference, notes, date)
                messages.success(request, f'Stocked in {quantity} {material.get_unit_display()} of {material.name}.')
            elif txn_type == TransactionType.STOCK_OUT:
                record_stock_out(material, quantity, reference, notes, date)
                messages.success(request, f'Stocked out {quantity} {material.get_unit_display()} of {material.name}.')
            elif txn_type == TransactionType.ADJUSTMENT:
                record_adjustment(material, quantity, notes, date)
                messages.success(request, f'Stock adjusted to {quantity} {material.get_unit_display()}.')
            elif txn_type == TransactionType.DAMAGED:
                record_damage(material, quantity, notes, date)
                messages.success(request, f'Recorded {quantity} {material.get_unit_display()} as damaged.')
            else:
                messages.error(request, 'Invalid transaction type.')
            return redirect('material_detail', material_id=material.pk)
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))

    context = {
        'material': material,
        'transaction_types': TransactionType.choices,
        'suppliers': Supplier.objects.filter(is_active=True),
        'today': timezone.localdate(),
    }
    return render(request, 'inventory/stock_transaction_form.html', context)


# ── Supplier Views ──

@login_required
def supplier_list(request):
    suppliers = Supplier.objects.filter(is_active=True)
    q = request.GET.get('q', '').strip()
    if q:
        suppliers = suppliers.filter(Q(name__icontains=q) | Q(phone__icontains=q) | Q(city__icontains=q))

    context = {
        'suppliers': suppliers,
        'q': q,
    }
    return render(request, 'inventory/supplier_list.html', context)


@login_required
def supplier_create(request):
    if request.method == 'POST':
        try:
            supplier = create_supplier_from_post(request.POST)
            messages.success(request, f'Supplier "{supplier.name}" added.')
            return redirect('supplier_list')
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))

    return render(request, 'inventory/supplier_form.html', {'editing': False})


@login_required
def supplier_edit(request, supplier_id):
    supplier = get_object_or_404(Supplier, pk=supplier_id)

    if request.method == 'POST':
        try:
            update_supplier_from_post(supplier, request.POST)
            messages.success(request, f'Supplier "{supplier.name}" updated.')
            return redirect('supplier_list')
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))

    return render(request, 'inventory/supplier_form.html', {'supplier': supplier, 'editing': True})


@login_required
@require_POST
def supplier_delete(request, supplier_id):
    supplier = get_object_or_404(Supplier, pk=supplier_id)
    supplier.is_active = False
    supplier.save(update_fields=['is_active', 'updated_at'])
    messages.success(request, f'Supplier "{supplier.name}" archived.')
    return redirect('supplier_list')


# ── Print View ──

@login_required
def inventory_print(request):
    materials = Material.objects.filter(is_active=True).select_related('supplier').order_by('category', 'name')
    generated_at = timezone.localtime()

    total_value = sum(m.stock_value for m in materials)
    low_stock_count = sum(1 for m in materials if m.is_low_stock)

    context = {
        'materials': materials,
        'generated_at': generated_at,
        'total_value': total_value,
        'low_stock_count': low_stock_count,
    }
    return render(request, 'inventory/inventory_print.html', context)

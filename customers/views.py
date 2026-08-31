import re
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.db.models import Q, Count, Sum
from .models import Customer
from .utils import normalize_phone, validate_phone, extract_local_phone
from measurements.models import FurnitureDimension

@login_required
def api_get_customer_by_phone(request, phone):
    phone = normalize_phone(phone)
    customer = Customer.objects.filter(phone=phone).order_by('-updated_at').first()
    if not customer and not phone.startswith('+'):
        customer = Customer.objects.filter(phone__endswith=phone).order_by('-updated_at').first()

    if customer:
        dimensions = FurnitureDimension.objects.filter(customer=customer)
        
        dimension_data = {}
        dimension_list = []
        for m in dimensions:
            dimension_data[m.furniture_type] = {
                'id': m.id,
                'values': m.values,
                'notes': m.notes,
                'is_sample_product': m.is_standard_catalog  # Kept key name as is_sample_product to avoid breaking JS scripts
            }
            dimension_list.append({
                'id': m.id,
                'category': m.furniture_type,
                'values': m.values,
                'notes': m.notes,
                'is_sample_product': m.is_standard_catalog
            })

        return JsonResponse({
            'success': True,
            'customer': {
                'id': customer.id,
                'full_name': customer.full_name,
                'phone': customer.phone,
                'city': customer.city or '',
            },
            'measurements': dimension_data,  # Kept key name as measurements to avoid breaking JS scripts
            'measurement_list': dimension_list
        })
    else:
        return JsonResponse({'success': False, 'message': 'Customer not found'})

@login_required
def api_search_customers(request):
    """Search customers by name or phone. Returns up to 10 results."""
    q = (request.GET.get('q') or '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    normalized_q = normalize_phone(q)
    customers = Customer.objects.filter(is_archived=False).filter(
        Q(full_name__icontains=q) | Q(phone__icontains=normalized_q or q)
    ).prefetch_related('measurements').order_by('-created_at')[:10]

    results = []
    for c in customers:
        dimensions_qs = c.measurements.all()
        dimension_data = {}
        dimension_list = []
        furniture_list = []
        for m in dimensions_qs:
            dimension_data[m.furniture_type] = {
                'id': m.id,
                'values': m.values,
                'notes': m.notes,
                'is_sample_product': m.is_standard_catalog
            }
            dimension_list.append({
                'id': m.id,
                'category': m.furniture_type,
                'values': m.values,
                'notes': m.notes,
                'is_sample_product': m.is_standard_catalog
            })
            furniture_list.append(m.furniture_type)

        results.append({
            'id': c.id,
            'full_name': c.full_name,
            'phone': c.phone,
            'city': c.city or '',
            'furniture': furniture_list,
            'measurements': dimension_data,
            'measurement_list': dimension_list,
        })

    return JsonResponse({'results': results})

from django.core.paginator import Paginator

@login_required
def customer_list(request):
    show_archived = request.GET.get('archived') == 'true'
    base_customers = Customer.objects.annotate(num_orders=Count('orders'))
    
    active_count = Customer.objects.filter(is_archived=False).count()
    archived_count = Customer.objects.filter(is_archived=True).count()
    
    if show_archived:
        customers = base_customers.filter(is_archived=True).order_by('-updated_at')
    else:
        customers = base_customers.filter(is_archived=False).order_by('-created_at')
    
    # Simple search
    q = request.GET.get('q')
    if q:
        normalized_q = normalize_phone(q)
        customers = customers.filter(
            Q(full_name__icontains=q)
            | Q(phone__icontains=normalized_q or q)
            | Q(city__icontains=q)
        )
    
    paginator = Paginator(customers, 10)  # Show 10 customers per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
        
    context = {
        'customers': page_obj,
        'q': q,
        'show_archived': show_archived,
        'active_count': active_count,
        'archived_count': archived_count,
    }
    return render(request, 'customers/customer_list.html', context)

@login_required
def customer_detail(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    orders = customer.orders.all().order_by('-created_at')
    dimensions = customer.measurements.all().order_by('-updated_at')
    
    # Calculate lifetime value
    lifetime_value = orders.exclude(status='cancelled').aggregate(total=Sum('final_amount'))['total'] or Decimal('0.00')
    order_count = orders.count()
    
    context = {
        'customer': customer,
        'orders': orders,
        'measurements': dimensions,  # Kept template key name as measurements to avoid changing customer_detail.html
        'lifetime_value': lifetime_value,
        'order_count': order_count,
    }
    return render(request, 'customers/customer_detail.html', context)


@login_required
def customer_create(request):
    from django.contrib import messages

    if request.method == 'POST':
        full_name = (request.POST.get('full_name') or '').strip()
        phone_local = (request.POST.get('phone') or '').strip()
        country_code = (request.POST.get('country_code') or '+91').strip()
        city = (request.POST.get('city') or '').strip()

        if not full_name or not phone_local:
            messages.error(request, 'Customer name and phone number are required.')
            return render(request, 'customers/customer_form.html', {
                'form_data': request.POST,
            })

        # Server-side check: local phone must be exactly 10 numeric digits
        local_digits = re.sub(r'\D+', '', phone_local)
        if len(local_digits) != 10:
            messages.error(request, f'Phone number must be exactly 10 digits (got {len(local_digits)} digits).')
            return render(request, 'customers/customer_form.html', {
                'form_data': request.POST,
            })

        if not country_code.startswith('+'):
            country_code = '+' + country_code
        phone = normalize_phone(country_code + local_digits)

        try:
            validate_phone(phone)
        except ValidationError as e:
            messages.error(request, str(e.messages[0]) if hasattr(e, 'messages') else str(e))
            return render(request, 'customers/customer_form.html', {
                'form_data': request.POST,
            })

        # Check for existing customer with same phone
        existing = Customer.objects.filter(phone=phone).first()
        if existing:
            if existing.full_name.strip().lower() == full_name.strip().lower():
                messages.info(request, f'Customer "{existing.full_name}" with phone {phone} already exists. Redirecting to their profile.')
                return redirect('customer_detail', customer_id=existing.id)
            elif request.POST.get('confirm_create') != 'true':
                messages.warning(request, f'A customer with this phone number already exists: {existing.full_name}. Create a new separate customer anyway?')
                return render(request, 'customers/customer_form.html', {
                    'form_data': request.POST,
                    'existing_customer': existing,
                    'confirm_prompt': True,
                })

        try:
            customer = Customer.objects.create(
                full_name=full_name,
                phone=phone,
                city=city,
            )
        except ValidationError as e:
            messages.error(request, str(e.messages[0]) if hasattr(e, 'messages') else str(e))
            return render(request, 'customers/customer_form.html', {
                'form_data': request.POST,
            })

        messages.success(request, f'Customer "{customer.full_name}" created successfully.')
        return redirect('customer_detail', customer_id=customer.id)

    return render(request, 'customers/customer_form.html', {})


@login_required
def customer_edit(request, customer_id):
    from django.contrib import messages

    customer = get_object_or_404(Customer, id=customer_id)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.POST.get('is_ajax') == 'true'

    if request.method == 'POST':
        full_name = (request.POST.get('full_name') or '').strip()
        phone_local = (request.POST.get('phone') or '').strip()
        country_code = (request.POST.get('country_code') or '+91').strip()
        city = (request.POST.get('city') or '').strip()

        if not full_name or not phone_local:
            err_msg = 'Customer name and phone number are required.'
            if is_ajax:
                return JsonResponse({'success': False, 'message': err_msg}, status=400)
            messages.error(request, err_msg)
            return redirect('customer_detail', customer_id=customer.id)

        local_digits = re.sub(r'\D+', '', phone_local)
        if len(local_digits) != 10:
            err_msg = f'Phone number must be exactly 10 digits (got {len(local_digits)} digits).'
            if is_ajax:
                return JsonResponse({'success': False, 'message': err_msg}, status=400)
            messages.error(request, err_msg)
            return redirect('customer_detail', customer_id=customer.id)

        if not country_code.startswith('+'):
            country_code = '+' + country_code
        phone = normalize_phone(country_code + local_digits)

        try:
            validate_phone(phone)
        except ValidationError as e:
            err_msg = str(e.messages[0]) if hasattr(e, 'messages') else str(e)
            if is_ajax:
                return JsonResponse({'success': False, 'message': err_msg}, status=400)
            messages.error(request, err_msg)
            return redirect('customer_detail', customer_id=customer.id)

        # Check duplicate phone for other customers
        duplicate = Customer.objects.filter(phone=phone).exclude(id=customer.id).first()
        if duplicate:
            err_msg = f'Another customer ({duplicate.full_name}) already has the phone number {phone}.'
            if is_ajax:
                return JsonResponse({'success': False, 'message': err_msg}, status=400)
            messages.error(request, err_msg)
            return redirect('customer_detail', customer_id=customer.id)

        customer.full_name = full_name
        customer.phone = phone
        customer.city = city
        try:
            customer.save()
        except ValidationError as e:
            err_msg = str(e.messages[0]) if hasattr(e, 'messages') else str(e)
            if is_ajax:
                return JsonResponse({'success': False, 'message': err_msg}, status=400)
            messages.error(request, err_msg)
            return redirect('customer_detail', customer_id=customer.id)

        success_msg = f'Customer "{customer.full_name}" details updated successfully.'
        if is_ajax:
            return JsonResponse({
                'success': True,
                'message': success_msg,
                'customer': {
                    'id': customer.id,
                    'full_name': customer.full_name,
                    'phone': customer.phone,
                    'city': customer.city or '',
                    'initial': customer.full_name[:1].upper() if customer.full_name else 'C',
                }
            })

        messages.success(request, success_msg)
        return redirect('customer_detail', customer_id=customer.id)

    # GET request handler for pre-filling edit modal
    if is_ajax:
        local_p = extract_local_phone(customer.phone)
        cc = '+91'
        if customer.phone.startswith('+') and not customer.phone.startswith('+91'):
            cc = customer.phone[:customer.phone.find(local_p)]
        return JsonResponse({
            'id': customer.id,
            'full_name': customer.full_name,
            'country_code': cc,
            'phone': local_p,
            'city': customer.city or '',
        })

    return redirect('customer_detail', customer_id=customer.id)


@login_required
def customer_delete(request, customer_id):
    """
    Deletes customer if 0 orders exist.
    If 1 or more orders exist, hard delete is blocked and customer is archived instead
    to protect invoices and financial history.
    """
    from django.contrib import messages
    customer = get_object_or_404(Customer, id=customer_id)
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == 'true'
    order_count = customer.orders.count()

    if request.method == 'POST':
        if order_count > 0:
            # Block hard delete! Fallback to archive
            customer.is_archived = True
            customer.save()
            msg = f'"{customer.full_name}" has {order_count} order(s) and cannot be deleted. Customer was archived instead to preserve financial records.'
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'action': 'archived_instead',
                    'message': msg,
                    'redirect_url': reverse('customer_detail', args=[customer.id])
                }, status=400)
            messages.warning(request, msg)
            return redirect('customer_detail', customer_id=customer.id)

        # 0 orders: genuine hard delete
        name = customer.full_name
        customer.delete()
        msg = f'Customer "{name}" has been permanently deleted.'
        if is_ajax:
            return JsonResponse({
                'success': True,
                'action': 'deleted',
                'message': msg,
                'redirect_url': reverse('customer_list')
            })
        messages.success(request, msg)
        return redirect('customer_list')

    # GET requests not supported for deletion
    return redirect('customer_detail', customer_id=customer.id)


@login_required
def customer_archive(request, customer_id):
    """Archives customer, hiding them from default directory list and search."""
    from django.contrib import messages
    customer = get_object_or_404(Customer, id=customer_id)
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == 'true'

    if request.method == 'POST':
        customer.is_archived = True
        customer.save(update_fields=['is_archived', 'updated_at'])
        msg = f'Customer "{customer.full_name}" has been archived and hidden from the active directory.'
        
        next_url = request.POST.get('next') or request.GET.get('next')
        if not next_url or not next_url.startswith('/'):
            next_url = reverse('customer_detail', args=[customer.id])

        if is_ajax:
            return JsonResponse({
                'success': True,
                'action': 'archived',
                'message': msg,
                'redirect_url': next_url
            })
        messages.success(request, msg)
        return redirect(next_url)

    return redirect('customer_detail', customer_id=customer.id)


@login_required
def customer_unarchive(request, customer_id):
    """Restores customer to active directory."""
    from django.contrib import messages
    customer = get_object_or_404(Customer, id=customer_id)
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == 'true'

    if request.method == 'POST':
        customer.is_archived = False
        customer.save(update_fields=['is_archived', 'updated_at'])
        msg = f'Customer "{customer.full_name}" has been restored to the active directory.'

        next_url = request.POST.get('next') or request.GET.get('next')
        if not next_url or not next_url.startswith('/'):
            next_url = reverse('customer_detail', args=[customer.id])

        if is_ajax:
            return JsonResponse({
                'success': True,
                'action': 'unarchived',
                'message': msg,
                'redirect_url': next_url
            })
        messages.success(request, msg)
        return redirect(next_url)

    return redirect('customer_detail', customer_id=customer.id)



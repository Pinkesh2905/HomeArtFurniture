from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, Count
from .models import Customer
from .utils import normalize_phone
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
    customers = Customer.objects.filter(
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
            'garments': furniture_list,  # Kept key name as garments to avoid breaking JS scripts
            'measurements': dimension_data,
            'measurement_list': dimension_list,
        })

    return JsonResponse({'results': results})

from django.core.paginator import Paginator

@login_required
def customer_list(request):
    customers = Customer.objects.annotate(num_orders=Count('orders')).order_by('-created_at')
    
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
    }
    return render(request, 'customers/customer_list.html', context)

@login_required
def customer_detail(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    orders = customer.orders.all().order_by('-created_at')
    dimensions = customer.measurements.all().order_by('-updated_at')
    
    # Calculate lifetime value
    lifetime_value = sum(order.final_amount for order in orders if order.status != 'cancelled')
    
    context = {
        'customer': customer,
        'orders': orders,
        'measurements': dimensions,  # Kept template key name as measurements to avoid changing customer_detail.html
        'lifetime_value': lifetime_value,
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
            messages.error(request, 'Customer name and phone are required.')
            return render(request, 'customers/customer_form.html', {
                'form_data': request.POST,
            })

        if not country_code.startswith('+'):
            country_code = '+' + country_code
        phone = normalize_phone(country_code + phone_local)

        # Check for existing customer with same phone
        existing = Customer.objects.filter(phone=phone).first()
        if existing:
            messages.info(request, f'Customer with phone {phone} already exists. Redirecting to their profile.')
            return redirect('customer_detail', customer_id=existing.id)

        customer = Customer.objects.create(
            full_name=full_name,
            phone=phone,
            city=city,
        )
        messages.success(request, f'Customer "{customer.full_name}" created successfully.')
        return redirect('customer_detail', customer_id=customer.id)

    return render(request, 'customers/customer_form.html', {})


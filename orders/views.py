from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from measurements.models import get_all_furniture_types
from customers.models import Customer
from .models import Order, OrderItem, OrderStatus, OrderType, PaymentMethod
from .services import create_order_from_post, update_order_from_post, update_order_info_from_post, update_order_item_from_post

@login_required
def order_create(request):
    if request.method == 'POST':
        customer_id = request.POST.get('customer_id')
        customer = get_object_or_404(Customer, id=customer_id)
        try:
            order = create_order_from_post(request.POST, customer)
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
            garments = ','.join(request.POST.getlist('item_furniture_type[]'))
            FurnitureDimensions = ','.join(request.POST.getlist('item_FurnitureDimension_id[]'))
            return redirect(f"{reverse('order_create')}?customer_id={customer.id}&garments={garments}&FurnitureDimensions={FurnitureDimensions}")
        return redirect(reverse('order_print', args=[order.id]))

    customer_id = request.GET.get('customer_id')
    garments_qs = request.GET.get('garments', '')
    FurnitureDimensions_qs = request.GET.get('FurnitureDimensions') or request.GET.get('measurements') or request.GET.get('dimensions') or ''
    
    if not customer_id:
        # If accessed directly, redirect back to FurnitureDimensions profile
        return redirect(reverse('measurement_profile'))
        
    customer = get_object_or_404(Customer, id=customer_id)
    order_type = request.GET.get('order_type') or OrderType.CUSTOM_BUILD
    
    # Generate temporary order number for display (will be finalized on save)
    today = timezone.localdate().strftime('%Y%m%d')
    last_order = Order.objects.order_by('-id').first()
    next_id = last_order.id + 1 if last_order else 1
    mock_order_id = f"HAF-{today}-{next_id:03d}"

    from measurements.models import FurnitureDimension
    # Build initial list of items
    selected_items = []
    all_cats = dict(get_all_furniture_types())

    if FurnitureDimensions_qs:
        FurnitureDimension_ids = [x.strip() for x in FurnitureDimensions_qs.split(',') if x.strip()]
        for m_id in FurnitureDimension_ids:
            try:
                m = FurnitureDimension.objects.get(id=m_id, customer=customer)
                label = all_cats.get(m.furniture_type, m.furniture_type.title())
                selected_items.append({
                    'type': m.furniture_type,
                    'label': label,
                    'qty': 1,
                    'rate': '',
                    'FurnitureDimension_id': m.id,
                    'measurement_id': m.id,
                })
            except (FurnitureDimension.DoesNotExist, ValueError):
                continue
    else:
        garment_types = garments_qs.split(',') if garments_qs else []
        for gtype in garment_types:
            if not gtype: continue
            label = all_cats.get(gtype, gtype.title())
            selected_items.append({
                'type': gtype,
                'label': label,
                'qty': 1,
                'rate': '',
                'FurnitureDimension_id': ''
            })

    context = {
        'customer': customer,
        'order_number': mock_order_id,
        'selected_items': selected_items,
        'order_types': OrderType.choices,
        'current_order_type': order_type,
    }
    return render(request, 'orders/order_form.html', context)


def num2words(num):
    # Very basic Indian numbering system converter up to Crores
    under_20 = ['Zero', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen']
    tens = ['Zero', 'Ten', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']

    if num == 0: return under_20[0]
    
    def convert(n):
        if n < 20:
            return under_20[n]
        if n < 100:
            return tens[n // 10] + ('' if n % 10 == 0 else ' ' + under_20[n % 10])
        if n < 1000:
            return under_20[n // 100] + ' Hundred' + ('' if n % 100 == 0 else ' and ' + convert(n % 100))
        if n < 100000:
            return convert(n // 1000) + ' Thousand' + ('' if n % 1000 == 0 else ' ' + convert(n % 1000))
        if n < 10000000:
            return convert(n // 100000) + ' Lakh' + ('' if n % 100000 == 0 else ' ' + convert(n % 100000))
        return convert(n // 10000000) + ' Crore' + ('' if n % 10000000 == 0 else ' ' + convert(n % 10000000))
    
    return convert(int(num)) + ' Only'

@login_required
def order_print(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    items = order.items.all()
    
    # Get FurnitureDimensions for each item in the order
    FurnitureDimensions = []
    from measurements.models import get_all_furniture_parameters, get_all_furniture_types
    all_params = get_all_furniture_parameters()
    all_cats = dict(get_all_furniture_types())

    for item in items:
        m = item.dimension
        if m:
            params = all_params.get(m.furniture_type, [])
            ordered_values = []
            for p in params:
                ordered_values.append({'label': p, 'value': m.values.get(p, '-')})
            
            FurnitureDimensions.append({
                'category_display': all_cats.get(m.furniture_type, m.furniture_type.title()),
                'data': ordered_values,
                'notes': m.notes,
                'is_standard_catalog': m.is_standard_catalog
            })
        elif item.furniture_type:
            # Fallback for legacy items
            from measurements.models import FurnitureDimension
            m = FurnitureDimension.objects.filter(customer=order.customer, furniture_type=item.furniture_type).order_by('-updated_at').first()
            if m:
                params = all_params.get(item.furniture_type, [])
                ordered_values = []
                for p in params:
                    ordered_values.append({'label': p, 'value': m.values.get(p, '-')})
                
                FurnitureDimensions.append({
                    'category_display': all_cats.get(item.furniture_type, item.furniture_type.title()),
                    'data': ordered_values,
                    'notes': m.notes,
                    'is_standard_catalog': m.is_standard_catalog
                })
                
    amount_in_words = num2words(order.final_amount)

    # Limit table rows to 6 (items + fillers) to prevent A5 page overflow
    max_total_rows = 6
    num_items = len(items)
    num_fillers = max(0, max_total_rows - num_items)
    filler_rows = range(num_fillers)

    # Chunk FurnitureDimensions into groups of max 3 items
    FurnitureDimension_groups = [FurnitureDimensions[i:i+3] for i in range(0, len(FurnitureDimensions), 3)]

    original_only = request.GET.get('original_only') == 'true'

    context = {
        'order': order,
        'items': items,
        'FurnitureDimensions': FurnitureDimensions,
        'FurnitureDimension_groups': FurnitureDimension_groups,
        'filler_rows': filler_rows,
        'amount_in_words': amount_in_words,
        'original_only': original_only,
    }
    return render(request, 'orders/order_print.html', context)

def filtered_orders_from_request(request):
    orders = Order.objects.select_related('customer').all().order_by('-created_at')
    
    status = request.GET.get('status')
    if status:
        orders = orders.filter(status=status)

    q = (request.GET.get('q') or '').strip()
    if q:
        orders = orders.filter(
            Q(order_number__icontains=q)
            | Q(customer__full_name__icontains=q)
            | Q(customer__phone__icontains=q)
        )

    red_flag = request.GET.get('red_flag')
    if red_flag == '1':
        orders = orders.filter(is_red_flagged=True)

    date_str = request.GET.get('date') or request.GET.get('delivery_date') or request.GET.get('delivery_from')
    order_date_val = parse_date(date_str) if date_str else None

    if order_date_val:
        orders = orders.filter(date=order_date_val)

    due = request.GET.get('due')
    today = timezone.localdate()
    if due == 'balance':
        orders = orders.filter(grand_total__gt=0)
    elif due == 'today':
        orders = orders.filter(date=today).exclude(status__in=[OrderStatus.DELIVERED, OrderStatus.CANCELLED])
    elif due == 'overdue':
        orders = orders.filter(date__lt=today).exclude(status__in=[OrderStatus.DELIVERED, OrderStatus.CANCELLED])

    return orders, {
        'current_status': status,
        'statuses': OrderStatus.choices,
        'q': q,
        'delivery_date': order_date_val,
        'due': due,
        'red_flag': red_flag,
    }


@login_required
def order_list(request):
    orders, filters_context = filtered_orders_from_request(request)

    context = {
        'orders': orders,
        **filters_context,
    }
    return render(request, 'orders/order_list.html', context)


@login_required
def order_list_print(request):
    orders, filters_context = filtered_orders_from_request(request)
    generated_at = timezone.localtime()
    total_amount = sum(order.final_amount for order in orders)

    context = {
        'orders': orders,
        'generated_at': generated_at,
        'total_amount': total_amount,
        **filters_context,
    }
    return render(request, 'orders/order_list_print.html', context)

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        try:
            update_order_from_post(order, request.POST)
            messages.success(request, 'Order updated.')
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
        return redirect('order_detail', order_id=order.id)
        
    items = order.items.all()
    
    import urllib.parse
    # Generate WhatsApp Message
    msg = f"Hello {order.customer.full_name},\n\n"
    msg += f"Thank you for your order ({order.order_number}) at Home Art Furniture!\n\n"
    msg += f"*Order Summary:*\n"
    msg += f"Total Bill: ₹{order.final_amount}\n"
    if order.advance_paid > 0:
        msg += f"Advance Paid: ₹{order.advance_paid}\n"
    if order.balance_due > 0:
        msg += f"Pending Balance: ₹{order.balance_due}\n"
        
    public_invoice_url = request.build_absolute_uri(reverse('public_invoice', args=[order.access_token]))
    msg += f"\nClick here to view or download your detailed bill:\n{public_invoice_url}"
    
    encoded_msg = urllib.parse.quote(msg)
    
    phone = order.customer.phone
    # Strip spaces or special chars
    phone = ''.join(filter(str.isdigit, phone))
    # Add country code if missing (assuming India default as per project context)
    if len(phone) == 10:
        phone = '91' + phone
        
    whatsapp_link = f"https://wa.me/{phone}?text={encoded_msg}"
    
    from measurements.models import get_all_furniture_parameters
    context = {
        'order': order,
        'items': items,
        'statuses': OrderStatus.choices,
        'balance_due': order.balance_due,
        'garment_parameters': get_all_furniture_parameters(),
        'whatsapp_link': whatsapp_link,
    }
    return render(request, 'orders/order_detail.html', context)


@login_required
def delivery_schedule(request):
    from django.db.models import Sum, Count
    today = timezone.localdate()

    from django.utils.dateparse import parse_date
    
    # Parse filter inputs
    filter_date_str = request.GET.get('date', '')
    filter_from_str = request.GET.get('from', '')
    filter_to_str = request.GET.get('to', '')
    
    filter_date = parse_date(filter_date_str) if filter_date_str else None
    filter_from = parse_date(filter_from_str) if filter_from_str else None
    filter_to = parse_date(filter_to_str) if filter_to_str else None
    
    filter_status = request.GET.get('status', '')
    q = (request.GET.get('q') or '').strip()

    orders = Order.objects.select_related('customer').prefetch_related('items').order_by('date', 'customer__full_name')

    # Default: if no filters at all, show next 30 days + overdue
    if not any([filter_date_str, filter_from_str, filter_to_str, filter_status, q]):
        orders = orders.exclude(status__in=[OrderStatus.DELIVERED, OrderStatus.CANCELLED])
    else:
        if filter_date:
            orders = orders.filter(date=filter_date)
        if filter_from:
            orders = orders.filter(date__gte=filter_from)
        if filter_to:
            orders = orders.filter(date__lte=filter_to)
        if filter_status:
            orders = orders.filter(status=filter_status)
        if q:
            orders = orders.filter(
                Q(order_number__icontains=q)
                | Q(customer__full_name__icontains=q)
                | Q(customer__phone__icontains=q)
            )

    # Group orders by date
    from collections import defaultdict
    grouped = defaultdict(list)
    for order in orders:
        grouped[order.date].append(order)

    # Sort groups: overdue first, then ascending
    def sort_key(d):
        return (0 if d < today else 1, d)

    grouped_sorted = sorted(grouped.items(), key=lambda x: sort_key(x[0]))

    # Summary stats
    total_orders = orders.count()
    overdue_count = orders.filter(date__lt=today).exclude(status__in=[OrderStatus.DELIVERED, OrderStatus.CANCELLED]).count()
    due_today_count = orders.filter(date=today).exclude(status__in=[OrderStatus.DELIVERED, OrderStatus.CANCELLED]).count()
    total_balance = sum(o.balance_due for o in orders)

    context = {
        'grouped_orders': grouped_sorted,
        'today': today,
        'filter_date': filter_date,
        'filter_from': filter_from,
        'filter_to': filter_to,
        'filter_status': filter_status,
        'statuses': OrderStatus.choices,
        'q': q,
        'total_orders': total_orders,
        'overdue_count': overdue_count,
        'due_today_count': due_today_count,
        'total_balance': total_balance,
    }
    return render(request, 'orders/delivery_schedule.html', context)


@login_required
def order_delete(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == 'POST':
        order_number = order.order_number
        customer_name = order.customer.full_name
        order.delete()  # CASCADE deletes OrderItems automatically
        messages.success(request, f'Order {order_number} for {customer_name} has been permanently deleted.')
        return redirect('order_list')
    # If GET, just redirect back (no GET-based deletion)
    return redirect('order_detail', order_id=order_id)

@login_required
def order_edit_info(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == 'POST':
        try:
            update_order_info_from_post(order, request.POST)
            messages.success(request, 'Order info updated.')
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
    return redirect('order_detail', order_id=order_id)

@login_required
def order_item_edit(request, order_id, item_id):
    order = get_object_or_404(Order, id=order_id)
    item = get_object_or_404(OrderItem, id=item_id, order=order)
    if request.method == 'POST':
        try:
            update_order_item_from_post(item, request.POST)
            messages.success(request, f'Item "{item.description}" updated.')
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
    return redirect('order_detail', order_id=order_id)


@login_required
@require_POST
def api_update_order_shortcut(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    # Extract data from POST
    status = request.POST.get('status')
    payment_amount_str = request.POST.get('payment_amount')
    payment_method = request.POST.get('payment_method')
    
    post_data = {}
    if status:
        post_data['status'] = status
    if payment_amount_str:
        post_data['additional_payment'] = payment_amount_str
    if payment_method:
        post_data['payment_method'] = payment_method
        
    errors = []
    if post_data:
        try:
            update_order_from_post(order, post_data)
        except ValidationError as exc:
            errors.extend(exc.messages)
            
    if errors:
        return JsonResponse({'success': False, 'errors': errors})
        
    return JsonResponse({
        'success': True,
        'order_id': order.id,
        'grand_total': str(order.grand_total),
        'status': order.status,
        'status_display': order.get_status_display(),
        'advance_paid': str(order.advance_paid),
        'payment_method': order.payment_method,
        'payment_method_display': order.get_payment_method_display(),
    })


@login_required
def payment_report(request):
    from datetime import datetime, timedelta
    
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    today = timezone.localdate()
    if not start_date_str:
        start_date = today - timedelta(days=30)
    else:
        start_date = parse_date(start_date_str) or (today - timedelta(days=30))
        
    if not end_date_str:
        end_date = today
    else:
        end_date = parse_date(end_date_str) or today
        
    # Query orders in this date range
    orders = Order.objects.filter(date__range=[start_date, end_date]).select_related('customer')
    
    # Categorize
    cash_orders = orders.filter(payment_method=PaymentMethod.CASH).order_by('-date')
    upi_orders = orders.filter(payment_method=PaymentMethod.UPI).order_by('-date')
    
    # Metrics
    total_cash_advance = sum(o.advance_paid for o in cash_orders)
    total_upi_advance = sum(o.advance_paid for o in upi_orders)
    total_advance = total_cash_advance + total_upi_advance
    
    total_cash_pending = sum(o.grand_total for o in cash_orders)
    total_upi_pending = sum(o.grand_total for o in upi_orders)
    total_pending = total_cash_pending + total_upi_pending
    
    context = {
        'cash_orders': cash_orders,
        'upi_orders': upi_orders,
        'start_date': start_date,
        'end_date': end_date,
        'total_cash_advance': total_cash_advance,
        'total_upi_advance': total_upi_advance,
        'total_advance': total_advance,
        'total_cash_pending': total_cash_pending,
        'total_upi_pending': total_upi_pending,
        'total_pending': total_pending,
        'cash_count': cash_orders.count(),
        'upi_count': upi_orders.count(),
    }
    return render(request, 'orders/payment_report.html', context)


@login_required
def payment_report_print(request):
    from datetime import datetime, timedelta
    
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    today = timezone.localdate()
    if not start_date_str:
        start_date = today - timedelta(days=30)
    else:
        start_date = parse_date(start_date_str) or (today - timedelta(days=30))
        
    if not end_date_str:
        end_date = today
    else:
        end_date = parse_date(end_date_str) or today
        
    # Query orders in this date range
    orders = Order.objects.filter(date__range=[start_date, end_date]).select_related('customer')
    
    # Categorize
    cash_orders = orders.filter(payment_method=PaymentMethod.CASH).order_by('-date')
    upi_orders = orders.filter(payment_method=PaymentMethod.UPI).order_by('-date')
    
    # Metrics
    total_cash_advance = sum(o.advance_paid for o in cash_orders)
    total_upi_advance = sum(o.advance_paid for o in upi_orders)
    total_advance = total_cash_advance + total_upi_advance
    
    total_cash_pending = sum(o.grand_total for o in cash_orders)
    total_upi_pending = sum(o.grand_total for o in upi_orders)
    total_pending = total_cash_pending + total_upi_pending
    
    generated_at = timezone.localtime()
    
    context = {
        'cash_orders': cash_orders,
        'upi_orders': upi_orders,
        'start_date': start_date,
        'end_date': end_date,
        'total_cash_advance': total_cash_advance,
        'total_upi_advance': total_upi_advance,
        'total_advance': total_advance,
        'total_cash_pending': total_cash_pending,
        'total_upi_pending': total_upi_pending,
        'total_pending': total_pending,
        'cash_count': cash_orders.count(),
        'upi_count': upi_orders.count(),
        'generated_at': generated_at,
    }
    return render(request, 'orders/payment_report_print.html', context)

def public_order_invoice(request, token):
    order = get_object_or_404(Order, access_token=token)
    items = order.items.all()
    
    FurnitureDimensions = []
    from measurements.models import get_all_furniture_parameters, get_all_furniture_types
    all_params = get_all_furniture_parameters()
    all_cats = dict(get_all_furniture_types())

    for item in items:
        m = item.dimension
        if m:
            params = all_params.get(m.furniture_type, [])
            ordered_values = []
            for p in params:
                ordered_values.append({'label': p, 'value': m.values.get(p, '-')})
            
            FurnitureDimensions.append({
                'category_display': all_cats.get(m.furniture_type, m.furniture_type.title()),
                'data': ordered_values,
                'notes': m.notes,
                'is_standard_catalog': m.is_standard_catalog
            })
                
    amount_in_words = num2words(order.final_amount)
    
    context = {
        'order': order,
        'items': items,
        'FurnitureDimensions': FurnitureDimensions,
        'amount_in_words': amount_in_words,
    }
    return render(request, 'orders/public_invoice.html', context)

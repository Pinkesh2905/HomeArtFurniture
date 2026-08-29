"""
One-time management command to fix existing orders where multiple OrderItems
share the same FurnitureDimension record. Each item should have its own distinct
FurnitureDimension so that editing one doesn't affect the other.
"""
from django.core.management.base import BaseCommand
from django.db.models import Count
from orders.models import OrderItem
from measurements.models import FurnitureDimension


class Command(BaseCommand):
    help = 'Fix orders where multiple items share the same FurnitureDimension record by cloning.'

    def handle(self, *args, **options):
        # Find all FurnitureDimension IDs that are referenced by more than one OrderItem
        shared = (
            OrderItem.objects
            .filter(dimension__isnull=False)
            .values('dimension_id')
            .annotate(cnt=Count('id'))
            .filter(cnt__gt=1)
        )

        total_cloned = 0
        for entry in shared:
            d_id = entry['dimension_id']
            items = list(OrderItem.objects.filter(dimension_id=d_id).select_related('dimension'))
            if len(items) <= 1:
                continue

            original = items[0].dimension
            self.stdout.write(f"FurnitureDimension #{d_id} ({original.furniture_type}) shared by {len(items)} items")

            # Keep the first item linked to the original, clone for the rest
            for item in items[1:]:
                clone = FurnitureDimension.objects.create(
                    customer=original.customer,
                    furniture_type=original.furniture_type,
                    values=dict(original.values) if original.values else {},
                    notes=original.notes,
                    is_standard_catalog=original.is_standard_catalog,
                )
                item.dimension = clone
                item.save(update_fields=['dimension'])
                total_cloned += 1
                self.stdout.write(
                    f"  -> Cloned FurnitureDimension #{d_id} -> #{clone.id} for OrderItem #{item.id} "
                    f"(Order #{item.order.order_number})"
                )

        if total_cloned == 0:
            self.stdout.write(self.style.SUCCESS("No shared dimensions found. All orders are clean."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Done. Cloned {total_cloned} dimension(s)."))

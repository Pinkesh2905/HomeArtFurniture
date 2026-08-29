from django.db import models
import copy
from customers.models import Customer

class FurnitureType(models.TextChoices):
    SOFA = 'sofa', 'Sofa'
    DINING_TABLE = 'dining_table', 'Dining Table'
    BED = 'bed', 'Bed'
    WARDROBE = 'wardrobe', 'Wardrobe'
    CHAIR = 'chair', 'Chair'
    DESK = 'desk', 'Desk'
    CABINET = 'cabinet', 'Cabinet'
    CONSOLE = 'console', 'Console'
    OTHER = 'other', 'Other'

FURNITURE_PARAMETERS = {
    'sofa': ['Width', 'Length', 'Height'],
    'dining_table': ['Width', 'Length', 'Height'],
    'bed': ['Width', 'Length', 'Height'],
    'wardrobe': ['Width', 'Length', 'Height'],
    'chair': ['Width', 'Length', 'Height'],
    'desk': ['Width', 'Length', 'Height'],
    'cabinet': ['Width', 'Length', 'Height'],
    'console': ['Width', 'Length', 'Height'],
    'other': ['Width', 'Length', 'Height'],
}

class CustomFurnitureType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class CustomFurnitureParameter(models.Model):
    category_name = models.CharField(max_length=50)
    name = models.CharField(max_length=50)

    class Meta:
        unique_together = ('category_name', 'name')

    def __str__(self):
        return f"{self.category_name} - {self.name}"

def get_all_furniture_types():
    base_choices = list(FurnitureType.choices)
    custom_categories = CustomFurnitureType.objects.all()
    for cat in custom_categories:
        slug = cat.name.lower().replace(' ', '_')
        base_choices.append((slug, cat.name))
    return base_choices

def get_all_furniture_parameters():
    params = copy.deepcopy(FURNITURE_PARAMETERS)
    for cp in CustomFurnitureParameter.objects.all():
        if cp.category_name not in params:
            params[cp.category_name] = []
        params[cp.category_name].append(cp.name)
    return params


class FurnitureDimension(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='measurements')
    furniture_type = models.CharField(max_length=50)
    values = models.JSONField(default=dict)
    notes = models.TextField(blank=True)
    is_standard_catalog = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        pass

    def __str__(self):
        cat_dict = dict(get_all_furniture_types())
        display = cat_dict.get(self.furniture_type, self.furniture_type.title())
        return f"{self.customer.full_name} - {display}"

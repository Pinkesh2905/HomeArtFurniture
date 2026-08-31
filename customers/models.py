# pyrefly: ignore [missing-import]
from django.db import models
from django.core.exceptions import ValidationError
from .utils import normalize_phone, validate_phone

class Customer(models.Model):
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=15, db_index=True)
    alt_phone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_archived = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self.phone:
            validate_phone(self.phone)
        if self.alt_phone:
            validate_phone(self.alt_phone)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        if update_fields is None or 'phone' in update_fields or 'alt_phone' in update_fields:
            self.phone = normalize_phone(self.phone)
            self.alt_phone = normalize_phone(self.alt_phone) if self.alt_phone else ''
            if self.city:
                self.city = self.city.strip().title()
            self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.phone})"

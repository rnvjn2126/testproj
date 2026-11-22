from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class OwnedRecord(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Customer(OwnedRecord):
    name = models.CharField(max_length=160)
    company_name = models.CharField(max_length=160, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    billing_address = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [models.UniqueConstraint(fields=["owner", "name"], name="unique_customer_name_per_owner")]

    def __str__(self):
        return self.name


class Supplier(OwnedRecord):
    name = models.CharField(max_length=160)
    company_name = models.CharField(max_length=160, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [models.UniqueConstraint(fields=["owner", "name"], name="unique_supplier_name_per_owner")]

    def __str__(self):
        return self.name


class Product(OwnedRecord):
    class Shape(models.TextChoices):
        ROUND_BAR = "round_bar", "Round bar"
        SHEET = "sheet", "Sheet"
        PLATE = "plate", "Plate"
        PIPE = "pipe", "Pipe"
        ANGLE = "angle", "Angle"
        CHANNEL = "channel", "Channel"
        OTHER = "other", "Other"

    class Unit(models.TextChoices):
        KG = "kg", "Kilogram (kg)"
        TONNE = "tonne", "Metric tonne"
        PIECE = "piece", "Piece"
        METRE = "m", "Metre (m)"

    class WeightBasis(models.TextChoices):
        NOT_APPLICABLE = "na", "Not applicable / not recorded"
        ACTUAL = "actual", "Actual weight"
        THEORETICAL = "theoretical", "Theoretical weight"

    name = models.CharField(max_length=160)
    grade = models.CharField(max_length=100, blank=True)
    shape = models.CharField(max_length=20, choices=Shape.choices)
    dimensions = models.CharField(max_length=160, blank=True, help_text="Metric dimensions, e.g. 25 mm diameter or 2 x 1 m x 3 mm")
    unit = models.CharField(max_length=12, choices=Unit.choices)
    weight_basis = models.CharField(max_length=16, choices=WeightBasis.choices, default=WeightBasis.NOT_APPLICABLE)
    weight_kg = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(0.001)], help_text="Optional item weight in kg; use actual or theoretical as the recorded basis.")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [models.UniqueConstraint(fields=["owner", "name"], name="unique_product_name_per_owner")]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.weight_kg is not None and self.weight_basis == self.WeightBasis.NOT_APPLICABLE:
            raise ValidationError({"weight_basis": "Choose actual or theoretical when recording an item weight."})

    def __str__(self):
        return self.name

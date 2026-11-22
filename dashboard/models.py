from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def _decimal(value):
    """Normalize persisted or in-memory numeric values before domain math."""
    return value if isinstance(value, Decimal) else Decimal(str(value))


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


class RFQ(OwnedRecord):
    class Source(models.TextChoices):
        PHONE = "phone", "Phone"
        WHATSAPP = "whatsapp", "WhatsApp"
        EMAIL = "email", "Email"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        NEW = "new", "New"
        IN_PROGRESS = "in_progress", "In progress"
        CLOSED = "closed", "Closed"

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="rfqs")
    reference = models.CharField(max_length=80, blank=True)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.OTHER)
    received_on = models.DateField()
    required_by = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW)

    class Meta:
        ordering = ["-received_on", "-id"]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.customer_id and self.owner_id and self.customer.owner_id != self.owner_id:
            raise ValidationError({"customer": "Choose a customer owned by your account."})

    def __str__(self):
        return self.reference or f"RFQ {self.pk}"


class RFQLine(OwnedRecord):
    rfq = models.ForeignKey(RFQ, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, null=True, blank=True, related_name="rfq_lines")
    description = models.CharField(max_length=160, blank=True)
    grade = models.CharField(max_length=100, blank=True)
    dimensions = models.CharField(max_length=160, blank=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=3, validators=[MinValueValidator(0.001)])
    unit = models.CharField(max_length=12, choices=Product.Unit.choices)

    class Meta:
        ordering = ["id"]

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.product and not (self.description or self.grade or self.dimensions):
            raise ValidationError("Enter a product or provide a description, grade, or dimensions.")
        if self.product and self.owner_id and self.product.owner_id != self.owner_id:
            raise ValidationError({"product": "Choose a product owned by your account."})
        if self.rfq and self.owner_id and self.rfq.owner_id != self.owner_id:
            raise ValidationError({"rfq": "The enquiry must belong to your account."})


class SupplierOffer(OwnedRecord):
    """A supplier's price and availability for one requested enquiry line."""

    rfq_line = models.ForeignKey(RFQLine, on_delete=models.CASCADE, related_name="supplier_offers")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="offers")
    available_quantity = models.DecimalField(
        max_digits=14, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))],
    )
    unit = models.CharField(max_length=12, choices=Product.Unit.choices)
    unit_price = models.DecimalField(
        max_digits=14, decimal_places=4, validators=[MinValueValidator(Decimal("0.0001"))],
        help_text="Supplier price for one unit selected below.",
    )
    freight_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    packaging_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Other packaging or incidental procurement cost for this offer.",
    )
    delivery_days = models.PositiveSmallIntegerField(validators=[MinValueValidator(0)])
    conversion_weight_kg = models.DecimalField(max_digits=12, decimal_places=3, blank=True, null=True, editable=False)
    conversion_weight_basis = models.CharField(
        max_length=16, choices=Product.WeightBasis.choices, blank=True, editable=False,
    )

    class Meta:
        ordering = ["id"]

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}
        line = self.rfq_line if self.rfq_line_id else None
        if line:
            if line.owner_id != line.rfq.owner_id or (self.owner_id and line.owner_id != self.owner_id):
                errors["rfq_line"] = "The enquiry item must belong to your account."
            if self.supplier_id and self.supplier.owner_id != line.owner_id:
                errors["supplier"] = "Choose a supplier owned by your account."
            product = line.product if line.product_id else None
            if (
                self.unit != line.unit
                and Product.Unit.PIECE in (self.unit, line.unit)
                and self.conversion_weight_kg is None
                and product
                and product.weight_kg is not None
            ):
                self.conversion_weight_kg = product.weight_kg
                self.conversion_weight_basis = product.weight_basis
            if self.unit and self.unit_conversion_factor is None:
                errors["unit"] = "This offer unit cannot be converted to the enquiry item's unit."
        if errors:
            raise ValidationError(errors)

    @property
    def unit_conversion_factor(self):
        """Number of enquiry units represented by one offered unit, if known."""
        line = self.rfq_line if self.rfq_line_id else None
        if not line:
            return None
        if self.unit == line.unit:
            return Decimal("1")

        # Weight conversions are explicit. Piece conversions are only possible when
        # the linked catalogue product has a recorded actual or theoretical weight.
        product = line.product if line.product_id else None
        piece_weight_kg = self.conversion_weight_kg
        if piece_weight_kg is None and product:
            piece_weight_kg = product.weight_kg

        def kilograms_per_unit(unit):
            if unit == Product.Unit.KG:
                return Decimal("1")
            if unit == Product.Unit.TONNE:
                return Decimal("1000")
            if unit == Product.Unit.PIECE and piece_weight_kg is not None:
                return _decimal(piece_weight_kg)
            return None

        offer_kg = kilograms_per_unit(self.unit)
        requested_kg = kilograms_per_unit(line.unit)
        if offer_kg is None or requested_kg is None or requested_kg == 0:
            return None
        return offer_kg / requested_kg

    @property
    def converted_available_quantity(self):
        factor = self.unit_conversion_factor
        if factor is None:
            return None
        return _decimal(self.available_quantity) * factor

    @property
    def covered_quantity(self):
        """Enquiry quantity this offer can cover, expressed in the enquiry unit."""
        available = self.converted_available_quantity
        if available is None or not self.rfq_line_id:
            return None
        return min(available, _decimal(self.rfq_line.quantity))

    @property
    def covers_full_quantity(self):
        return self.covered_quantity is not None and self.covered_quantity >= _decimal(self.rfq_line.quantity)

    @property
    def normalized_unit_price(self):
        factor = self.unit_conversion_factor
        if factor is None or factor == 0:
            return None
        return _decimal(self.unit_price) / factor

    @property
    def landed_cost_per_requested_unit(self):
        """Price normalized to the RFQ unit plus freight/incidental cost per covered unit."""
        covered = self.covered_quantity
        base_price = self.normalized_unit_price
        if covered is None or covered <= 0 or base_price is None:
            return None
        allocated_costs = _decimal(self.freight_cost) + _decimal(self.packaging_cost)
        return base_price + allocated_costs / covered

    @property
    def total_landed_cost(self):
        covered = self.covered_quantity
        unit_cost = self.landed_cost_per_requested_unit
        if covered is None or unit_cost is None:
            return None
        return covered * unit_cost

    @property
    def conversion_assumption(self):
        line = self.rfq_line if self.rfq_line_id else None
        factor = self.unit_conversion_factor
        if line is None or factor is None:
            return "Unit conversion unavailable."
        offered_display = self.get_unit_display()
        requested_display = line.get_unit_display()
        if self.unit == line.unit:
            return f"No unit conversion; both rates are per {requested_display.lower()}."
        if Product.Unit.PIECE in (self.unit, line.unit):
            product = line.product if line.product_id else None
            weight = self.conversion_weight_kg
            weight_basis = self.conversion_weight_basis
            if weight is None and product:
                weight = product.weight_kg
                weight_basis = product.weight_basis
            if weight is not None:
                basis_label = dict(Product.WeightBasis.choices).get(weight_basis, "recorded").lower()
                return (
                    f"Piece conversion uses the recorded {basis_label} "
                    f"of {_decimal(weight)} kg per piece."
                )
        return f"Converted {offered_display.lower()} to {requested_display.lower()} using the metric weight ratio."


class QuotePricingSettings(OwnedRecord):
    """Account-owned pricing guardrails used as defaults for new quotations."""

    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    target_margin_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("12.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("99.99"))],
        help_text="Target gross margin. This is margin on the selling price, not markup on cost.",
    )
    minimum_margin_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("8.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("99.99"))],
        help_text="Quotes below this gross margin require explicit staff review.",
    )
    maximum_discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("5.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("99.99"))],
        help_text="Largest discount allowed from the target-margin selling price.",
    )

    class Meta:
        verbose_name = "quote pricing settings"
        verbose_name_plural = "quote pricing settings"

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}
        if self.target_margin_percent is not None and self.target_margin_percent >= 100:
            errors["target_margin_percent"] = "Target gross margin must be less than 100%."
        if self.minimum_margin_percent is not None and self.minimum_margin_percent >= 100:
            errors["minimum_margin_percent"] = "Minimum gross margin must be less than 100%."
        if self.maximum_discount_percent is not None and self.maximum_discount_percent >= 100:
            errors["maximum_discount_percent"] = "Maximum discount must be less than 100%."
        if errors:
            raise ValidationError(errors)


class Quote(OwnedRecord):
    class Status(models.TextChoices):
        READY = "ready", "Ready"
        NEEDS_REVIEW = "needs_review", "Needs manager review"
        APPROVED = "approved", "Approved after review"

    rfq = models.ForeignKey(RFQ, on_delete=models.PROTECT, related_name="quotes")
    target_margin_percent = models.DecimalField(max_digits=5, decimal_places=2)
    minimum_margin_percent = models.DecimalField(max_digits=5, decimal_places=2)
    maximum_discount_percent = models.DecimalField(max_digits=5, decimal_places=2)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.READY)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="approved_steel_quotes",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}
        if self.rfq_id and self.owner_id and self.rfq.owner_id != self.owner_id:
            errors["rfq"] = "Choose an enquiry owned by your account."
        elif self.rfq_id and self.owner_id and self.rfq.customer.owner_id != self.owner_id:
            errors["rfq"] = "The enquiry's customer must belong to your account."
        for field in ("target_margin_percent", "minimum_margin_percent", "maximum_discount_percent"):
            value = getattr(self, field)
            if value is not None and (value < 0 or value >= 100):
                errors[field] = "Enter a percentage from 0 up to (but not including) 100."
        if self.approved_by_id and self.owner_id and self.approved_by_id != self.owner_id:
            errors["approved_by"] = "The reviewer must belong to this account."
        if self.status == self.Status.APPROVED and (not self.approved_by_id or not self.approved_at):
            errors["status"] = "A reviewed quotation must record its reviewer and review time."
        if errors:
            raise ValidationError(errors)

    @property
    def needs_review(self):
        return self.status == self.Status.NEEDS_REVIEW

    @property
    def total_landed_cost(self):
        return sum((line.total_landed_cost for line in self.lines.all()), Decimal("0.00"))

    @property
    def total_selling_price(self):
        return sum((line.total_selling_price for line in self.lines.all()), Decimal("0.00"))

    @property
    def gross_margin_percent(self):
        selling_price = self.total_selling_price
        if selling_price <= 0:
            return None
        return ((selling_price - self.total_landed_cost) / selling_price * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP,
        )


class QuoteLine(OwnedRecord):
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="lines")
    rfq_line = models.ForeignKey(RFQLine, on_delete=models.PROTECT, related_name="quote_lines")
    supplier_offer = models.ForeignKey(SupplierOffer, on_delete=models.PROTECT, related_name="quote_lines")
    quantity = models.DecimalField(max_digits=14, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    unit = models.CharField(max_length=12, choices=Product.Unit.choices)
    landed_cost_per_unit = models.DecimalField(max_digits=14, decimal_places=4, validators=[MinValueValidator(Decimal("0.0001"))])
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    selling_price_per_unit = models.DecimalField(max_digits=14, decimal_places=4, validators=[MinValueValidator(Decimal("0.0001"))])

    class Meta:
        ordering = ["id"]

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}
        if self.quote_id and self.owner_id and self.quote.owner_id != self.owner_id:
            errors["quote"] = "The quotation must belong to your account."
        if self.rfq_line_id and self.quote_id:
            if self.rfq_line.owner_id != self.owner_id or self.rfq_line.rfq_id != self.quote.rfq_id:
                errors["rfq_line"] = "Choose an item from this quotation's enquiry."
            if self.rfq_line.product_id and self.rfq_line.product.owner_id != self.owner_id:
                errors["rfq_line"] = "The enquiry item's product must belong to your account."
            if self.unit != self.rfq_line.unit or self.quantity != self.rfq_line.quantity:
                errors["quantity"] = "The quoted quantity and unit must match the enquiry item."
        if self.supplier_offer_id and self.rfq_line_id:
            if self.supplier_offer.owner_id != self.owner_id or self.supplier_offer.rfq_line_id != self.rfq_line_id:
                errors["supplier_offer"] = "Choose an offer for this enquiry item from your account."
            elif self.supplier_offer.supplier.owner_id != self.owner_id:
                errors["supplier_offer"] = "The offer's supplier must belong to your account."
            elif not self.supplier_offer.covers_full_quantity:
                errors["supplier_offer"] = "The selected offer must cover the full quoted quantity."
        if self.quote_id and self.discount_percent is not None and self.discount_percent > self.quote.maximum_discount_percent:
            errors["discount_percent"] = "The discount exceeds this quotation's saved guardrail."
        if errors:
            raise ValidationError(errors)

    @property
    def total_landed_cost(self):
        return (self.quantity * self.landed_cost_per_unit).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def total_selling_price(self):
        return (self.quantity * self.selling_price_per_unit).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def target_price_per_unit(self):
        target_margin = self.quote.target_margin_percent / Decimal("100")
        return (self.landed_cost_per_unit / (Decimal("1") - target_margin)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP,
        )

    @property
    def gross_margin_percent(self):
        selling_price = self.selling_price_per_unit
        if selling_price <= 0:
            return None
        return ((selling_price - self.landed_cost_per_unit) / selling_price * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP,
        )

    @property
    def needs_review(self):
        margin = self.gross_margin_percent
        return margin is None or margin < self.quote.minimum_margin_percent


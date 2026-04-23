from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.exceptions import ValidationError
from datetime import date

import qrcode
from io import BytesIO
import base64

User = get_user_model()


# ======================
# CATEGORY
# ======================
class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


# ======================
# LOCATION
# ======================
class Location(models.Model):
    name = models.CharField(max_length=120, unique=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


# ======================
# ASSET
# ======================
class Asset(models.Model):

    STATUS_CHOICES = [
        ("IN_STOCK", "In Stock"),
        ("ASSIGNED", "Assigned"),
        ("MAINTENANCE", "Under Maintenance"),
        ("DISPOSED", "Disposed"),
    ]

    tag = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=200)

    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)

    purchase_date = models.DateField(null=True, blank=True)
    value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="IN_STOCK")
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    # ----------------------
    # VALIDATION
    # ----------------------
    def clean(self):
        if self.value and self.value < 0:
            raise ValidationError("Asset value cannot be negative.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    # ----------------------
    # QR CODE
    # ----------------------
    def qr_code_base64(self):
        url = reverse("inventory:asset_detail", args=[self.pk])

        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = BytesIO()
        img.save(buffer, format="PNG")

        img_str = base64.b64encode(buffer.getvalue()).decode()

        return f"data:image/png;base64,{img_str}"

    def __str__(self):
        return f"{self.tag} - {self.name}"

    class Meta:
        ordering = ["-created_at"]


# ======================
# ASSET ASSIGNMENT
# ======================
class AssetAssignment(models.Model):

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="assignments")
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    department = models.CharField(max_length=120, blank=True)

    assigned_on = models.DateField(auto_now_add=True)
    returned_on = models.DateField(null=True, blank=True)

    note = models.TextField(blank=True)

    # ----------------------
    # VALIDATION
    # ----------------------
    def clean(self):

        # prevent double active assignment
        active = AssetAssignment.objects.filter(
            asset=self.asset,
            returned_on__isnull=True
        ).exclude(pk=self.pk).first()

        if active:
            raise ValidationError("This asset is already assigned and not returned.")

        # date validation
        if self.returned_on and self.returned_on < self.assigned_on:
            raise ValidationError("Return date cannot be before assignment date.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.asset.tag} -> {self.assigned_to or self.department}"

    class Meta:
        ordering = ["-assigned_on"]


# ======================
# STOCK ITEM
# ======================
class StockItem(models.Model):

    sku = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=200)

    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)

    quantity = models.IntegerField(default=0)
    unit = models.CharField(max_length=30, default="pcs")
    reorder_level = models.IntegerField(default=5)

    def __str__(self):
        return f"{self.sku} - {self.name}"

    class Meta:
        ordering = ["name"]


# ======================
# STOCK MOVEMENT
# ======================
class StockMovement(models.Model):

    stock_item = models.ForeignKey(StockItem, on_delete=models.CASCADE, related_name="movements")

    movement_type = models.CharField(max_length=3, choices=[("IN", "IN"), ("OUT", "OUT")])

    qty = models.IntegerField()
    note = models.TextField(blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    done_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    # ----------------------
    # VALIDATION
    # ----------------------
    def clean(self):

        if self.qty <= 0:
            raise ValidationError("Quantity must be greater than zero.")

        if self.movement_type == "OUT":
            if self.stock_item and self.qty > self.stock_item.quantity:
                raise ValidationError(
                    f"Cannot remove {self.qty}. Only {self.stock_item.quantity} available."
                )

    # ----------------------
    # SAFE STOCK UPDATE
    # ----------------------
    def save(self, *args, **kwargs):

        self.full_clean()

        if not self.pk:
            if self.movement_type == "IN":
                self.stock_item.quantity += self.qty
            elif self.movement_type == "OUT":
                self.stock_item.quantity -= self.qty

            self.stock_item.save()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.stock_item.sku} {self.movement_type} {self.qty}"

    class Meta:
        ordering = ["-timestamp"]


# ======================
# MAINTENANCE
# ======================
class MaintenanceRecord(models.Model):

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="maintenance")

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    performed_by = models.CharField(max_length=200, blank=True)
    performed_on = models.DateField()

    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # ----------------------
    # VALIDATION
    # ----------------------
    def clean(self):
        if self.cost < 0:
            raise ValidationError("Cost cannot be negative.")

        if self.performed_on > date.today():
            raise ValidationError("Maintenance date cannot be in the future.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.asset.tag} - {self.title}"

    class Meta:
        ordering = ["-performed_on"]


# ======================
# AUDIT LOG (UNCHANGED BUT SAFE)
# ======================
class AuditLog(models.Model):

    ACTION_CHOICES = [
        ("CREATE", "Create"),
        ("UPDATE", "Update"),
        ("DELETE", "Delete"),
        ("LOGIN", "Login"),
        ("LOGOUT", "Logout"),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.timestamp} - {self.user} - {self.action}"


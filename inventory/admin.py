from django.contrib import admin
from .models import (
    Category, Location, Asset, AssetAssignment,
    StockItem, StockMovement, MaintenanceRecord, AuditLog
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("tag", "name", "category", "location", "status", "created_at")
    search_fields = ("tag", "name")
    list_filter = ("status", "category", "location")
    ordering = ("-created_at",)


@admin.register(AssetAssignment)
class AssetAssignmentAdmin(admin.ModelAdmin):
    list_display = ("asset", "assigned_to", "department", "assigned_on", "returned_on")
    search_fields = ("asset__tag", "assigned_to__username", "department")
    list_filter = ("assigned_on", "returned_on")


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "quantity", "unit", "reorder_level")
    search_fields = ("sku", "name")
    list_filter = ("category",)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("stock_item", "movement_type", "qty", "done_by", "timestamp")
    search_fields = ("stock_item__sku",)
    list_filter = ("movement_type", "timestamp")


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):
    list_display = ("asset", "title", "performed_by", "performed_on", "cost")
    search_fields = ("asset__tag", "title")
    list_filter = ("performed_on",)


# ======================
# AUDIT LOG (READ-ONLY)
# ======================
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "user", "action", "model_name", "object_id")
    list_filter = ("action", "model_name", "timestamp")
    search_fields = ("object_id", "description", "user__username")

    readonly_fields = (
        "timestamp",
        "user",
        "action",
        "model_name",
        "object_id",
        "description",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

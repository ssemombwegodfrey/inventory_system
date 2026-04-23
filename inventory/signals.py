from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

from .models import Asset, StockMovement, MaintenanceRecord, AuditLog
from .middleware import get_current_user


# ===================== HELPER =====================

def log_action(instance, action, description=""):
    AuditLog.objects.create(
        user=get_current_user(),
        action=action,
        model_name=instance.__class__.__name__,
        object_id=instance.pk,
        description=description
    )


# ===================== ASSET =====================

@receiver(pre_save, sender=Asset)
def asset_pre_save(sender, instance, **kwargs):
    """Capture old values before update"""
    if instance.pk:
        try:
            old = Asset.objects.get(pk=instance.pk)
            instance._old_values = {
                "name": old.name,
                "status": old.status,
                "location": old.location_id,
            }
        except Asset.DoesNotExist:
            instance._old_values = {}
    else:
        instance._old_values = {}


@receiver(post_save, sender=Asset)
def asset_saved(sender, instance, created, **kwargs):
    if created:
        log_action(
            instance,
            "CREATE",
            f"Created Asset: {instance.name} (Tag: {instance.tag})"
        )
    else:
        changes = []

        old = getattr(instance, "_old_values", {})

        if old.get("name") != instance.name:
            changes.append(f"name: '{old.get('name')}' → '{instance.name}'")

        if old.get("status") != instance.status:
            changes.append(f"status: {old.get('status')} → {instance.status}")

        if old.get("location") != (instance.location.id if instance.location else None):
            changes.append("location changed")

        description = ", ".join(changes) if changes else "Updated asset"

        log_action(instance, "UPDATE", description)


@receiver(post_delete, sender=Asset)
def asset_deleted(sender, instance, **kwargs):
    log_action(
        instance,
        "DELETE",
        f"Deleted Asset: {instance.name} (Tag: {instance.tag})"
    )


# ===================== STOCK MOVEMENT =====================

@receiver(post_save, sender=StockMovement)
def stock_moved(sender, instance, created, **kwargs):
    if created:
        log_action(
            instance,
            "CREATE",
            f"{instance.movement_type} {instance.qty} units of {instance.stock_item.name}"
        )


# ===================== MAINTENANCE =====================

@receiver(post_save, sender=MaintenanceRecord)
def maintenance_logged(sender, instance, created, **kwargs):
    if created:
        log_action(
            instance,
            "CREATE",
            f"Maintenance '{instance.title}' for {instance.asset.name} cost {instance.cost}"
        )
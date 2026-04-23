from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from inventory.models import Asset, StockItem, MaintenanceRecord


class Command(BaseCommand):
    help = "Create user roles and assign permissions"

    def handle(self, *args, **kwargs):
        # Create groups
        admin_group, _ = Group.objects.get_or_create(name="Admin")
        staff_group, _ = Group.objects.get_or_create(name="Staff")
        viewer_group, _ = Group.objects.get_or_create(name="Viewer")

        # Content types
        asset_ct = ContentType.objects.get_for_model(Asset)
        stock_ct = ContentType.objects.get_for_model(StockItem)
        maintenance_ct = ContentType.objects.get_for_model(MaintenanceRecord)

        # Permissions for Admin (full access)
        admin_perms = Permission.objects.filter(content_type__in=[asset_ct, stock_ct, maintenance_ct])
        admin_group.permissions.set(admin_perms)

        # Permissions for Staff (create/edit but not delete)
        staff_perms = Permission.objects.filter(
            content_type__in=[asset_ct, stock_ct, maintenance_ct],
            codename__in=[
                "add_asset", "change_asset", "view_asset",
                "add_stockitem", "change_stockitem", "view_stockitem",
                "add_stockmovement", "change_stockmovement", "view_stockmovement",
                "add_maintenancerecord", "change_maintenancerecord", "view_maintenancerecord",
                "assign_asset", "adjust_stock", "view_maintenance_costs",
            ]
        )
        staff_group.permissions.set(staff_perms)

        # Permissions for Viewer (read-only)
        viewer_perms = Permission.objects.filter(
            content_type__in=[asset_ct, stock_ct, maintenance_ct],
            codename__in=[
                "view_asset",
                "view_stockitem",
                "view_stockmovement",
                "view_maintenancerecord",
                "view_dashboard",
                "view_maintenance_costs",
            ]
        )
        viewer_group.permissions.set(viewer_perms)

        self.stdout.write(self.style.SUCCESS("Roles & permissions created successfully."))

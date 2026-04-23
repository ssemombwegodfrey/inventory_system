from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.db.models import F, Sum, Q
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages
from django.db import transaction
from .models import AuditLog

from openpyxl import Workbook
from openpyxl.styles import Font
import csv

from .models import (
    Asset, StockItem, StockMovement,
    MaintenanceRecord, Category, AssetAssignment
)
from .forms import AssetForm, StockMovementForm, MaintenanceForm

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .serializers import AssetSerializer, StockItemSerializer, StockMovementSerializer



# ======================
# DASHBOARD
# ======================
@login_required
def dashboard(request):
    total_assets = Asset.objects.count()
    assigned = Asset.objects.filter(status="ASSIGNED").count()
    in_stock = Asset.objects.filter(status="IN_STOCK").count()
    maintenance = Asset.objects.filter(status="MAINTENANCE").count()
    disposed = Asset.objects.filter(status="DISPOSED").count()

    low_stock = StockItem.objects.filter(quantity__lte=F("reorder_level"))

    recent_movements = (
        StockMovement.objects
        .select_related("stock_item", "done_by")
        .order_by("-timestamp")[:5]
    )

    asset_status_chart = {
        "labels": ["In Stock", "Assigned", "Maintenance", "Disposed"],
        "data": [in_stock, assigned, maintenance, disposed],
    }

    months, costs = [], []
    today = timezone.now().date()

    for i in range(5, -1, -1):
        month_date = today - timedelta(days=30 * i)
        months.append(month_date.strftime("%b %Y"))

        cost = (
            MaintenanceRecord.objects.filter(
                performed_on__month=month_date.month,
                performed_on__year=month_date.year
            ).aggregate(total=Sum("cost"))["total"] or 0
        )

        costs.append(float(cost))

    maintenance_cost_chart = {
        "labels": months,
        "data": costs,
    }

    stock_items = StockItem.objects.order_by("name")

    stock_chart = {
        "labels": [i.name for i in stock_items],
        "data": [i.quantity for i in stock_items],
    }

    return render(request, "inventory/dashboard.html", {
        "total_assets": total_assets,
        "assigned": assigned,
        "in_stock": in_stock,
        "maintenance": maintenance,
        "disposed": disposed,
        "low_stock": low_stock,
        "recent_movements": recent_movements,
        "asset_status_chart": asset_status_chart,
        "maintenance_cost_chart": maintenance_cost_chart,
        "stock_chart": stock_chart,
    })


# ======================
# ASSETS
# ======================
@login_required
@permission_required("inventory.view_asset", raise_exception=True)
def asset_list(request):

    assets = Asset.objects.select_related("category", "location")

    query = request.GET.get("q")
    if query:
        assets = assets.filter(
            Q(name__icontains=query) |
            Q(tag__icontains=query) |
            Q(category__name__icontains=query)
        )

    category_id = request.GET.get("category")
    status = request.GET.get("status")

    if category_id:
        assets = assets.filter(category_id=category_id)

    if status:
        assets = assets.filter(status=status)

    assets = assets.order_by("-created_at")

    paginator = Paginator(assets, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    categories = Category.objects.all()

    return render(request, "inventory/asset_list.html", {
        "page_obj": page_obj,
        "categories": categories,
        "query": query,
        "selected_category": category_id,
        "selected_status": status,
    })


@login_required
@permission_required("inventory.add_asset", raise_exception=True)
def asset_add(request):
    form = AssetForm(request.POST or None)

    if form.is_valid():
        asset = form.save(commit=False)

        # Prevent duplicate tag (extra safety)
        if Asset.objects.filter(tag=asset.tag).exists():
            form.add_error("tag", "Asset tag already exists.")
            return render(request, "inventory/asset_form.html", {"form": form})

        asset.save()
        messages.success(request, "Asset created successfully.")

        return redirect("inventory:asset_list")

    return render(request, "inventory/asset_form.html", {"form": form})


@login_required
@permission_required("inventory.change_asset", raise_exception=True)
def asset_edit(request, pk):
    asset = get_object_or_404(Asset, pk=pk)
    form = AssetForm(request.POST or None, instance=asset)

    if form.is_valid():
        form.save()
        messages.success(request, "Asset updated successfully.")
        return redirect("inventory:asset_list")

    return render(request, "inventory/asset_form.html", {
        "form": form,
        "asset": asset
    })


@login_required
@permission_required("inventory.delete_asset", raise_exception=True)
def asset_delete(request, pk):
    asset = get_object_or_404(Asset, pk=pk)

    if request.method == "POST":
        asset.delete()
        messages.success(request, "Asset deleted successfully.")
        return redirect("inventory:asset_list")

    return render(request, "inventory/asset_confirm_delete.html", {
        "asset": asset
    })


# ======================
# ASSET DETAIL
# ======================
@login_required
@permission_required("inventory.view_asset", raise_exception=True)
def asset_detail(request, pk):
    asset = get_object_or_404(
        Asset.objects.select_related("category", "location"),
        pk=pk
    )

    assignments = AssetAssignment.objects.filter(
        asset=asset
    ).order_by("-assigned_on")

    maintenance_records = MaintenanceRecord.objects.filter(
        asset=asset
    ).order_by("-performed_on")

    return render(request, "inventory/asset_detail.html", {
        "asset": asset,
        "assignments": assignments,
        "maintenance_records": maintenance_records
    })


# ======================
# STOCK
# ======================
@login_required
@permission_required("inventory.view_stockitem", raise_exception=True)
def stock_list(request):
    items = StockItem.objects.order_by("name")
    paginator = Paginator(items, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "inventory/stock_list.html", {
        "page_obj": page_obj
    })


@login_required
@permission_required("inventory.add_stockmovement", raise_exception=True)
def stock_move(request):
    form = StockMovementForm(request.POST or None)

    if form.is_valid():
        movement = form.save(commit=False)
        movement.done_by = request.user
        item = movement.stock_item

        # Validation
        if movement.qty <= 0:
            messages.error(request, "Quantity must be greater than zero.")
            return render(request, "inventory/stock_move.html", {"form": form})

        if movement.movement_type == "OUT" and item.quantity < movement.qty:
            messages.error(request, "Insufficient stock for this operation.")
            return render(request, "inventory/stock_move.html", {"form": form})

        # Atomic update
        with transaction.atomic():
            movement.save()

            if movement.movement_type == "IN":
                item.quantity = F("quantity") + movement.qty
            else:
                item.quantity = F("quantity") - movement.qty

            item.save()
            item.refresh_from_db()

        messages.success(request, "Stock movement recorded successfully.")
        return redirect("inventory:stock_list")

    return render(request, "inventory/stock_move.html", {"form": form})


# ======================
# REPORTS
# ======================
@login_required
@permission_required("inventory.view_asset", raise_exception=True)
def asset_register_report(request):
    assets = Asset.objects.select_related("category", "location").order_by("tag")

    return render(request, "inventory/reports/asset_register.html", {
        "assets": assets
    })


@login_required
@permission_required("inventory.view_stockitem", raise_exception=True)
def stock_summary_report(request):
    items = StockItem.objects.select_related("category").order_by("name")

    return render(request, "inventory/reports/stock_summary.html", {
        "items": items
    })


# ======================
# EXPORTS
# ======================
@login_required
@permission_required("inventory.view_asset", raise_exception=True)
def export_asset_register_csv(request):
    assets = Asset.objects.select_related("category", "location")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="asset_register.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "Tag", "Name", "Category",
        "Location", "Status",
        "Value", "Purchase Date"
    ])

    for a in assets:
        writer.writerow([
            a.tag,
            a.name,
            a.category.name if a.category else "",
            a.location.name if a.location else "",
            a.status,
            a.value,
            a.purchase_date
        ])

    return response


@login_required
@permission_required("inventory.view_stockitem", raise_exception=True)
def export_stock_summary_xlsx(request):
    wb = Workbook()
    ws = wb.active
    ws.title = "Stock Summary"

    headers = ["SKU", "Item", "Category", "Quantity", "Reorder Level", "Status"]
    ws.append(headers)

    for col in range(1, len(headers) + 1):
        ws.cell(row=1, column=col).font = Font(bold=True)

    for item in StockItem.objects.select_related("category"):
        status = "LOW STOCK" if item.quantity <= item.reorder_level else "OK"
        ws.append([
            item.sku,
            item.name,
            item.category.name if item.category else "",
            item.quantity,
            item.reorder_level,
            status,
        ])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="stock_summary.xlsx"'

    wb.save(response)
    return response


# ======================
# MAINTENANCE
# ======================
@login_required
@permission_required("inventory.view_maintenancerecord", raise_exception=True)
def maintenance_list(request):
    records = MaintenanceRecord.objects.select_related("asset").order_by("-performed_on")

    total_cost = records.aggregate(total=Sum("cost"))["total"] or 0

    cost_per_asset = (
        records.values("asset__tag", "asset__name")
        .annotate(total_cost=Sum("cost"))
        .order_by("-total_cost")
    )

    return render(request, "inventory/maintenance_list.html", {
        "records": records,
        "total_cost": total_cost,
        "cost_per_asset": cost_per_asset,
    })


# ======================
# AUDIT LOG
# ======================
@login_required
@permission_required("inventory.view_auditlog", raise_exception=True)
def audit_log_list(request):

    logs = AuditLog.objects.select_related("user").order_by("-timestamp")

    # 🔍 SEARCH
    query = request.GET.get("q")
    if query:
        logs = logs.filter(
            Q(model_name__icontains=query) |
            Q(description__icontains=query) |
            Q(user__username__icontains=query)
        )

    # 🎯 FILTER BY ACTION
    action = request.GET.get("action")
    if action:
        logs = logs.filter(action=action)

    paginator = Paginator(logs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "inventory/audit_log.html", {
        "page_obj": page_obj,
        "query": query,
        "selected_action": action,
    })

 # API VIEWS

class AssetViewSet(viewsets.ModelViewSet):
    queryset = Asset.objects.all()
    serializer_class = AssetSerializer
    permission_classes = [IsAuthenticated]


class StockItemViewSet(viewsets.ModelViewSet):
    queryset = StockItem.objects.all()
    serializer_class = StockItemSerializer
    permission_classes = [IsAuthenticated]


class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = StockMovement.objects.all()
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated]
    
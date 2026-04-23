from django.urls import path
from . import views

# DRF
from rest_framework.routers import DefaultRouter
from .views import AssetViewSet, StockItemViewSet, StockMovementViewSet

app_name = "inventory"

# ======================
# NORMAL URLS
# ======================
urlpatterns = [

    # DASHBOARD
    path("", views.dashboard, name="dashboard"),

    # ASSETS
    path("assets/", views.asset_list, name="asset_list"),
    path("assets/add/", views.asset_add, name="asset_add"),
    path("assets/<int:pk>/", views.asset_detail, name="asset_detail"),
    path("assets/<int:pk>/edit/", views.asset_edit, name="asset_edit"),
    path("assets/<int:pk>/delete/", views.asset_delete, name="asset_delete"),

    # STOCK
    path("stock/", views.stock_list, name="stock_list"),
    path("stock/move/", views.stock_move, name="stock_move"),

    # MAINTENANCE
    path("maintenance/", views.maintenance_list, name="maintenance_list"),

    # REPORTS
    path("reports/assets/", views.asset_register_report, name="asset_register_report"),
    path("reports/stock/", views.stock_summary_report, name="stock_summary_report"),

    # EXPORTS
    path("export/assets/csv/", views.export_asset_register_csv, name="export_assets_csv"),
    path("reports/assets/export/", views.export_asset_register_csv, name="export_asset_register_csv"),
    path("reports/stock/export/xlsx/", views.export_stock_summary_xlsx, name="export_stock_summary_xlsx"),

    # AUDIT
    path("audit-logs/", views.audit_log_list, name="audit_log"),
]

# ======================
# API ROUTES (DRF)
# ======================
router = DefaultRouter()
router.register(r"api/assets", AssetViewSet)
router.register(r"api/stock-items", StockItemViewSet)
router.register(r"api/movements", StockMovementViewSet)

urlpatterns += router.urls
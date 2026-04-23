from django import forms
from .models import Asset, StockItem, StockMovement, MaintenanceRecord, AssetAssignment

class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = "__all__"

class StockMovementForm(forms.ModelForm):
    class Meta:
        model = StockMovement
        fields = ["stock_item","movement_type","qty","note"]

class MaintenanceForm(forms.ModelForm):
    class Meta:
        model = MaintenanceRecord
        fields = ["asset","title","description","performed_by","performed_on","cost"]

class AssignForm(forms.ModelForm):
    class Meta:
        model = AssetAssignment
        fields = ["asset","assigned_to","department","note"]

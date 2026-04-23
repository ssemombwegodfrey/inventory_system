from rest_framework import serializers
from .models import Asset, StockItem, StockMovement


class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = "__all__"


class StockItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockItem
        fields = "__all__"


class StockMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockMovement
        fields = "__all__"
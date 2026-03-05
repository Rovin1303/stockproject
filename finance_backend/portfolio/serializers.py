from rest_framework import serializers
from .models import Portfolio, Stock

class StockSerializer(serializers.ModelSerializer):
    # when creating via API we only expect ticker and portfolio; other fields will be filled
    current_price = serializers.FloatField(read_only=True)
    pe_ratio = serializers.FloatField(read_only=True)
    high_52w = serializers.FloatField(read_only=True)
    low_52w = serializers.FloatField(read_only=True)
    price_history_30 = serializers.ListField(read_only=True)
    predicted_price = serializers.FloatField(read_only=True)
    predicted_for_date = serializers.DateField(read_only=True)
    company_name = serializers.CharField(read_only=True)

    discount = serializers.SerializerMethodField()

    class Meta:
        model = Stock
        fields = "__all__"

    def get_discount(self, obj):
        return obj.discount_level()

    def create(self, validated_data):
        from eda.services.stock_service import get_stock_analysis
        from eda.services.regression_service import predict_next_day_price, tomorrow_date_str

        ticker = (validated_data.get("ticker") or "").upper().strip()
        validated_data["ticker"] = ticker
        analysis = get_stock_analysis(ticker)
        if not analysis:
            raise serializers.ValidationError({"ticker": "Invalid ticker symbol"})

        validated_data["current_price"] = analysis.get("current_price") or 0
        validated_data["pe_ratio"] = analysis.get("pe_ratio") or 0
        validated_data["high_52w"] = analysis.get("high_52w")
        validated_data["low_52w"] = analysis.get("low_52w")
        validated_data["company_name"] = analysis.get("company_name") or analysis.get("ticker")
        history_30 = (analysis.get("price_history") or [])[-30:]
        validated_data["price_history_30"] = history_30
        validated_data["predicted_price"] = predict_next_day_price(history_30)
        validated_data["predicted_for_date"] = tomorrow_date_str()
        return super().create(validated_data)


class PortfolioSerializer(serializers.ModelSerializer):
    stocks = StockSerializer(many=True, read_only=True)

    class Meta:
        model = Portfolio
        fields = "__all__"

from rest_framework import serializers

class StockAnalysisSerializer(serializers.Serializer):
    ticker = serializers.CharField()
    company_name = serializers.CharField(required=False, allow_blank=True)
    current_price = serializers.FloatField()
    high_52w = serializers.FloatField()
    low_52w = serializers.FloatField()
    percent_from_low = serializers.FloatField()
    percent_from_high = serializers.FloatField()
    pe_ratio = serializers.FloatField(allow_null=True)
    market_cap = serializers.FloatField(allow_null=True)
    price_history = serializers.ListField()
    dates = serializers.ListField()
    pe_history = serializers.ListField()
    pe_quarters = serializers.ListField()
    opportunity_score = serializers.IntegerField()

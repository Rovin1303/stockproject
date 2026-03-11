from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services.stock_service import get_stock_analysis, search_stocks
from .services.metal_correlation_service import get_gold_silver_correlation
from .serializers import StockAnalysisSerializer
from portfolio.models import Stock
from staff.models import Staff


def _extract_staff_id(request):
    raw = request.query_params.get("staff_id")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None

class StockDetailAPIView(APIView):

    def get(self, request, stock_id):
        staff_id = _extract_staff_id(request)
        if not staff_id:
            return Response({"error": "Valid staff_id is required"}, status=status.HTTP_401_UNAUTHORIZED)

        staff = Staff.objects.filter(id=staff_id).first()
        if not staff:
            return Response({"error": "Invalid staff_id"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            stock_obj = Stock.objects.get(id=stock_id, portfolio__created_by=staff)
        except Stock.DoesNotExist:
            return Response(
                {"error": "Stock not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        ticker = stock_obj.ticker

        data = get_stock_analysis(ticker)

        if not data:
            return Response(
                {"error": "Invalid ticker"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = StockAnalysisSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class StockSearchAPIView(APIView):
    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if len(query) < 2:
            return Response([], status=status.HTTP_200_OK)

        results = search_stocks(query)
        return Response(results, status=status.HTTP_200_OK)


class GoldSilverCorrelationAPIView(APIView):
    def get(self, request):
        period = request.query_params.get("period", "5y")
        interval = request.query_params.get("interval", "1d")

        data = get_gold_silver_correlation(
            period=period,
            interval=interval,
        )
        if not data:
            return Response(
                {"error": "Unable to fetch gold/silver data for correlation"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(data, status=status.HTTP_200_OK)

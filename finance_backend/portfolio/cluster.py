import json
import os
import sys
from pathlib import Path
import pandas as pd


def _init_django():
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "finance_backend.settings")
    import django

    django.setup()


def fetch_stocks_from_portfolio(portfolio_id, csv_path=None):
    _init_django()
    from portfolio.models import Portfolio, Stock

    portfolio = Portfolio.objects.filter(id=portfolio_id).first()
    if not portfolio:
        print(f"Portfolio not found for id={portfolio_id}")
        return None

    queryset = Stock.objects.filter(portfolio_id=portfolio_id).order_by("id")
    if not queryset.exists():
        print(f"No stocks found for portfolio id={portfolio_id}")
        return None

    rows = list(
        queryset.values(
            "id",
            "portfolio_id",
            "company_name",
            "ticker",
            "current_price",
            "pe_ratio",
            "high_52w",
            "low_52w",
            "intrinsic_value",
        )
    )
    df = pd.DataFrame(rows)

    if csv_path is None:
        csv_path = Path.cwd() / f"portfolio_{portfolio_id}_stocks.csv"
    else:
        csv_path = Path(csv_path)

    df.to_csv(csv_path, index=False)

    print(f"Saved CSV: {csv_path}")
    print("Stocks JSON:")
    print(json.dumps(rows, indent=2, default=str))
    return df


def main():
    portfolio_id_text = input("Enter portfolio id: ").strip()
    if not portfolio_id_text.isdigit():
        print("Invalid portfolio id. Please enter a number.")
        return

    fetch_stocks_from_portfolio(int(portfolio_id_text))


if __name__ == "__main__":
    main()

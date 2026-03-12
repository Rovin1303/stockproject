import yfinance as yf
import time


_STOCK_ANALYSIS_CACHE = {}
_STOCK_ANALYSIS_CACHE_TTL_SECONDS = 120


def _resolve_live_price(stock, info, hist):
    # Prefer live-ish quote fields over daily close.
    try:
        fast_info = getattr(stock, "fast_info", None)
        if fast_info:
            last_price = fast_info.get("last_price")
            if last_price not in (None, 0):
                return float(last_price)
    except Exception:
        pass

    market_price = info.get("regularMarketPrice")
    if market_price not in (None, 0):
        return float(market_price)

    previous_close = info.get("previousClose")
    if previous_close not in (None, 0):
        return float(previous_close)

    if hist is not None and not hist.empty:
        return float(hist["Close"].iloc[-1])

    return None


def _resolve_pe_ratio(info, current_price):
    trailing_pe = info.get("trailingPE")
    if trailing_pe is not None:
        return float(trailing_pe)

    forward_pe = info.get("forwardPE")
    if forward_pe is not None:
        return float(forward_pe)

    trailing_eps = info.get("trailingEps")
    if trailing_eps not in (None, 0):
        try:
            return float(current_price / float(trailing_eps))
        except Exception:
            return None

    return None


def get_stock_analysis(ticker, force_refresh=False):

    key = (ticker or "").strip().upper()
    if not key:
        return None

    now = time.time()
    cached_entry = _STOCK_ANALYSIS_CACHE.get(key)
    if (not force_refresh) and cached_entry and (now - cached_entry["ts"]) < _STOCK_ANALYSIS_CACHE_TTL_SECONDS:
        return cached_entry["data"]

    try:
        stock = yf.Ticker(key)

        # ===============================
        # 1 YEAR PRICE DATA
        # ===============================
        hist = stock.history(
            period="1y",
            interval="1d",
            auto_adjust=False
        )

        if hist.empty:
            return None

        info = stock.info
        live_price = _resolve_live_price(stock, info, hist)
        if live_price is None:
            return None

        current_price = float(live_price)
        high_52w = float(hist["Close"].max())
        low_52w = float(hist["Close"].min())

        percent_from_high = float(((current_price - high_52w) / high_52w) * 100)
        percent_from_low = float(((current_price - low_52w) / low_52w) * 100)

        # ===============================
        # BASIC INFO
        # ===============================
        pe_ratio = _resolve_pe_ratio(info, current_price)
        market_cap = info.get("marketCap")

        # ===============================
        # PE RATIO - LAST 4 QUARTERS
        # ===============================

        pe_history = []
        pe_quarters = []

        try:
            earnings = stock.quarterly_earnings

            if earnings is not None and not earnings.empty:
                earnings = earnings.tail(4)

                for index, row in earnings.iterrows():
                    eps = row.get("Earnings")

                    if eps and eps != 0:
                        pe = round(current_price / eps, 2)
                        pe_history.append(pe)

                        quarter = f"{index.year}-Q{((index.month - 1)//3)+1}"
                        pe_quarters.append(quarter)

                pe_history.reverse()
                pe_quarters.reverse()

        except Exception as e:
            print("Quarterly earnings error:", e)

        # ===============================
        # OPPORTUNITY SCORE
        # ===============================

        lowFactor = max(0, 100 - percent_from_low)
        highFactor = max(0, -percent_from_high * 2)

        if pe_ratio:
            if pe_ratio < 20:
                peFactor = 80
            elif pe_ratio < 30:
                peFactor = 60
            else:
                peFactor = 30
        else:
            peFactor = 50

        score = round(
            (lowFactor * 0.4) +
            (highFactor * 0.3) +
            (peFactor * 0.3)
        )

        score = min(100, max(0, score))

        # ===============================
        # RETURN JSON RESPONSE
        # ===============================

        result = {
            "ticker": key,
            "company_name": info.get("longName") or info.get("shortName") or ticker,
            "current_price": round(current_price, 2),
            "high_52w": round(high_52w, 2),
            "low_52w": round(low_52w, 2),
            "percent_from_low": round(percent_from_low, 2),
            "percent_from_high": round(percent_from_high, 2),
            "pe_ratio": pe_ratio,
            "market_cap": market_cap,
            "price_history": hist["Close"].tolist(),
            "open_history": hist["Open"].tolist(),
            "high_history": hist["High"].tolist(),
            "low_history": hist["Low"].tolist(),
            "volume_history": hist["Volume"].fillna(0).tolist(),
            "dates": hist.index.strftime("%Y-%m-%d").tolist(),
            "pe_history": pe_history,
            "pe_quarters": pe_quarters,
            "opportunity_score": score
        }

        _STOCK_ANALYSIS_CACHE[key] = {
            "ts": now,
            "data": result,
        }
        return result

    except Exception as e:
        print("YFinance Error:", e)
        return None


def search_stocks(query):
    if not query or len(query.strip()) < 2:
        return []

    try:
        search = yf.Search(query=query, max_results=8)
        quotes = getattr(search, "quotes", []) or []

        results = []
        for item in quotes:
            symbol = item.get("symbol")
            name = item.get("shortname") or item.get("longname") or symbol
            exchange = item.get("exchDisp") or item.get("exchange")

            if not symbol:
                continue

            results.append(
                {
                    "ticker": symbol,
                    "name": name,
                    "exchange": exchange,
                }
            )

        return results
    except Exception as e:
        print("YFinance search error:", e)
        return []

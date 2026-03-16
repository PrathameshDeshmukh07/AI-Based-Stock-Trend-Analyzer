"""
AI-Based Stock Trend Analyzer
Flask backend with time-series prediction using probabilistic learning.
"""

import json
import datetime
from flask import Flask, jsonify, request, send_from_directory
import yfinance as yf
import pandas as pd
import numpy as np
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.arima.model import ARIMA
from scipy import stats
import warnings

warnings.filterwarnings("ignore")

app = Flask(__name__, static_folder="static", static_url_path="")


# ── Serve Frontend ────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ── Popular Stocks for Default View ──────────────────────────────────────────
POPULAR_STOCKS = [
    {"symbol": "AAPL", "name": "Apple Inc."},
    {"symbol": "MSFT", "name": "Microsoft Corporation"},
    {"symbol": "GOOGL", "name": "Alphabet Inc."},
    {"symbol": "AMZN", "name": "Amazon.com Inc."},
    {"symbol": "TSLA", "name": "Tesla Inc."},
    {"symbol": "META", "name": "Meta Platforms Inc."},
    {"symbol": "NVDA", "name": "NVIDIA Corporation"},
    {"symbol": "JPM", "name": "JPMorgan Chase & Co."},
    {"symbol": "V", "name": "Visa Inc."},
    {"symbol": "WMT", "name": "Walmart Inc."},
    {"symbol": "NFLX", "name": "Netflix Inc."},
    {"symbol": "DIS", "name": "The Walt Disney Company"},
    {"symbol": "RELIANCE.NS", "name": "Reliance Industries (NSE)"},
    {"symbol": "TCS.NS", "name": "Tata Consultancy Services (NSE)"},
    {"symbol": "INFY.NS", "name": "Infosys Ltd. (NSE)"},
]


# ── Helper: Fetch Stock Data ────────────────────────────────────────────────
def fetch_stock_data(symbol, period="1y"):
    """Fetch historical stock data using yfinance."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        if hist.empty:
            return None, None
        info = {}
        try:
            raw_info = ticker.info
            info = {
                "name": raw_info.get("shortName", symbol),
                "sector": raw_info.get("sector", "N/A"),
                "industry": raw_info.get("industry", "N/A"),
                "marketCap": raw_info.get("marketCap", 0),
                "currency": raw_info.get("currency", "USD"),
            }
        except Exception:
            info = {
                "name": symbol,
                "sector": "N/A",
                "industry": "N/A",
                "marketCap": 0,
                "currency": "USD",
            }
        return hist, info
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None, None


# ── Helper: Compute Technical Indicators ─────────────────────────────────────
def compute_indicators(df):
    """Calculate RSI, MACD, Bollinger Bands, and Moving Averages."""
    close = df["Close"]

    # Moving Averages
    sma_20 = close.rolling(window=20).mean()
    sma_50 = close.rolling(window=50).mean()
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()

    # MACD
    macd_line = ema_12 - ema_26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_histogram = macd_line - signal_line

    # RSI (14-period)
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    # Bollinger Bands (20-period)
    bb_middle = sma_20
    bb_std = close.rolling(window=20).std()
    bb_upper = bb_middle + (bb_std * 2)
    bb_lower = bb_middle - (bb_std * 2)

    # Volume Moving Average
    vol_ma = df["Volume"].rolling(window=20).mean()

    return {
        "sma_20": sma_20,
        "sma_50": sma_50,
        "ema_12": ema_12,
        "ema_26": ema_26,
        "macd_line": macd_line,
        "signal_line": signal_line,
        "macd_histogram": macd_histogram,
        "rsi": rsi,
        "bb_upper": bb_upper,
        "bb_middle": bb_middle,
        "bb_lower": bb_lower,
        "vol_ma": vol_ma,
    }


# ── Helper: Time-Series Prediction ──────────────────────────────────────────
def predict_trend(df, forecast_days=30):
    """
    Probabilistic trend forecast using ARIMA + Exponential Smoothing ensemble.
    Returns point forecasts with 80% and 95% confidence intervals.
    """
    close = df["Close"].dropna().values
    if len(close) < 60:
        return None

    forecasts = []
    conf_80 = []
    conf_95 = []
    dates = []

    last_date = df.index[-1]
    for i in range(1, forecast_days + 1):
        next_date = last_date + pd.Timedelta(days=i)
        dates.append(next_date.strftime("%Y-%m-%d"))

    # ── Method 1: ARIMA ──────────────────────────────────────────────────
    arima_forecast = None
    arima_conf = None
    try:
        model_arima = ARIMA(close, order=(5, 1, 2))
        fitted_arima = model_arima.fit()
        pred_arima = fitted_arima.get_forecast(steps=forecast_days)
        arima_forecast = pred_arima.predicted_mean
        arima_conf_80 = pred_arima.conf_int(alpha=0.20)
        arima_conf_95 = pred_arima.conf_int(alpha=0.05)
    except Exception:
        pass

    # ── Method 2: Exponential Smoothing ──────────────────────────────────
    es_forecast = None
    try:
        model_es = ExponentialSmoothing(
            close, trend="add", seasonal=None, damped_trend=True
        )
        fitted_es = model_es.fit(optimized=True)
        es_forecast = fitted_es.forecast(steps=forecast_days)
    except Exception:
        pass

    # ── Ensemble Combination ─────────────────────────────────────────────
    if arima_forecast is not None and es_forecast is not None:
        # Weighted average: 60% ARIMA, 40% ES
        ensemble = 0.6 * arima_forecast + 0.4 * es_forecast
        for i in range(forecast_days):
            forecasts.append(float(ensemble[i]))
            conf_80.append(
                [float(arima_conf_80[i, 0]), float(arima_conf_80[i, 1])]
            )
            conf_95.append(
                [float(arima_conf_95[i, 0]), float(arima_conf_95[i, 1])]
            )
    elif arima_forecast is not None:
        for i in range(forecast_days):
            forecasts.append(float(arima_forecast[i]))
            conf_80.append(
                [float(arima_conf_80[i, 0]), float(arima_conf_80[i, 1])]
            )
            conf_95.append(
                [float(arima_conf_95[i, 0]), float(arima_conf_95[i, 1])]
            )
    elif es_forecast is not None:
        # Generate synthetic confidence intervals from volatility
        vol = float(np.std(close[-30:]))
        for i in range(forecast_days):
            f = float(es_forecast[i])
            forecasts.append(f)
            spread_80 = vol * np.sqrt(i + 1) * 1.28
            spread_95 = vol * np.sqrt(i + 1) * 1.96
            conf_80.append([f - spread_80, f + spread_80])
            conf_95.append([f - spread_95, f + spread_95])
    else:
        return None

    # ── Trend Direction and Strength ─────────────────────────────────────
    current_price = float(close[-1])
    predicted_end = forecasts[-1]
    change_pct = ((predicted_end - current_price) / current_price) * 100

    if change_pct > 2:
        trend = "BULLISH"
        strength = min(abs(change_pct) / 10, 1.0)
    elif change_pct < -2:
        trend = "BEARISH"
        strength = min(abs(change_pct) / 10, 1.0)
    else:
        trend = "NEUTRAL"
        strength = 0.3

    # ── Probability Calculation ──────────────────────────────────────────
    # Use recent returns to compute probability of positive/negative movement
    returns = np.diff(close[-60:]) / close[-61:-1]
    prob_up = float(np.mean(returns > 0))
    prob_down = 1 - prob_up

    return {
        "dates": dates,
        "forecast": forecasts,
        "conf_80": conf_80,
        "conf_95": conf_95,
        "trend": trend,
        "strength": round(strength, 2),
        "change_pct": round(change_pct, 2),
        "current_price": round(current_price, 2),
        "predicted_price": round(predicted_end, 2),
        "probability_up": round(prob_up * 100, 1),
        "probability_down": round(prob_down * 100, 1),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  API  ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════


@app.route("/api/stock/<symbol>")
def get_stock(symbol):
    """Fetch historical data for a stock symbol."""
    period = request.args.get("period", "1y")
    hist, info = fetch_stock_data(symbol.upper(), period)
    if hist is None:
        return jsonify({"error": f"Could not fetch data for {symbol}"}), 404

    data = {
        "symbol": symbol.upper(),
        "info": info,
        "dates": [d.strftime("%Y-%m-%d") for d in hist.index],
        "open": [round(float(v), 2) for v in hist["Open"]],
        "high": [round(float(v), 2) for v in hist["High"]],
        "low": [round(float(v), 2) for v in hist["Low"]],
        "close": [round(float(v), 2) for v in hist["Close"]],
        "volume": [int(v) for v in hist["Volume"]],
    }
    return jsonify(data)


@app.route("/api/predict/<symbol>")
def get_prediction(symbol):
    """Run time-series prediction on a stock."""
    period = request.args.get("period", "1y")
    forecast_days = int(request.args.get("days", 30))
    hist, info = fetch_stock_data(symbol.upper(), period)
    if hist is None:
        return jsonify({"error": f"Could not fetch data for {symbol}"}), 404

    prediction = predict_trend(hist, forecast_days)
    if prediction is None:
        return jsonify({"error": "Not enough data for prediction"}), 400

    prediction["symbol"] = symbol.upper()
    prediction["info"] = info
    return jsonify(prediction)


@app.route("/api/indicators/<symbol>")
def get_indicators(symbol):
    """Compute technical indicators for a stock."""
    period = request.args.get("period", "1y")
    hist, info = fetch_stock_data(symbol.upper(), period)
    if hist is None:
        return jsonify({"error": f"Could not fetch data for {symbol}"}), 404

    indicators = compute_indicators(hist)

    def to_list(series):
        return [None if pd.isna(v) else round(float(v), 2) for v in series]

    data = {
        "symbol": symbol.upper(),
        "dates": [d.strftime("%Y-%m-%d") for d in hist.index],
        "close": [round(float(v), 2) for v in hist["Close"]],
        "volume": [int(v) for v in hist["Volume"]],
        "sma_20": to_list(indicators["sma_20"]),
        "sma_50": to_list(indicators["sma_50"]),
        "ema_12": to_list(indicators["ema_12"]),
        "ema_26": to_list(indicators["ema_26"]),
        "macd_line": to_list(indicators["macd_line"]),
        "signal_line": to_list(indicators["signal_line"]),
        "macd_histogram": to_list(indicators["macd_histogram"]),
        "rsi": to_list(indicators["rsi"]),
        "bb_upper": to_list(indicators["bb_upper"]),
        "bb_middle": to_list(indicators["bb_middle"]),
        "bb_lower": to_list(indicators["bb_lower"]),
        "vol_ma": to_list(indicators["vol_ma"]),
        # Latest values for the dashboard cards
        "latest": {
            "rsi": round(float(indicators["rsi"].dropna().iloc[-1]), 2)
            if not indicators["rsi"].dropna().empty
            else None,
            "macd": round(float(indicators["macd_line"].dropna().iloc[-1]), 2)
            if not indicators["macd_line"].dropna().empty
            else None,
            "signal": round(
                float(indicators["signal_line"].dropna().iloc[-1]), 2
            )
            if not indicators["signal_line"].dropna().empty
            else None,
            "sma_20": round(float(indicators["sma_20"].dropna().iloc[-1]), 2)
            if not indicators["sma_20"].dropna().empty
            else None,
            "sma_50": round(float(indicators["sma_50"].dropna().iloc[-1]), 2)
            if not indicators["sma_50"].dropna().empty
            else None,
            "bb_upper": round(
                float(indicators["bb_upper"].dropna().iloc[-1]), 2
            )
            if not indicators["bb_upper"].dropna().empty
            else None,
            "bb_lower": round(
                float(indicators["bb_lower"].dropna().iloc[-1]), 2
            )
            if not indicators["bb_lower"].dropna().empty
            else None,
        },
    }
    return jsonify(data)


@app.route("/api/search")
def search_stocks():
    """Search for stock symbols."""
    query = request.args.get("q", "").upper()
    if not query:
        return jsonify(POPULAR_STOCKS)
    results = [s for s in POPULAR_STOCKS if query in s["symbol"] or query in s["name"].upper()]
    # Also try direct yfinance lookup
    if not results:
        try:
            ticker = yf.Ticker(query)
            hist = ticker.history(period="5d")
            if not hist.empty:
                try:
                    name = ticker.info.get("shortName", query)
                except Exception:
                    name = query
                results.append({"symbol": query, "name": name})
        except Exception:
            pass
    return jsonify(results)


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n  🚀  AI-Based Stock Trend Analyzer")
    print("  ──────────────────────────────────")
    print("  Open http://localhost:5000 in your browser\n")
    app.run(debug=True, host="0.0.0.0", port=5000)

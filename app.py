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
import os
import requests
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.arima.model import ARIMA
from scipy import stats
import warnings


warnings.filterwarnings("ignore")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")


# ── Serve Frontend ────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return app.send_static_file("index.html")


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


# Simple memory cache for fetched data
_data_cache = {}
CACHE_DURATION = 3600  # 1 hour

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
    recent_close = close[-60:]
    returns = np.diff(recent_close) / recent_close[:-1]
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


@app.route("/api/chat", methods=["POST"])
def chat():
    """Dynamic AI chatbot for stock queries."""
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"reply": "I'm sorry, I didn't catch that."}), 400

    msg = data["message"].lower()
    symbol = data.get("symbol", "").upper()
    has_symbol = bool(symbol and symbol != "—" and symbol.strip())

    if "hello" in msg or "hi" in msg:
        return jsonify({"reply": "Hello there! I'm your AI Stock Assistant. How can I help you analyze the market today?"})

    elif "predict" in msg or "trend" in msg or "forecast" in msg or "target" in msg:
        if not has_symbol:
            return jsonify({"reply": "Please search for a stock first so I can forecast it!"})
            
        df, info = fetch_stock_data(symbol, "1y")
        if df is None:
            return jsonify({"reply": f"Sorry, I couldn't fetch data for {symbol}."})
            
        pred = predict_trend(df)
        if pred:
            price = pred["predicted_price"]
            trend = pred["trend"].title()
            return jsonify({"reply": f"Based on my ARIMA and Exponential Smoothing models, the 30-day forecast for {symbol} is **{trend}**, with a target price of **${price}**."})
        else:
            return jsonify({"reply": f"Sorry, there is not enough historical data to generate a confident prediction for {symbol} right now."})
            
    elif "price" in msg or "quote" in msg or "how much" in msg:
        if not has_symbol:
             return jsonify({"reply": "Please search for a stock first so I can check its price!"})
             
        df, info = fetch_stock_data(symbol, "1mo")
        if df is None:
            return jsonify({"reply": f"Sorry, I couldn't fetch the price for {symbol}."})
            
        current_price = df["Close"].iloc[-1]
        return jsonify({"reply": f"The current real-time price of **{symbol}** is **${current_price:.2f}**."})

    elif "rsi" in msg:
        if not has_symbol:
            return jsonify({"reply": "The Relative Strength Index (RSI) measures momentum. Over 70 is overbought, under 30 is oversold. Search a stock to see its RSI!"})
            
        df, info = fetch_stock_data(symbol, "6mo")
        if df is None:
             return jsonify({"reply": f"Sorry, I couldn't fetch data for {symbol}."})
             
        inds = compute_indicators(df)
        rsi = inds["rsi"].dropna().iloc[-1]
        
        status = "neutral"
        if rsi > 70: status = "**overbought**"
        elif rsi < 30: status = "**oversold**"
        
        return jsonify({"reply": f"The current RSI for {symbol} is **{rsi:.1f}**. This indicates the stock is currently {status}."})
        
    elif "macd" in msg:
        if not has_symbol:
            return jsonify({"reply": "MACD is a trend-following momentum indicator. Search a stock to see its live MACD!"})
            
        df, info = fetch_stock_data(symbol, "6mo")
        if df is None:
             return jsonify({"reply": f"Sorry, I couldn't fetch data for {symbol}."})
             
        inds = compute_indicators(df)
        macd = inds["macd_line"].dropna().iloc[-1]
        signal = inds["signal_line"].dropna().iloc[-1]
        
        status = "**bullish** setup" if macd > signal else "**bearish** setup"
        
        return jsonify({"reply": f"The MACD line for {symbol} is at **{macd:.2f}**, and the Signal line is at **{signal:.2f}**. Since the MACD is {'above' if macd > signal else 'below'} the signal, this is a {status}."})

    elif "thank" in msg:
        return jsonify({"reply": "You're welcome! Let me know if you need anything else."})
        
    return jsonify({"reply": "I'm still learning! Right now I can tell you the real-time **price**, **forecast**, **RSI**, or **MACD** of the stock you are viewing. Try asking me one of those!"})


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
    import os
    port = int(os.environ.get("PORT", 8080))
    print("\n  🚀  AI-Based Stock Trend Analyzer")
    print("  ──────────────────────────────────")
    print(f"  Starting server on port {port}...\n")
    app.run(debug=True, host="0.0.0.0", port=port)

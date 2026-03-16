# 🚀 AI-Based Stock Trend Analyzer

A full-stack web application for **stock trend prediction** using **probabilistic learning** on **time-series data**. Built with a Python/Flask backend and a modern glassmorphism frontend.

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1-000000?style=for-the-badge&logo=flask&logoColor=white)
![Chart.js](https://img.shields.io/badge/Chart.js-4.4-FF6384?style=for-the-badge&logo=chartdotjs&logoColor=white)

---

## 📋 Project Details

| Item | Description |
|---|---|
| **Problem** | Stock Trend Prediction |
| **Feasibility Study** | Time-Series Analysis |
| **AI Technique(s)** | Probabilistic Learning (ARIMA + Exponential Smoothing) |
| **Representation** | Time-Series Model |
| **Tools** | Python, Flask, yfinance, statsmodels, Chart.js |
| **Outcome** | Trend Forecast with Confidence Intervals |

---

## ✨ Features

- 📈 **Real-time Stock Data** — Fetches live OHLCV data via Yahoo Finance
- 🤖 **AI Trend Prediction** — ARIMA + Exponential Smoothing ensemble model
- 📊 **Interactive Charts** — Price, RSI, MACD, Volume with Chart.js
- 🎯 **Confidence Intervals** — 80% and 95% probabilistic forecast bands
- 📉 **Technical Indicators** — RSI, MACD, Bollinger Bands, SMA/EMA
- 🔍 **Stock Search** — Search any stock symbol globally
- 🌙 **Dark Glassmorphism UI** — Premium modern design with animations
- 📱 **Responsive** — Works on desktop, tablet, and mobile

---

## 🛠️ Installation

### Prerequisites
- Python 3.9 or higher
- pip (Python package manager)

### Setup

```bash
# Clone the repository
git clone https://github.com/Prathamesh-07git/AI-Based-Stock-Trend-Analyzer.git
cd AI-Based-Stock-Trend-Analyzer

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

Open **http://localhost:5000** in your browser.

---

## 🏗️ Architecture

```
AI-Based-Stock-Trend-Analyzer/
├── app.py                  # Flask backend + prediction engine
├── requirements.txt        # Python dependencies
├── .gitignore
├── README.md
└── static/
    ├── index.html          # Dashboard UI
    ├── css/
    │   └── style.css       # Dark glassmorphism styles
    └── js/
        └── app.js          # Chart rendering & API integration
```

### AI Pipeline

```
Stock Symbol → yfinance API → Historical Data
                                    ↓
                        ┌───────────┴───────────┐
                        │                       │
                    ARIMA(5,1,2)        Exponential Smoothing
                        │               (Damped Trend)
                        └───────────┬───────────┘
                                    ↓
                        Ensemble (60/40 Weighted)
                                    ↓
                    Forecast + 80%/95% Confidence Bands
                                    ↓
                        Trend: BULLISH / BEARISH / NEUTRAL
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/stock/<symbol>` | Historical OHLCV data |
| `GET` | `/api/predict/<symbol>` | AI trend forecast with confidence intervals |
| `GET` | `/api/indicators/<symbol>` | Technical indicators (RSI, MACD, BB) |
| `GET` | `/api/search?q=<query>` | Search stock symbols |

---

## ⚠️ Disclaimer

This tool uses AI-based probabilistic models for **educational purposes only**. Predictions are **not financial advice**. Past performance does not guarantee future results. Always consult a qualified financial advisor before making investment decisions.

---

## 📄 License

This project is for educational and academic purposes.

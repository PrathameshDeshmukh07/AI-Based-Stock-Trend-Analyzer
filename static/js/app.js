/**
 * AI-Based Stock Trend Analyzer
 * Frontend application — Chart rendering, API calls, and UI interactions
 */

// ── State ────────────────────────────────────────────────────────────────────
const state = {
    symbol: null,
    period: "1y",
    stockData: null,
    prediction: null,
    indicators: null,
    charts: {},
};

// ── DOM References ───────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);
const welcomeScreen = $("welcomeScreen");
const dashboard = $("dashboard");
const loadingOverlay = $("loadingOverlay");
const searchInput = $("searchInput");
const searchDropdown = $("searchDropdown");

// ── Chart.js Defaults ────────────────────────────────────────────────────────
function applyChartTheme(theme) {
    const isDark = theme !== "light";
    Chart.defaults.color = isDark ? "#94a3b8" : "#64748b";
    Chart.defaults.borderColor = isDark ? "rgba(255,255,255,0.04)" : "rgba(0,0,0,0.06)";
    Chart.defaults.plugins.tooltip.backgroundColor = isDark ? "rgba(17, 24, 39, 0.95)" : "rgba(255, 255, 255, 0.95)";
    Chart.defaults.plugins.tooltip.titleColor = isDark ? "#f1f5f9" : "#1e293b";
    Chart.defaults.plugins.tooltip.bodyColor = isDark ? "#94a3b8" : "#475569";
    Chart.defaults.plugins.tooltip.borderColor = isDark ? "rgba(99, 102, 241, 0.3)" : "rgba(99, 102, 241, 0.2)";
}
Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.pointStyleWidth = 10;
Chart.defaults.plugins.tooltip.borderWidth = 1;
Chart.defaults.plugins.tooltip.cornerRadius = 10;
Chart.defaults.plugins.tooltip.padding = 12;
Chart.defaults.plugins.tooltip.titleFont = { weight: "600", size: 13 };
Chart.defaults.plugins.tooltip.bodyFont = { size: 12 };
applyChartTheme(localStorage.getItem("stockai-theme") || "dark");

// ── Theme Toggle ─────────────────────────────────────────────────────────────
function setupThemeToggle() {
    const toggle = document.getElementById("themeToggle");
    const saved = localStorage.getItem("stockai-theme") || "dark";
    document.documentElement.setAttribute("data-theme", saved);

    toggle.addEventListener("click", () => {
        const cur = document.documentElement.getAttribute("data-theme");
        const next = cur === "light" ? "dark" : "light";
        document.documentElement.setAttribute("data-theme", next);
        localStorage.setItem("stockai-theme", next);
        applyChartTheme(next);
        // Re-render charts so grid/tooltip colours update
        if (state.stockData) {
            renderPriceChart();
            renderRSIChart();
            renderMACDChart();
            renderVolumeChart();
        }
    });
}

// ── Initialize ───────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    lucide.createIcons();
    setupThemeToggle();
    setupSearch();
    setupPeriodButtons();
    loadPopularStocks();
});

// ── Search ───────────────────────────────────────────────────────────────────
function setupSearch() {
    let debounceTimer;

    searchInput.addEventListener("input", () => {
        clearTimeout(debounceTimer);
        const query = searchInput.value.trim();
        if (query.length === 0) {
            hideDropdown();
            return;
        }
        debounceTimer = setTimeout(() => searchStocks(query), 300);
    });

    searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            const query = searchInput.value.trim().toUpperCase();
            if (query) {
                hideDropdown();
                loadStock(query);
            }
        }
    });

    document.addEventListener("click", (e) => {
        if (!$("searchContainer").contains(e.target)) {
            hideDropdown();
        }
    });
}

async function searchStocks(query) {
    try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        renderDropdown(data);
    } catch (err) {
        console.error("Search error:", err);
    }
}

function renderDropdown(items) {
    if (!items.length) {
        hideDropdown();
        return;
    }
    searchDropdown.innerHTML = items
        .map(
            (item) => `
        <div class="search-item" onclick="selectStock('${item.symbol}')">
            <span class="search-item-symbol">${item.symbol}</span>
            <span class="search-item-name">${item.name}</span>
        </div>`
        )
        .join("");
    searchDropdown.classList.add("show");
}

function hideDropdown() {
    searchDropdown.classList.remove("show");
}

function selectStock(symbol) {
    searchInput.value = symbol;
    hideDropdown();
    loadStock(symbol);
}

// ── Period Buttons ───────────────────────────────────────────────────────────
function setupPeriodButtons() {
    document.querySelectorAll(".period-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".period-btn").forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            state.period = btn.dataset.period;
            if (state.symbol) {
                loadStock(state.symbol);
            }
        });
    });
}

// ── Popular Stocks ───────────────────────────────────────────────────────────
async function loadPopularStocks() {
    try {
        const res = await fetch("/api/search?q=");
        const data = await res.json();
        const list = document.querySelector(".popular-list");
        list.innerHTML = data
            .slice(0, 10)
            .map(
                (s) =>
                    `<span class="popular-chip" onclick="selectStock('${s.symbol}')">${s.symbol}</span>`
            )
            .join("");
    } catch (err) {
        console.error("Error loading popular stocks:", err);
    }
}

// ── Load Stock Data ──────────────────────────────────────────────────────────
async function loadStock(symbol) {
    state.symbol = symbol.toUpperCase();
    showLoading();

    try {
        // Fetch all data in parallel, but enforce a minimum 4000ms loading time 
        // to let the premium loading animations play out completely.
        const [stockRes, predRes, indRes] = await Promise.all([
            fetch(`/api/stock/${state.symbol}?period=${state.period}`),
            fetch(`/api/predict/${state.symbol}?period=${state.period}&days=30`),
            fetch(`/api/indicators/${state.symbol}?period=${state.period}`),
            new Promise(resolve => setTimeout(resolve, 4000)) // Enforce 4s minimum wait
        ]);

        if (!stockRes.ok) {
            const err = await stockRes.json();
            throw new Error(err.error || "Failed to fetch stock data");
        }

        state.stockData = await stockRes.json();
        state.prediction = predRes.ok ? await predRes.json() : null;
        state.indicators = indRes.ok ? await indRes.json() : null;

        // Show dashboard
        welcomeScreen.style.display = "none";
        dashboard.style.display = "block";

        // Render everything
        renderStockInfo();
        renderTrendCards();
        renderPriceChart();
        renderRSIChart();
        renderMACDChart();
        renderVolumeChart();
        renderIndicatorsSummary();

        // Re-init icons
        lucide.createIcons();
    } catch (err) {
        console.error("Error loading stock:", err);
        alert(`Error: ${err.message}`);
    } finally {
        hideLoading();
    }
}

// ── Render Stock Info Bar ────────────────────────────────────────────────────
function renderStockInfo() {
    const d = state.stockData;
    if (!d) return;

    $("stockName").textContent = d.info?.name || d.symbol;
    $("stockSymbol").textContent = d.symbol;
    $("stockSector").textContent = d.info?.sector || "";

    const lastPrice = d.close[d.close.length - 1];
    const prevPrice = d.close[d.close.length - 2] || lastPrice;
    const change = lastPrice - prevPrice;
    const changePct = ((change / prevPrice) * 100).toFixed(2);

    $("currentPrice").textContent = `${d.info?.currency || "$"} ${lastPrice.toFixed(2)}`;

    const changeEl = $("priceChange");
    const sign = change >= 0 ? "+" : "";
    changeEl.textContent = `${sign}${change.toFixed(2)} (${sign}${changePct}%)`;
    changeEl.className = `price-change ${change >= 0 ? "up" : "down"}`;
}

// ── Render Trend Cards ───────────────────────────────────────────────────────
function renderTrendCards() {
    const p = state.prediction;
    if (!p || p.error) {
        $("trendDirection").textContent = "N/A";
        $("predictedPrice").textContent = "N/A";
        $("probUp").textContent = "N/A";
        $("probDown").textContent = "N/A";
        return;
    }

    // Trend direction
    const trendEl = $("trendDirection");
    trendEl.textContent = p.trend;
    trendEl.className = `card-value ${p.trend.toLowerCase()}`;
    $("trendStrength").textContent = `Strength: ${(p.strength * 100).toFixed(0)}%`;

    // Predicted price
    $("predictedPrice").textContent = `$${p.predicted_price.toFixed(2)}`;
    const changeEl = $("predictedChange");
    const sign = p.change_pct >= 0 ? "+" : "";
    changeEl.textContent = `${sign}${p.change_pct.toFixed(2)}% in 30 days`;
    changeEl.style.color = p.change_pct >= 0 ? "var(--green)" : "var(--red)";

    // Probabilities
    $("probUp").textContent = `${p.probability_up}%`;
    $("probDown").textContent = `${p.probability_down}%`;
    $("probUpBar").style.width = `${p.probability_up}%`;
    $("probDownBar").style.width = `${p.probability_down}%`;

    // Color the trend card accent
    const dirCard = $("trendDirectionCard");
    if (p.trend === "BULLISH") {
        dirCard.style.borderTopColor = "var(--green)";
    } else if (p.trend === "BEARISH") {
        dirCard.style.borderTopColor = "var(--red)";
    } else {
        dirCard.style.borderTopColor = "var(--yellow)";
    }
}

// ── Render Price Chart ───────────────────────────────────────────────────────
function renderPriceChart() {
    const d = state.stockData;
    if (!d) return;

    if (state.charts.price) state.charts.price.destroy();

    const datasets = [];

    // Historical close
    datasets.push({
        label: "Close Price",
        data: d.dates.map((date, i) => ({ x: date, y: d.close[i] })),
        borderColor: "#6366f1",
        backgroundColor: "rgba(99, 102, 241, 0.08)",
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 5,
        pointHoverBackgroundColor: "#6366f1",
        fill: true,
        tension: 0.3,
        order: 2,
    });

    // Bollinger Bands from indicators
    if (state.indicators) {
        const ind = state.indicators;
        datasets.push({
            label: "BB Upper",
            data: ind.dates.map((date, i) => ({ x: date, y: ind.bb_upper[i] })),
            borderColor: "rgba(168, 85, 247, 0.3)",
            borderWidth: 1,
            borderDash: [4, 4],
            pointRadius: 0,
            fill: false,
            tension: 0.3,
            order: 3,
        });
        datasets.push({
            label: "BB Lower",
            data: ind.dates.map((date, i) => ({ x: date, y: ind.bb_lower[i] })),
            borderColor: "rgba(168, 85, 247, 0.3)",
            borderWidth: 1,
            borderDash: [4, 4],
            pointRadius: 0,
            fill: "-1",
            backgroundColor: "rgba(168, 85, 247, 0.04)",
            tension: 0.3,
            order: 3,
        });

        // SMA 20
        datasets.push({
            label: "SMA 20",
            data: ind.dates.map((date, i) => ({ x: date, y: ind.sma_20[i] })),
            borderColor: "rgba(245, 158, 11, 0.6)",
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false,
            tension: 0.3,
            order: 3,
        });

        // SMA 50
        datasets.push({
            label: "SMA 50",
            data: ind.dates.map((date, i) => ({ x: date, y: ind.sma_50[i] })),
            borderColor: "rgba(6, 182, 212, 0.6)",
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false,
            tension: 0.3,
            order: 3,
        });
    }

    // Prediction
    const p = state.prediction;
    if (p && !p.error) {
        // Connect last historical point to first forecast
        const lastDate = d.dates[d.dates.length - 1];
        const lastClose = d.close[d.close.length - 1];

        // Forecast line
        const forecastData = [{ x: lastDate, y: lastClose }];
        const conf95Upper = [{ x: lastDate, y: lastClose }];
        const conf95Lower = [{ x: lastDate, y: lastClose }];
        const conf80Upper = [{ x: lastDate, y: lastClose }];
        const conf80Lower = [{ x: lastDate, y: lastClose }];

        p.dates.forEach((date, i) => {
            forecastData.push({ x: date, y: p.forecast[i] });
            conf95Upper.push({ x: date, y: p.conf_95[i][1] });
            conf95Lower.push({ x: date, y: p.conf_95[i][0] });
            conf80Upper.push({ x: date, y: p.conf_80[i][1] });
            conf80Lower.push({ x: date, y: p.conf_80[i][0] });
        });

        // 95% confidence band
        datasets.push({
            label: "95% Confidence",
            data: conf95Upper,
            borderColor: "transparent",
            backgroundColor: "rgba(16, 185, 129, 0.06)",
            pointRadius: 0,
            fill: false,
            tension: 0.3,
            order: 4,
        });
        datasets.push({
            label: "95% Lower",
            data: conf95Lower,
            borderColor: "transparent",
            backgroundColor: "rgba(16, 185, 129, 0.06)",
            pointRadius: 0,
            fill: "-1",
            tension: 0.3,
            order: 4,
        });

        // 80% confidence band
        datasets.push({
            label: "80% Confidence",
            data: conf80Upper,
            borderColor: "transparent",
            backgroundColor: "rgba(16, 185, 129, 0.12)",
            pointRadius: 0,
            fill: false,
            tension: 0.3,
            order: 4,
        });
        datasets.push({
            label: "80% Lower",
            data: conf80Lower,
            borderColor: "transparent",
            backgroundColor: "rgba(16, 185, 129, 0.12)",
            pointRadius: 0,
            fill: "-1",
            tension: 0.3,
            order: 4,
        });

        // Forecast line
        const trendColor = p.trend === "BULLISH" ? "#10b981" : p.trend === "BEARISH" ? "#ef4444" : "#f59e0b";
        datasets.push({
            label: "Forecast",
            data: forecastData,
            borderColor: trendColor,
            borderWidth: 2.5,
            borderDash: [6, 4],
            pointRadius: 0,
            pointHoverRadius: 5,
            pointHoverBackgroundColor: trendColor,
            fill: false,
            tension: 0.3,
            order: 1,
        });
    }

    const ctx = $("priceChart").getContext("2d");
    state.charts.price = new Chart(ctx, {
        type: "line",
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: "index",
                intersect: false,
            },
            scales: {
                x: {
                    type: "time",
                    time: { unit: "month", tooltipFormat: "MMM d, yyyy" },
                    grid: { display: false },
                    ticks: { font: { size: 11 } },
                },
                y: {
                    grid: { color: "rgba(255,255,255,0.03)" },
                    ticks: {
                        font: { size: 11 },
                        callback: (v) => "$" + v.toFixed(2),
                    },
                },
            },
            plugins: {
                legend: {
                    labels: {
                        filter: (item) => {
                            // Hide fill bands from legend
                            return !["95% Lower", "80% Lower"].includes(item.text);
                        },
                        font: { size: 11 },
                    },
                },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: $${ctx.parsed.y?.toFixed(2) || "N/A"}`,
                    },
                },
            },
        },
    });
}

// ── Render RSI Chart ─────────────────────────────────────────────────────────
function renderRSIChart() {
    const ind = state.indicators;
    if (!ind) return;
    if (state.charts.rsi) state.charts.rsi.destroy();

    const latestRSI = ind.latest?.rsi;
    $("rsiValue").textContent = latestRSI != null ? latestRSI.toFixed(1) : "—";

    const ctx = $("rsiChart").getContext("2d");
    state.charts.rsi = new Chart(ctx, {
        type: "line",
        data: {
            labels: ind.dates,
            datasets: [
                {
                    label: "RSI",
                    data: ind.rsi,
                    borderColor: "#a855f7",
                    backgroundColor: "rgba(168, 85, 247, 0.08)",
                    borderWidth: 1.5,
                    pointRadius: 0,
                    fill: true,
                    tension: 0.3,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    type: "time",
                    time: { unit: "month" },
                    display: false,
                },
                y: {
                    min: 0,
                    max: 100,
                    grid: { color: "rgba(255,255,255,0.03)" },
                    ticks: { font: { size: 10 } },
                },
            },
            plugins: {
                legend: { display: false },
                annotation: {
                    annotations: {
                        overbought: {
                            type: "line",
                            yMin: 70,
                            yMax: 70,
                            borderColor: "rgba(239, 68, 68, 0.4)",
                            borderDash: [4, 4],
                            borderWidth: 1,
                        },
                        oversold: {
                            type: "line",
                            yMin: 30,
                            yMax: 30,
                            borderColor: "rgba(16, 185, 129, 0.4)",
                            borderDash: [4, 4],
                            borderWidth: 1,
                        },
                    },
                },
            },
        },
        plugins: [
            {
                id: "rsiZones",
                beforeDraw(chart) {
                    const { ctx, chartArea, scales } = chart;
                    if (!chartArea) return;

                    // Overbought zone (70-100)
                    const y70 = scales.y.getPixelForValue(70);
                    const y100 = scales.y.getPixelForValue(100);
                    ctx.fillStyle = "rgba(239, 68, 68, 0.04)";
                    ctx.fillRect(chartArea.left, y100, chartArea.width, y70 - y100);

                    // Oversold zone (0-30)
                    const y30 = scales.y.getPixelForValue(30);
                    const y0 = scales.y.getPixelForValue(0);
                    ctx.fillStyle = "rgba(16, 185, 129, 0.04)";
                    ctx.fillRect(chartArea.left, y30, chartArea.width, y0 - y30);

                    // Lines
                    ctx.strokeStyle = "rgba(239, 68, 68, 0.3)";
                    ctx.setLineDash([4, 4]);
                    ctx.beginPath();
                    ctx.moveTo(chartArea.left, y70);
                    ctx.lineTo(chartArea.right, y70);
                    ctx.stroke();

                    ctx.strokeStyle = "rgba(16, 185, 129, 0.3)";
                    ctx.beginPath();
                    ctx.moveTo(chartArea.left, y30);
                    ctx.lineTo(chartArea.right, y30);
                    ctx.stroke();
                    ctx.setLineDash([]);
                },
            },
        ],
    });
}

// ── Render MACD Chart ────────────────────────────────────────────────────────
function renderMACDChart() {
    const ind = state.indicators;
    if (!ind) return;
    if (state.charts.macd) state.charts.macd.destroy();

    const latestMACD = ind.latest?.macd;
    $("macdValue").textContent = latestMACD != null ? latestMACD.toFixed(2) : "—";

    // Color histogram bars
    const histColors = ind.macd_histogram.map((v) =>
        v != null ? (v >= 0 ? "rgba(16, 185, 129, 0.6)" : "rgba(239, 68, 68, 0.6)") : "transparent"
    );

    const ctx = $("macdChart").getContext("2d");
    state.charts.macd = new Chart(ctx, {
        type: "bar",
        data: {
            labels: ind.dates,
            datasets: [
                {
                    label: "Histogram",
                    data: ind.macd_histogram,
                    backgroundColor: histColors,
                    borderWidth: 0,
                    barPercentage: 0.8,
                    order: 2,
                },
                {
                    label: "MACD",
                    data: ind.macd_line,
                    borderColor: "#3b82f6",
                    borderWidth: 1.5,
                    pointRadius: 0,
                    type: "line",
                    fill: false,
                    tension: 0.3,
                    order: 1,
                },
                {
                    label: "Signal",
                    data: ind.signal_line,
                    borderColor: "#f59e0b",
                    borderWidth: 1.5,
                    pointRadius: 0,
                    type: "line",
                    fill: false,
                    tension: 0.3,
                    order: 1,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    type: "time",
                    time: { unit: "month" },
                    display: false,
                },
                y: {
                    grid: { color: "rgba(255,255,255,0.03)" },
                    ticks: { font: { size: 10 } },
                },
            },
            plugins: {
                legend: {
                    labels: { font: { size: 10 } },
                },
            },
        },
    });
}

// ── Render Volume Chart ──────────────────────────────────────────────────────
function renderVolumeChart() {
    const d = state.stockData;
    if (!d) return;
    if (state.charts.volume) state.charts.volume.destroy();

    const volColors = d.close.map((c, i) => {
        if (i === 0) return "rgba(99, 102, 241, 0.4)";
        return c >= d.close[i - 1] ? "rgba(16, 185, 129, 0.4)" : "rgba(239, 68, 68, 0.4)";
    });

    const datasets = [
        {
            label: "Volume",
            data: d.dates.map((date, i) => ({ x: date, y: d.volume[i] })),
            backgroundColor: volColors,
            borderWidth: 0,
            barPercentage: 0.8,
        },
    ];

    if (state.indicators) {
        datasets.push({
            label: "Vol MA (20)",
            data: state.indicators.dates.map((date, i) => ({
                x: date,
                y: state.indicators.vol_ma[i],
            })),
            type: "line",
            borderColor: "rgba(245, 158, 11, 0.6)",
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false,
            tension: 0.3,
        });
    }

    const ctx = $("volumeChart").getContext("2d");
    state.charts.volume = new Chart(ctx, {
        type: "bar",
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    type: "time",
                    time: { unit: "month", tooltipFormat: "MMM d, yyyy" },
                    grid: { display: false },
                    ticks: { font: { size: 11 } },
                },
                y: {
                    grid: { color: "rgba(255,255,255,0.03)" },
                    ticks: {
                        font: { size: 10 },
                        callback: (v) => {
                            if (v >= 1e9) return (v / 1e9).toFixed(1) + "B";
                            if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
                            if (v >= 1e3) return (v / 1e3).toFixed(0) + "K";
                            return v;
                        },
                    },
                },
            },
            plugins: {
                legend: {
                    labels: { font: { size: 11 } },
                },
            },
        },
    });
}

// ── Render Indicators Summary Grid ───────────────────────────────────────────
function renderIndicatorsSummary() {
    const ind = state.indicators;
    if (!ind?.latest) return;

    const d = state.stockData;
    const lastClose = d ? d.close[d.close.length - 1] : 0;

    const items = [
        {
            label: "RSI (14)",
            value: ind.latest.rsi,
            format: (v) => v.toFixed(1),
            color: (v) => (v > 70 ? "down" : v < 30 ? "up" : ""),
        },
        {
            label: "MACD",
            value: ind.latest.macd,
            format: (v) => v.toFixed(2),
            color: (v) => (v > 0 ? "up" : "down"),
        },
        {
            label: "Signal",
            value: ind.latest.signal,
            format: (v) => v.toFixed(2),
            color: () => "",
        },
        {
            label: "SMA 20",
            value: ind.latest.sma_20,
            format: (v) => "$" + v.toFixed(2),
            color: (v) => (lastClose > v ? "up" : "down"),
        },
        {
            label: "SMA 50",
            value: ind.latest.sma_50,
            format: (v) => "$" + v.toFixed(2),
            color: (v) => (lastClose > v ? "up" : "down"),
        },
        {
            label: "BB Upper",
            value: ind.latest.bb_upper,
            format: (v) => "$" + v.toFixed(2),
            color: () => "",
        },
        {
            label: "BB Lower",
            value: ind.latest.bb_lower,
            format: (v) => "$" + v.toFixed(2),
            color: () => "",
        },
    ];

    // Add prediction data
    const p = state.prediction;
    if (p && !p.error) {
        items.push({
            label: "Forecast (30d)",
            value: p.predicted_price,
            format: (v) => "$" + v.toFixed(2),
            color: () => (p.change_pct >= 0 ? "up" : "down"),
        });
        items.push({
            label: "Prob. Up",
            value: p.probability_up,
            format: (v) => v + "%",
            color: (v) => (v > 50 ? "up" : "down"),
        });
        items.push({
            label: "Trend",
            value: p.trend,
            format: (v) => v,
            color: () =>
                p.trend === "BULLISH" ? "up" : p.trend === "BEARISH" ? "down" : "",
        });
    }

    const grid = $("indicatorsGrid");
    grid.innerHTML = items
        .map((item) => {
            if (item.value == null) return "";
            const colorClass = typeof item.color === "function" ? item.color(item.value) : "";
            const formattedValue =
                typeof item.format === "function" ? item.format(item.value) : item.value;
            return `
                <div class="indicator-item">
                    <span class="indicator-item-label">${item.label}</span>
                    <span class="indicator-item-value ${colorClass}">${formattedValue}</span>
                </div>`;
        })
        .join("");
}

// ── Loading ──────────────────────────────────────────────────────────────────
let _loaderInterval = null;
let _loaderStep = 0;
let _constellationAnimId = null;

const LOADER_MESSAGES = [
    "Fetching historical prices...",
    "Downloading market data...",
    "Running ARIMA model...",
    "Applying Exponential Smoothing...",
    "Computing technical indicators...",
    "Calculating RSI & MACD...",
    "Generating probability forecast...",
    "Building confidence intervals...",
    "Rendering visualizations...",
];

function showLoading() {
    loadingOverlay.classList.add("show");
    _loaderStep = 0;
    let msgIdx = 0;

    // Reset progress
    const bar = document.getElementById("loaderProgressBar");
    const status = document.getElementById("loaderStatus");
    if (bar) bar.style.width = "0%";

    // Reset steps
    ["step1","step2","step3"].forEach(id => {
        const el = document.getElementById(id);
        if (el) { el.classList.remove("active"); }
    });
    const s1 = document.getElementById("step1");
    if (s1) s1.classList.add("active");

    // Animate progress and steps
    _loaderInterval = setInterval(() => {
        _loaderStep++;

        // Rotate status message
        msgIdx = (msgIdx + 1) % LOADER_MESSAGES.length;
        if (status) status.textContent = LOADER_MESSAGES[msgIdx];

        // Advance progress bar (max 95%)
        const progress = Math.min(10 + _loaderStep * 8, 95);
        if (bar) bar.style.width = progress + "%";

        // Advance step indicators (total 3 steps, so spread them out)
        if (_loaderStep === 4) {
            const s1 = document.getElementById("step1");
            const s2 = document.getElementById("step2");
            if (s1) { s1.classList.remove("active"); }
            if (s2) s2.classList.add("active");
        }
        if (_loaderStep === 8) {
            const s2 = document.getElementById("step2");
            const s3 = document.getElementById("step3");
            if (s2) { s2.classList.remove("active"); }
            if (s3) s3.classList.add("active");
        }
    }, 500);
}

function hideLoading() {
    // Complete the progress to 100%
    const bar = document.getElementById("loaderProgressBar");
    if (bar) bar.style.width = "100%";

    // Short delay for the 100% fill to render before hiding
    setTimeout(() => {
        loadingOverlay.classList.remove("show");
        clearInterval(_loaderInterval);
        _loaderInterval = null;
    }, 400);
}

// %% Chatbot %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
document.addEventListener('DOMContentLoaded', () => {
    const chatFab = $('chatFab');
    const chatWindow = $('chatWindow');
    const chatClose = $('chatClose');
    const chatSend = $('chatSend');
    const chatInput = $('chatInput');
    const chatMessages = $('chatMessages');

    function toggleChat() {
        chatWindow.classList.toggle('open');
        if (chatWindow.classList.contains('open')) {
            setTimeout(() => chatInput.focus(), 300);
        }
    }

    chatFab.addEventListener('click', toggleChat);
    chatClose.addEventListener('click', toggleChat);

    function addMessage(text, sender) {
        const bubble = document.createElement('div');
        bubble.className = `chat-bubble ${sender}`;
        bubble.textContent = text;
        chatMessages.appendChild(bubble);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function addTypingIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'typing-indicator';
        indicator.id = 'typingIndicator';
        indicator.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';
        chatMessages.appendChild(indicator);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function removeTypingIndicator() {
        const indicator = typingIndicator;
        if (indicator) {
            indicator.remove();
        }
    }

    async function sendMessage() {
        const text = chatInput.value.trim();
        if (!text) return;

        chatInput.value = '';
        addMessage(text, 'user');
        addTypingIndicator();

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    message: text,
                    symbol: state.symbol || ' '
                })
            });
            const data = await res.json();
            
            removeTypingIndicator();
            if (data.reply) {
                addMessage(data.reply, 'bot');
            }
        } catch (err) {
            removeTypingIndicator();
            addMessage('Sorry, I encountered an error connecting to the server.', 'bot');
            console.error('Chat error:', err);
        }
    }

    chatSend.addEventListener('click', sendMessage);
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
});


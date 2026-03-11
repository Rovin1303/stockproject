import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Line } from "react-chartjs-2";
import "chart.js/auto";
import api from "../services/api";
import "./TimeSeriesForecast.css";

function TimeSeriesForecast() {
  const navigate = useNavigate();
  const staffName = localStorage.getItem("staff_name") || "Admin";

  const [portfolios, setPortfolios] = useState([]);
  const [stocks, setStocks] = useState([]);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState("");
  const [selectedStockId, setSelectedStockId] = useState("");
  const [selectedForecastType, setSelectedForecastType] = useState("ts_1");
  const [selectedModelType, setSelectedModelType] = useState("arima");
  const [historyRange, setHistoryRange] = useState("3m");
  const [forecastData, setForecastData] = useState(null);
  const [loadingPortfolios, setLoadingPortfolios] = useState(true);
  const [loadingStocks, setLoadingStocks] = useState(false);
  const [loadingForecast, setLoadingForecast] = useState(false);
  const [error, setError] = useState("");
  const hasPortfolios = portfolios.length > 0;

  useEffect(() => {
    if (!localStorage.getItem("staff_id")) {
      navigate("/login");
      return;
    }

    setLoadingPortfolios(true);
    api.get("portfolio/")
      .then((res) => {
        const userPortfolios = res.data || [];
        setPortfolios(userPortfolios);
        if (!userPortfolios.length) {
          setError("Create a portfolio first to use time series forecasting.");
        } else {
          setError("");
        }
      })
      .catch(() => {
        setError("Unable to load portfolios.");
      })
      .finally(() => setLoadingPortfolios(false));
  }, [navigate]);

  useEffect(() => {
    if (!selectedPortfolioId) {
      setStocks([]);
      setSelectedStockId("");
      return;
    }

    setLoadingStocks(true);
    setSelectedStockId("");
    setForecastData(null);
    api.get(`portfolio/${selectedPortfolioId}/`)
      .then((res) => {
        setStocks(res.data?.stocks || []);
        setError("");
      })
      .catch(() => {
        setStocks([]);
        setError("Unable to load stocks for this portfolio.");
      })
      .finally(() => setLoadingStocks(false));
  }, [selectedPortfolioId]);

  const loadForecast = (forecastType, modelType = selectedModelType) => {
    if (!selectedStockId) return;

    setSelectedForecastType(forecastType);
    setSelectedModelType(modelType);
    setLoadingForecast(true);
    setForecastData(null);
    setError("");

    api.get(
      `timeseries/predict/?stock_id=${selectedStockId}&forecast_type=${forecastType}&model_type=${modelType}`
    )
      .then((res) => {
        setForecastData(res.data);
      })
      .catch((err) => {
        const message = err?.response?.data?.error || "Unable to generate forecast.";
        setError(message);
      })
      .finally(() => setLoadingForecast(false));
  };

  const chartData = useMemo(() => {
    if (!forecastData?.graph) return null;

    const fullHistoryDates = forecastData.graph.history_dates || [];
    const fullHistoryPrices = forecastData.graph.history_prices || [];
    const futureDates = forecastData.graph.forecast_dates || [];
    const futurePrices = forecastData.graph.forecast_prices || [];
    const fittedDates = forecastData.graph.fitted_dates || [];
    const fittedPrices = forecastData.graph.fitted_prices || [];
    const lowerBand = forecastData.prediction?.confidence_interval_lower || [];
    const upperBand = forecastData.prediction?.confidence_interval_upper || [];

    const historySliceSize = historyRange === "3m" ? 90 : fullHistoryPrices.length;
    const historyDates = fullHistoryDates.slice(-historySliceSize);
    const historyPrices = fullHistoryPrices.slice(-historySliceSize);

    const lastHistory = historyPrices.length ? historyPrices[historyPrices.length - 1] : null;

    const labels = [...historyDates, ...futureDates];
    const historySeries = [...historyPrices, ...Array(futurePrices.length).fill(null)];
    const forecastSeries = [
      ...Array(Math.max(0, historyPrices.length - 1)).fill(null),
      lastHistory,
      ...futurePrices,
    ];
    const lowerSeries = [...Array(historyPrices.length).fill(null), ...lowerBand];
    const upperSeries = [...Array(historyPrices.length).fill(null), ...upperBand];

    const fitMap = new Map();
    for (let i = 0; i < fittedDates.length; i += 1) {
      fitMap.set(fittedDates[i], fittedPrices[i]);
    }
    const fittedSeries = labels.map((date) => (fitMap.has(date) ? fitMap.get(date) : null));

    const modelLabel = (forecastData.model_type || selectedModelType || "arima").toUpperCase();

    return {
      labels,
      datasets: [
        {
          label: historyRange === "3m" ? "Historical Close (Last 3 Months)" : "Historical Close",
          data: historySeries,
          borderColor: "#1d4ed8",
          backgroundColor: "rgba(29, 78, 216, 0.14)",
          borderWidth: 2.2,
          tension: 0.22,
          pointRadius: 0,
          fill: false,
        },
        {
          label: `${modelLabel} Forecast`,
          data: forecastSeries,
          borderColor: "#be123c",
          backgroundColor: "rgba(190, 18, 60, 0.16)",
          borderDash: [8, 5],
          borderWidth: 2.4,
          tension: 0.22,
          pointRadius: 2.6,
          fill: false,
        },
        {
          label: `${modelLabel} Fitted (Predicted vs Actual)`,
          data: fittedSeries,
          borderColor: "#0f766e",
          backgroundColor: "rgba(15, 118, 110, 0.14)",
          borderDash: [4, 4],
          borderWidth: 1.8,
          tension: 0.2,
          pointRadius: 0,
          fill: false,
        },
        {
          label: "95% CI Lower",
          data: lowerSeries,
          borderColor: "#f59e0b",
          backgroundColor: "rgba(245, 158, 11, 0.09)",
          borderWidth: 1.1,
          tension: 0.2,
          pointRadius: 0,
          fill: false,
        },
        {
          label: "95% CI Upper",
          data: upperSeries,
          borderColor: "#16a34a",
          backgroundColor: "rgba(22, 163, 74, 0.12)",
          borderWidth: 1.1,
          tension: 0.2,
          pointRadius: 0,
          fill: "-1",
        },
      ],
    };
  }, [forecastData, historyRange, selectedModelType]);

  const chartOptions = useMemo(() => {
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false,
      },
      plugins: {
        legend: {
          position: "top",
        },
      },
      scales: {
        y: {
          ticks: {
            callback: (value) => Number(value).toLocaleString(),
          },
        },
      },
    };
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("staff_id");
    localStorage.removeItem("staff_name");
    navigate("/login");
  };

  const modelOrder = forecastData?.prediction?.model_order;
  const trainingMeta = modelOrder?.training;

  return (
    <div className="ts-page">
      <div className="ts-shell">
        <div className="ts-navbar">
          <div className="ts-nav-left">
            <div className="ts-app-name">Check.Stock</div>
            <button className="ts-nav-link" onClick={() => navigate("/dashboard")}>Dashboard</button>
            <button className="ts-nav-link" onClick={() => navigate("/metals")}>Gold-Silver</button>
            <button className="ts-nav-link active" onClick={() => navigate("/timeseries")}>Time Series</button>
          </div>
          <div className="ts-nav-right">
            <div className="ts-admin-pill">Admin: {staffName}</div>
            <button className="ts-logout-btn" onClick={handleLogout}>Logout</button>
          </div>
        </div>

        <div className="ts-card">
          <h1>{selectedModelType.toUpperCase()} Time Series Forecast</h1>
          <p>Select portfolio -&gt; stock -&gt; model -&gt; forecast horizon (ts_1 or ts_7).</p>

          <div className="ts-controls-grid">
            <div>
              <label>Portfolio</label>
              <select
                value={selectedPortfolioId}
                onChange={(e) => setSelectedPortfolioId(e.target.value)}
                disabled={loadingPortfolios || !hasPortfolios}
              >
                <option value="">Select Portfolio</option>
                {portfolios.map((portfolio) => (
                  <option key={portfolio.id} value={portfolio.id}>
                    {portfolio.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label>Stock</label>
              <select
                value={selectedStockId}
                onChange={(e) => {
                  setSelectedStockId(e.target.value);
                  setForecastData(null);
                }}
                disabled={!selectedPortfolioId || loadingStocks}
              >
                <option value="">Select Stock</option>
                {stocks.map((stock) => (
                  <option key={stock.id} value={stock.id}>
                    {stock.ticker} - {stock.company_name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="ts-button-row">
            <button
              className={`ts-type-btn ${selectedModelType === "arima" ? "active" : ""}`}
              disabled={!selectedStockId || loadingForecast || !hasPortfolios}
              onClick={() => loadForecast(selectedForecastType, "arima")}
            >
              ARIMA
            </button>
            <button
              className={`ts-type-btn ${selectedModelType === "rnn" ? "active" : ""}`}
              disabled={!selectedStockId || loadingForecast || !hasPortfolios}
              onClick={() => loadForecast(selectedForecastType, "rnn")}
            >
              RNN
            </button>
          </div>

          <div className="ts-button-row">
            <button
              className={`ts-type-btn ${selectedForecastType === "ts_1" ? "active" : ""}`}
              disabled={!selectedStockId || loadingForecast || !hasPortfolios}
              onClick={() => loadForecast("ts_1", selectedModelType)}
            >
              TS 1 Day
            </button>
            <button
              className={`ts-type-btn ${selectedForecastType === "ts_7" ? "active" : ""}`}
              disabled={!selectedStockId || loadingForecast || !hasPortfolios}
              onClick={() => loadForecast("ts_7", selectedModelType)}
            >
              TS 7 Days
            </button>
          </div>

          {loadingForecast && <p className="ts-state">Generating {selectedModelType.toUpperCase()} forecast...</p>}
          {error && <p className="ts-error">{error}</p>}
        </div>

        {forecastData?.stock && (
          <div className="ts-card">
            <h3>Stock Snapshot</h3>
            <div className="ts-info-grid">
              <div><span>Ticker</span><strong>{forecastData.stock.ticker}</strong></div>
              <div><span>Company</span><strong>{forecastData.stock.company_name}</strong></div>
              <div><span>Current Price</span><strong>Rs {Number(forecastData.stock.current_price || 0).toFixed(2)}</strong></div>
              <div><span>PE Ratio</span><strong>{forecastData.stock.pe_ratio ? Number(forecastData.stock.pe_ratio).toFixed(2) : "N/A"}</strong></div>
              <div><span>52W High</span><strong>{forecastData.stock.high_52w ?? "N/A"}</strong></div>
              <div><span>52W Low</span><strong>{forecastData.stock.low_52w ?? "N/A"}</strong></div>
              <div><span>Forecast Type</span><strong>{forecastData.forecast_type.toUpperCase()}</strong></div>
              <div><span>Model Type</span><strong>{(forecastData.model_type || selectedModelType).toUpperCase()}</strong></div>
              <div><span>Model</span><strong>{forecastData.prediction.model_name}</strong></div>
              <div><span>Framework</span><strong>{modelOrder?.framework || "N/A"}</strong></div>
              <div><span>Window Size</span><strong>{modelOrder?.window_size ?? "N/A"}</strong></div>
              <div><span>Layers</span><strong>{Array.isArray(modelOrder?.layers) ? modelOrder.layers.join(" -> ") : "N/A"}</strong></div>
              <div><span>Training Epochs</span><strong>{trainingMeta?.epochs_trained ?? "N/A"}</strong></div>
              <div><span>Best Validation Loss</span><strong>{trainingMeta?.best_val_loss != null ? Number(trainingMeta.best_val_loss).toFixed(5) : "N/A"}</strong></div>
              <div><span>Predicted Price</span><strong>Rs {Number(forecastData.prediction.predicted_price || 0).toFixed(2)}</strong></div>
              <div><span>Predicted Date</span><strong>{forecastData.prediction.predicted_for_date}</strong></div>
            </div>
          </div>
        )}

        {chartData && (
          <div className="ts-card">
            <div className="ts-chart-header">
              <h3>Dynamic Forecast Graph</h3>
              <div className="ts-button-row compact">
                <button
                  className={`ts-type-btn ${historyRange === "3m" ? "active" : ""}`}
                  onClick={() => setHistoryRange("3m")}
                >
                  Last 3 Months
                </button>
                <button
                  className={`ts-type-btn ${historyRange === "full" ? "active" : ""}`}
                  onClick={() => setHistoryRange("full")}
                >
                  Full History
                </button>
              </div>
            </div>
            <div className="ts-chart-box">
              <Line data={chartData} options={chartOptions} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default TimeSeriesForecast;

import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Bar, Line } from "react-chartjs-2";
import "chart.js/auto";
import api from "../services/api";
import "./StockDetail.css";

function StockDetail() {
  const { stockId } = useParams();
  const navigate = useNavigate();
  const staffName = localStorage.getItem("staff_name") || "Admin";
  const [stock, setStock] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!stockId) return;
    setLoading(true);

    api.get(`eda/stock/${stockId}/`)
      .then((res) => {
        setStock(res.data);
        setLoading(false);
      })
      .catch((err) => {
        console.log(err);
        setError("Failed to load stock data.");
        setLoading(false);
      });
  }, [stockId]);

  const scoreLabel = useMemo(() => {
    if (!stock) return "Neutral";
    const score = stock.opportunity_score;
    if (score >= 75) return "High Opportunity";
    if (score >= 55) return "Moderate Opportunity";
    if (score >= 40) return "Watch Zone";
    return "Low Opportunity";
  }, [stock]);

  const trendInfo = useMemo(() => {
    if (!stock?.price_history?.length) return { value: 0, positive: true };
    const start = Number(stock.price_history[0]) || 0;
    const end = Number(stock.price_history[stock.price_history.length - 1]) || 0;
    if (!start) return { value: 0, positive: true };
    const pct = ((end - start) / start) * 100;
    return { value: pct, positive: pct >= 0 };
  }, [stock]);

  if (loading) return <h2 className="state-msg">Loading...</h2>;
  if (error) return <h2 className="state-msg">{error}</h2>;
  if (!stock) return <h2 className="state-msg">No data available.</h2>;

  const currentPrice = Number(stock.current_price || 0);
  const high52 = Number(stock.high_52w || 0);
  const low52 = Number(stock.low_52w || 0);
  const rangePercent = high52 > low52 ? ((currentPrice - low52) / (high52 - low52)) * 100 : 0;

  const priceChartData = {
    labels: stock.dates,
    datasets: [
      {
        label: "1Y Price",
        data: stock.price_history,
        borderColor: "#0f766e",
        backgroundColor: "rgba(15, 118, 110, 0.15)",
        borderWidth: 2.5,
        tension: 0.28,
        fill: true,
        pointRadius: 0,
      },
    ],
  };

  const peChartData =
    stock.pe_history && stock.pe_history.length > 0
      ? {
          labels: stock.pe_quarters,
          datasets: [
            {
              label: "Quarterly PE",
              data: stock.pe_history,
              backgroundColor: ["#1d4ed8", "#2563eb", "#3b82f6", "#60a5fa"],
              borderRadius: 10,
            },
          ],
        }
      : null;

  const handleLogout = () => {
    localStorage.removeItem("staff_id");
    localStorage.removeItem("staff_name");
    navigate("/login");
  };

  return (
    <div className="stock-page">
      <div className="stock-shell">
        <div className="stock-navbar">
          <div className="stock-nav-left">
            <div className="stock-app-name">Check.Stock</div>
            <button className="stock-nav-link" onClick={() => navigate("/dashboard")}>Dashboard</button>
            <button className="stock-nav-link" onClick={() => navigate("/metals")}>Gold-Silver</button>
          </div>
          <div className="stock-nav-right">
            <div className="stock-admin-pill">Admin: {staffName}</div>
            <button className="stock-logout-btn" onClick={handleLogout}>
              Logout
            </button>
          </div>
        </div>

        <div className="stock-topbar">
          <button className="back-btn" onClick={() => navigate(-1)}>
            Back
          </button>
        </div>

        <div className="hero-card">
          <div>
            <h1>{stock.company_name || stock.ticker}</h1>
            <p className="ticker-line">{stock.ticker}</p>
          </div>
          <div className="hero-right">
            <div className="price-large">Rs {currentPrice.toFixed(2)}</div>
            <div className={`trend-pill ${trendInfo.positive ? "up" : "down"}`}>
              {trendInfo.positive ? "+" : ""}
              {trendInfo.value.toFixed(2)}% (1Y)
            </div>
          </div>
        </div>

        <div className="score-card">
          <div>
            <h3>Opportunity Score</h3>
            <p className="score-caption">{scoreLabel}</p>
          </div>
          <div className="score-big">{stock.opportunity_score}/100</div>
          <div className="score-track">
            <div className="score-fill" style={{ width: `${stock.opportunity_score}%` }} />
          </div>
        </div>

        <div className="metrics-grid">
          <div className="metric-card">
            <span>PE Ratio</span>
            <strong>{stock.pe_ratio ? Number(stock.pe_ratio).toFixed(2) : "N/A"}</strong>
          </div>
          <div className="metric-card">
            <span>Market Cap</span>
            <strong>{stock.market_cap ? `Rs ${(stock.market_cap / 1e9).toFixed(2)} B` : "N/A"}</strong>
          </div>
          <div className="metric-card">
            <span>% From 52W Low</span>
            <strong>{Number(stock.percent_from_low || 0).toFixed(2)}%</strong>
          </div>
          <div className="metric-card">
            <span>% From 52W High</span>
            <strong>{Number(stock.percent_from_high || 0).toFixed(2)}%</strong>
          </div>
        </div>

        <div className="range-card">
          <div className="range-head">
            <h3>52 Week Range</h3>
            <span>Rs {low52.toFixed(2)} - Rs {high52.toFixed(2)}</span>
          </div>
          <div className="range-track">
            <div className="range-fill" style={{ width: `${Math.max(0, Math.min(100, rangePercent))}%` }} />
          </div>
        </div>

        <div className="chart-card">
          <h3>1 Year Price Movement</h3>
          <Line data={priceChartData} />
        </div>

        {peChartData && (
          <div className="chart-card">
            <h3>Quarterly PE Trend</h3>
            <Bar data={peChartData} />
          </div>
        )}
      </div>
    </div>
  );
}

export default StockDetail;

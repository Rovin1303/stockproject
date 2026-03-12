import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Line, Scatter } from "react-chartjs-2";
import "chart.js/auto";
import api from "../services/api";
import AppNavbar from "../components/AppNavbar";
import "./MetalsCorrelationPage.css";

function MetalsCorrelationPage() {
  const navigate = useNavigate();
  const staffName = localStorage.getItem("staff_name") || "Admin";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!localStorage.getItem("staff_id")) {
      navigate("/login");
      return;
    }

    setLoading(true);
    api.get("eda/metals/correlation/")
      .then((res) => {
        setData(res.data);
        setError("");
      })
      .catch((err) => {
        const message = !err?.response
          ? "Cannot connect to backend server. Ensure Django API is running on port 8000."
          : (err?.response?.data?.error || "Unable to load gold-silver correlation data.");
        setError(message);
      })
      .finally(() => setLoading(false));
  }, [navigate]);

  const handleLogout = () => {
    localStorage.removeItem("staff_id");
    localStorage.removeItem("staff_name");
    navigate("/login");
  };

  if (loading) return <div className="metals-state">Loading...</div>;
  if (error) return <div className="metals-state">{error}</div>;
  if (!data) return <div className="metals-state">No data available.</div>;

  const scatterPoints = data.series.price_scatter_silver.map((silver, idx) => ({
    x: silver,
    y: data.series.price_scatter_gold[idx],
  }));
  const regLine = data.series.price_scatter_silver.map((silver, idx) => ({
    x: silver,
    y: data.series.price_fit_gold[idx],
  })).sort((a, b) => a.x - b.x);

  const priceLineData = {
    labels: data.series.dates,
    datasets: [
      {
        label: "Gold Close",
        data: data.series.gold_close,
        borderColor: "#d97706",
        backgroundColor: "rgba(217, 119, 6, 0.1)",
        yAxisID: "yGold",
        pointRadius: 0,
        borderWidth: 2,
        tension: 0.25,
      },
      {
        label: "Silver Close",
        data: data.series.silver_close,
        borderColor: "#475569",
        backgroundColor: "rgba(71, 85, 105, 0.1)",
        yAxisID: "ySilver",
        pointRadius: 0,
        borderWidth: 2,
        tension: 0.25,
      },
    ],
  };
  const priceLineOptions = {
    responsive: true,
    interaction: { mode: "index", intersect: false },
    scales: {
      yGold: {
        type: "linear",
        position: "left",
        title: { display: true, text: "Gold Close" },
      },
      ySilver: {
        type: "linear",
        position: "right",
        grid: { drawOnChartArea: false },
        title: { display: true, text: "Silver Close" },
      },
    },
  };

  const scatterData = {
    datasets: [
      {
        label: "Actual Prices",
        data: scatterPoints,
        backgroundColor: "rgba(37, 99, 235, 0.45)",
        pointRadius: 3,
      },
      {
        label: "Linear Fit",
        data: regLine,
        showLine: true,
        borderColor: "#ef4444",
        backgroundColor: "#ef4444",
        pointRadius: 0,
        borderWidth: 2,
      },
    ],
  };

  return (
    <div className="metals-page">
      <div className="metals-shell">
        <AppNavbar staffName={staffName} onLogout={handleLogout} />

        <div className="metals-card">
          <h1>Gold-Silver Linear Regression Correlation</h1>
          <p>Period: {data.period} | Interval: {data.interval} | Rows: {data.rows_used}</p>
          <p><strong>Return Correlation:</strong> {data.correlation_returns}</p>
          <p><strong>Price Correlation:</strong> {data.correlation_prices}</p>
          <p>
            <strong>Regression:</strong>{" "}
            y = {data.price_regression.intercept} + {data.price_regression.slope}x
            {" "} (R2 {data.price_regression.r2})
          </p>
        </div>

        <div className="metals-chart-card">
          <h3>Gold vs Silver Price (Recent Window)</h3>
          <Line data={priceLineData} options={priceLineOptions} />
        </div>

        <div className="metals-chart-card">
          <h3>Gold vs Silver Correlation Scatter (Price)</h3>
          <Scatter data={scatterData} />
        </div>
      </div>
    </div>
  );
}

export default MetalsCorrelationPage;

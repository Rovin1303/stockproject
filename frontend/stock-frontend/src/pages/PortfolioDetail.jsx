import { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Bar, Scatter } from "react-chartjs-2";
import "chart.js/auto";
import api from "../services/api";
import "./PortfolioDetail.css";

function PortfolioDetail() {
  const { portfolioId } = useParams();
  const navigate = useNavigate();
  const staffName = localStorage.getItem("staff_name") || "Admin";

  const [portfolio, setPortfolio] = useState(null);
  const [stocks, setStocks] = useState([]);
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [selectedTicker, setSelectedTicker] = useState("");
  const [adding, setAdding] = useState(false);
  const [predictions, setPredictions] = useState({});
  const [logisticRows, setLogisticRows] = useState([]);
  const [clusterRows, setClusterRows] = useState([]);
  const [clusterCounts, setClusterCounts] = useState({ "High Risk": 0, "Medium Risk": 0, "Low Risk": 0 });
  const [activeGraph, setActiveGraph] = useState("");
  const [refreshingPrices, setRefreshingPrices] = useState(false);

  const loadPortfolio = useCallback(async () => {
    const res = await api.get(`portfolio/${portfolioId}/`);
    setPortfolio(res.data);
    setStocks(res.data.stocks || []);
    return res.data;
  }, [portfolioId]);

  useEffect(() => {
    if (!localStorage.getItem("staff_id")) {
      navigate("/login");
      return;
    }
    loadPortfolio().catch((err) => console.log(err));
  }, [loadPortfolio, navigate]);

  useEffect(() => {
    if (query.trim().length < 2) {
      setSuggestions([]);
      return;
    }

    const timeoutId = setTimeout(() => {
      api.get(`eda/search/?q=${encodeURIComponent(query.trim())}`)
        .then((res) => setSuggestions(res.data || []))
        .catch(() => setSuggestions([]));
    }, 250);

    return () => clearTimeout(timeoutId);
  }, [query]);

  const handleAddStock = async () => {
    const ticker = (selectedTicker || query).trim().toUpperCase();
    if (!ticker) return;

    setAdding(true);
    try {
      await api.post("stocks/", {
        ticker,
        portfolio: Number(portfolioId),
      });
      setQuery("");
      setSelectedTicker("");
      setSuggestions([]);
      loadPortfolio();
    } catch (err) {
      console.log(err);
      alert("Unable to add stock. Check ticker or duplicate in this portfolio.");
    } finally {
      setAdding(false);
    }
  };

  const handleRemoveStock = async (stockId) => {
    try {
      await api.delete(`stocks/${stockId}/`);
      setStocks((prev) => prev.filter((stock) => stock.id !== stockId));
    } catch (err) {
      console.log(err);
      alert("Unable to remove stock.");
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("staff_id");
    localStorage.removeItem("staff_name");
    navigate("/login");
  };

  const loadClusters = useCallback(async () => {
    const res = await api.get(`portfolio/${portfolioId}/clusters/`);
    setClusterRows(res.data?.stocks || []);
    setClusterCounts(res.data?.cluster_counts || { "High Risk": 0, "Medium Risk": 0, "Low Risk": 0 });
  }, [portfolioId]);

  const handleRefreshPrices = async () => {
    setRefreshingPrices(true);
    try {
      await loadPortfolio();
      await loadClusters();
    } catch (err) {
      console.log(err);
      alert("Unable to refresh stock prices right now.");
    } finally {
      setRefreshingPrices(false);
    }
  };

  useEffect(() => {
    if (!stocks.length) {
      setPredictions({});
      return;
    }

    let active = true;
    const loadPredictions = async () => {
      try {
        const res = await api.get(`portfolio/${portfolioId}/predictions/`);
        const mapped = {};
        (res.data || []).forEach((item) => {
          mapped[item.stock_id] = {
            date_tom: item.date_tom,
            price_predict: item.price_predict,
          };
        });
        if (active) setPredictions(mapped);
      } catch (err) {
        console.log(err);
        if (active) setPredictions({});
      }
    };

    loadPredictions();
    return () => {
      active = false;
    };
  }, [stocks, portfolioId]);

  useEffect(() => {
    if (!stocks.length) {
      setClusterRows([]);
      setClusterCounts({ "High Risk": 0, "Medium Risk": 0, "Low Risk": 0 });
      return;
    }

    let active = true;
    const loadClustersForEffect = async () => {
      try {
        const res = await api.get(`portfolio/${portfolioId}/clusters/`);
        if (!active) return;
        setClusterRows(res.data?.stocks || []);
        setClusterCounts(res.data?.cluster_counts || { "High Risk": 0, "Medium Risk": 0, "Low Risk": 0 });
      } catch (err) {
        console.log(err);
        if (!active) return;
        setClusterRows([]);
        setClusterCounts({ "High Risk": 0, "Medium Risk": 0, "Low Risk": 0 });
      }
    };

    loadClustersForEffect();
    return () => {
      active = false;
    };
  }, [stocks, portfolioId]);

  useEffect(() => {
    if (!stocks.length) {
      setLogisticRows([]);
      return;
    }

    let active = true;
    const loadLogistic = async () => {
      try {
        const res = await api.get(`portfolio/${portfolioId}/logistic/`);
        if (active) setLogisticRows(res.data || []);
      } catch (err) {
        console.log(err);
        if (active) setLogisticRows([]);
      }
    };

    loadLogistic();
    return () => {
      active = false;
    };
  }, [stocks, portfolioId]);

  const peChartData = {
    labels: stocks.map((stock) => stock.ticker),
    datasets: [
      {
        label: "PE Ratio",
        data: stocks.map((stock) => {
          const pe = Number(stock.pe_ratio);
          return Number.isFinite(pe) && pe > 0 ? pe : 0;
        }),
        backgroundColor: "#667eea",
        borderRadius: 6,
      },
    ],
  };
  const hasAnyPositivePe = stocks.some((stock) => Number(stock.pe_ratio) > 0);
  const logisticMap = {};
  logisticRows.forEach((row) => {
    logisticMap[row.stock_id] = row;
  });

  const clusterChartData = {
    datasets: [
      {
        label: "High Risk",
        data: clusterRows
          .filter((row) => row.cluster === "High Risk")
          .map((row) => ({
            x: Number(row.vol_21 || 0),
            y: Number(row.max_drawdown_126 || 0),
            ticker: row.ticker,
          })),
        backgroundColor: "#16a34a",
        pointRadius: 6,
      },
      {
        label: "Medium Risk",
        data: clusterRows
          .filter((row) => row.cluster === "Medium Risk")
          .map((row) => ({
            x: Number(row.vol_21 || 0),
            y: Number(row.max_drawdown_126 || 0),
            ticker: row.ticker,
          })),
        backgroundColor: "#f59e0b",
        pointRadius: 6,
      },
      {
        label: "Low Risk",
        data: clusterRows
          .filter((row) => row.cluster === "Low Risk")
          .map((row) => ({
            x: Number(row.vol_21 || 0),
            y: Number(row.max_drawdown_126 || 0),
            ticker: row.ticker,
          })),
        backgroundColor: "#ef4444",
        pointRadius: 6,
      },
    ],
  };
  const clusterChartOptions = {
    responsive: true,
    plugins: {
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const ticker = ctx.raw?.ticker || "";
            const x = Number(ctx.raw?.x || 0).toFixed(2);
            const y = Number(ctx.raw?.y || 0).toFixed(2);
            return `${ticker}: Vol21 ${x}% | MaxDD126 ${y}%`;
          },
        },
      },
    },
    scales: {
      x: {
        title: { display: true, text: "Volatility 21D (%)" },
      },
      y: {
        title: { display: true, text: "Max Drawdown 126D (%)" },
      },
    },
  };

  const riskClassName = (risk) => {
    if (risk === "High Risk") return "risk-high";
    if (risk === "Medium Risk") return "risk-medium";
    if (risk === "Low Risk") return "risk-low";
    return "";
  };
  const getDiscountPctForRow = (row) => {
    const apiValue = Number(row.discount_pct);
    if (Number.isFinite(apiValue)) return apiValue;

    const linkedStock = stocks.find((s) => s.id === row.stock_id || s.ticker === row.ticker);
    if (!linkedStock) return null;

    const high = Number(linkedStock.high_52w || 0);
    const current = Number(linkedStock.current_price || 0);
    if (high <= 0) return null;
    return ((high - current) / high) * 100;
  };
  const riskOrder = {
    "Low Risk": 0,
    "Medium Risk": 1,
    "High Risk": 2,
  };
  const sortedClusterRows = [...clusterRows].sort((a, b) => {
    const rankA = riskOrder[a.cluster] ?? 99;
    const rankB = riskOrder[b.cluster] ?? 99;
    if (rankA !== rankB) return rankA - rankB;
    return String(a.ticker || "").localeCompare(String(b.ticker || ""));
  });

  if (!portfolio) return <div>Loading...</div>;

  return (
    <div className="portfolio-container">
      <div className="page-navbar">
        <div className="nav-left">
          <div className="app-name">Check.Stock</div>
          <button className="nav-link" onClick={() => navigate("/dashboard")}>Dashboard</button>
          <button className="nav-link" onClick={() => navigate("/metals")}>Gold-Silver</button>
          <button className="nav-link" onClick={() => navigate("/timeseries")}>Time Series</button>
        </div>
        <div className="nav-right">
          <div className="admin-pill">Admin: {staffName}</div>
          <button className="logout-btn" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </div>

      <button className="back-btn" onClick={() => navigate("/dashboard")}>
        Back to Dashboard
      </button>

      <h1 className="portfolio-title">{portfolio.name}</h1>
      <p className="portfolio-description">{portfolio.description || "-"}</p>

      <div className="add-stock-card">
        <h3>Add Stock</h3>
        <div className="add-stock-row">
          <input
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedTicker("");
            }}
            placeholder="Search company or ticker (e.g. mahindra)"
          />
          <button onClick={handleAddStock} disabled={adding}>
            {adding ? "Adding..." : "Add Stock"}
          </button>
        </div>

        {suggestions.length > 0 && (
          <div className="suggestions-list">
            {suggestions.map((item) => (
              <button
                key={`${item.ticker}-${item.exchange || ""}`}
                className="suggestion-item"
                onClick={() => {
                  setSelectedTicker(item.ticker);
                  setQuery(`${item.name} (${item.ticker})`);
                  setSuggestions([]);
                }}
              >
                <span>{item.name}</span>
                <span>{item.ticker}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="graph-toggle-card">
        <button
          className={`graph-toggle-btn ${activeGraph === "pe" ? "active" : ""}`}
          onClick={() => setActiveGraph(activeGraph === "pe" ? "" : "pe")}
        >
          PE Graph
        </button>
        <button
          className={`graph-toggle-btn ${activeGraph === "kmeans" ? "active" : ""}`}
          onClick={() => setActiveGraph(activeGraph === "kmeans" ? "" : "kmeans")}
        >
          KMeans Clustering Graph
        </button>
        <button
          className={`graph-toggle-btn ${activeGraph === "kmeans_table" ? "active" : ""}`}
          onClick={() => setActiveGraph(activeGraph === "kmeans_table" ? "" : "kmeans_table")}
        >
          KMeans Table
        </button>
      </div>

      {activeGraph === "kmeans" && (
        <div className="chart-card">
          <h3>Stock Risk Clustering (Vol21 / MaxDrawdown126)</h3>
          {clusterRows.length === 0 ? (
            <p className="chart-note">Not enough stock history to build clusters.</p>
          ) : (
            <>
              <p className="chart-note">
                High Risk: {clusterCounts["High Risk"]} | Medium Risk: {clusterCounts["Medium Risk"]} | Low Risk: {clusterCounts["Low Risk"]}
              </p>
              <Scatter data={clusterChartData} options={clusterChartOptions} />
            </>
          )}
        </div>
      )}

      {activeGraph === "kmeans_table" && (
        <div className="table-card">
          <h3>KMeans Clustering Dataframe</h3>
          <div className="table-wrap">
            <table className="stocks-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Company</th>
                  <th>Vol21 %</th>
                  <th>MaxDrawdown126 %</th>
                  <th>Discount %</th>
                  <th>Risk Group</th>
                </tr>
              </thead>
              <tbody>
                {clusterRows.length === 0 && (
                  <tr>
                    <td colSpan="6" className="empty-row">No clustering data available.</td>
                  </tr>
                )}
                {sortedClusterRows.map((row) => (
                  <tr key={`cluster-row-${row.stock_id}`}>
                    <td>{row.ticker}</td>
                    <td>{row.company_name}</td>
                    <td>{Number(row.vol_21 || 0).toFixed(2)}%</td>
                    <td>{Number(row.max_drawdown_126 || 0).toFixed(2)}%</td>
                    <td>
                      {(() => {
                        const discountPct = getDiscountPctForRow(row);
                        return Number.isFinite(discountPct) ? `${discountPct.toFixed(2)}%` : "N/A";
                      })()}
                    </td>
                    <td>
                      <span className={riskClassName(row.cluster)}>
                        {row.cluster || "N/A"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeGraph === "pe" && stocks.length > 0 && (
        <div className="chart-card">
          <h3>PE Ratio Comparison</h3>
          {!hasAnyPositivePe && (
            <p className="chart-note">
              PE ratio is unavailable for current symbols (common for crypto); bars are shown as 0.
            </p>
          )}
          <Bar data={peChartData} />
        </div>
      )}

      <div className="table-card">
        <div className="table-card-header">
          <h3>Portfolio Stocks (Unified)</h3>
          <button className="refresh-btn" onClick={handleRefreshPrices} disabled={refreshingPrices}>
            {refreshingPrices ? "Refreshing..." : "Refresh Prices"}
          </button>
        </div>
        <div className="table-wrap">
          <table className="stocks-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Company</th>
                <th>Current Price</th>
                <th>Min Price</th>
                <th>Max Price</th>
                <th>Discount %</th>
                <th>PE Ratio</th>
                <th>Price Predict</th>
                <th>Up/Down</th>
                <th>Pred Change %</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {stocks.length === 0 && (
                <tr>
                  <td colSpan="11" className="empty-row">No stocks added yet.</td>
                </tr>
              )}
              {stocks.map((stock) => (
                <tr key={stock.id}>
                  <td>{stock.ticker}</td>
                  <td>{stock.company_name}</td>
                  <td>Rs {Number(stock.current_price || 0).toFixed(2)}</td>
                  <td>{stock.low_52w !== null && stock.low_52w !== undefined ? `Rs ${Number(stock.low_52w).toFixed(2)}` : "N/A"}</td>
                  <td>{stock.high_52w !== null && stock.high_52w !== undefined ? `Rs ${Number(stock.high_52w).toFixed(2)}` : "N/A"}</td>
                  <td>
                    {Number(stock.high_52w || 0) > 0
                      ? `${(((Number(stock.high_52w) - Number(stock.current_price || 0)) / Number(stock.high_52w)) * 100).toFixed(2)}%`
                      : "N/A"}
                  </td>
                  <td>{stock.pe_ratio !== null && stock.pe_ratio !== undefined && Number(stock.pe_ratio) > 0 ? Number(stock.pe_ratio).toFixed(2) : "N/A"}</td>
                  <td>
                    {predictions[stock.id]?.price_predict !== null && predictions[stock.id]?.price_predict !== undefined
                      ? `Rs ${Number(predictions[stock.id].price_predict).toFixed(2)}`
                      : "Calculating"}
                  </td>
                  <td>
                    {logisticMap[stock.id]?.predicted_label ? (
                      <span className={logisticMap[stock.id].predicted_label === "UP" ? "dir-up" : "dir-down"}>
                        {logisticMap[stock.id].predicted_label}
                      </span>
                    ) : "Calculating"}
                  </td>
                  <td>
                    {predictions[stock.id]?.price_predict !== null && predictions[stock.id]?.price_predict !== undefined && Number(stock.current_price || 0) > 0
                      ? (() => {
                          const current = Number(stock.current_price || 0);
                          const pred = Number(predictions[stock.id].price_predict);
                          const pct = ((pred - current) / current) * 100;
                          const text = `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`;
                          return <span className={pct >= 0 ? "dir-up" : "dir-down"}>{text}</span>;
                        })()
                      : "Calculating"}
                  </td>
                  <td className="action-cell">
                    <button onClick={() => navigate(`/stock/${stock.id}`)}>View</button>
                    <button
                      className="remove-btn"
                      onClick={() => handleRemoveStock(stock.id)}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default PortfolioDetail;

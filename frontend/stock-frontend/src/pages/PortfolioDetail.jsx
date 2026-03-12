import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Bar, Scatter } from "react-chartjs-2";
import "chart.js/auto";
import api from "../services/api";
import AppNavbar from "../components/AppNavbar";
import "./PortfolioDetail.css";

const RISK_ORDER = {
  "Low Risk": 0,
  "Medium Risk": 1,
  "High Risk": 2,
};

function PortfolioDetail() {
  const { portfolioId } = useParams();
  const navigate = useNavigate();
  const staffName = localStorage.getItem("staff_name") || "Admin";

  const [portfolio, setPortfolio] = useState(null);
  const [portfolioLoading, setPortfolioLoading] = useState(true);
  const [portfolioError, setPortfolioError] = useState("");
  const [stocks, setStocks] = useState([]);
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [selectedTicker, setSelectedTicker] = useState("");
  const [adding, setAdding] = useState(false);
  const [predictions, setPredictions] = useState({});
  const [logisticRows, setLogisticRows] = useState([]);
  const [clusterRows, setClusterRows] = useState([]);
  const [clusterCounts, setClusterCounts] = useState({ "High Risk": 0, "Medium Risk": 0, "Low Risk": 0 });
  const [clusterLoading, setClusterLoading] = useState(false);
  const [clusterError, setClusterError] = useState("");
  const [activeGraph, setActiveGraph] = useState("");
  const [refreshingPrices, setRefreshingPrices] = useState(false);
  const [stockSort, setStockSort] = useState({ key: "company", direction: "asc" });
  const [clusterSort, setClusterSort] = useState({ key: "ticker", direction: "asc" });

  const stockSortOptions = [
    { key: "symbol", label: "Symbol" },
    { key: "company", label: "Company" },
    { key: "current_price", label: "Current Price" },
    { key: "min_price", label: "Min Price" },
    { key: "max_price", label: "Max Price" },
    { key: "discount_pct", label: "Discount %" },
    { key: "pe_ratio", label: "PE Ratio" },
    { key: "price_predict", label: "Price Predict" },
    { key: "up_down", label: "Up/Down" },
    { key: "pred_change", label: "Pred Change %" },
  ];

  const loadPortfolio = useCallback(async (options = {}) => {
    const {
      forceRefresh = false,
      showLoadingScreen = true,
      timeoutMs,
    } = options;
    if (showLoadingScreen) {
      setPortfolioLoading(true);
      setPortfolioError("");
    }
    try {
      const res = await api.get(`portfolio/${portfolioId}/`, {
        params: forceRefresh ? { force_refresh: 1 } : undefined,
        timeout: timeoutMs,
      });
      setPortfolio(res.data);
      setStocks(res.data.stocks || []);
      return res.data;
    } catch (err) {
      const message = err?.response?.data?.error || "Unable to load portfolio data right now.";
      setPortfolioError(message);
      throw err;
    } finally {
      if (showLoadingScreen) {
        setPortfolioLoading(false);
      }
    }
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

  const loadClusters = useCallback(async (options = {}) => {
    const { forceRefresh = false } = options;
    setClusterLoading(true);
    setClusterError("");
    try {
      const res = await api.get(`portfolio/${portfolioId}/clusters/`, {
        params: forceRefresh ? { force_refresh: 1 } : undefined,
      });
      setClusterRows(res.data?.stocks || []);
      setClusterCounts(res.data?.cluster_counts || { "High Risk": 0, "Medium Risk": 0, "Low Risk": 0 });
    } catch (err) {
      const message = err?.response?.data?.error || "Unable to load clustering right now.";
      setClusterError(message);
      setClusterRows([]);
      setClusterCounts({ "High Risk": 0, "Medium Risk": 0, "Low Risk": 0 });
    } finally {
      setClusterLoading(false);
    }
  }, [portfolioId]);

  const handleRefreshPrices = async () => {
    setRefreshingPrices(true);
    try {
      await loadPortfolio({
        forceRefresh: true,
        showLoadingScreen: false,
        timeoutMs: 90000,
      });
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
    const isClusterViewOpen = activeGraph === "kmeans" || activeGraph === "kmeans_table";
    if (!isClusterViewOpen) {
      return;
    }

    if (!stocks.length) {
      setClusterRows([]);
      setClusterCounts({ "High Risk": 0, "Medium Risk": 0, "Low Risk": 0 });
      setClusterError("");
      return;
    }

    let active = true;
    const loadClustersForEffect = async () => {
      await loadClusters();
      if (!active) return;
    };

    loadClustersForEffect();
    return () => {
      active = false;
    };
  }, [stocks, activeGraph, loadClusters]);

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
  const logisticMap = useMemo(() => {
    const mapped = {};
    logisticRows.forEach((row) => {
      mapped[row.stock_id] = row;
    });
    return mapped;
  }, [logisticRows]);

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
  const getDiscountPctForRow = useCallback((row) => {
    const apiValue = Number(row.discount_pct);
    if (Number.isFinite(apiValue)) return apiValue;

    const linkedStock = stocks.find((s) => s.id === row.stock_id || s.ticker === row.ticker);
    if (!linkedStock) return null;

    const high = Number(linkedStock.high_52w || 0);
    const current = Number(linkedStock.current_price || 0);
    if (high <= 0) return null;
    return ((high - current) / high) * 100;
  }, [stocks]);
  const compareValues = (left, right, direction) => {
    const order = direction === "asc" ? 1 : -1;
    const leftMissing = left === null || left === undefined || left === "";
    const rightMissing = right === null || right === undefined || right === "";

    if (leftMissing && rightMissing) return 0;
    if (leftMissing) return 1;
    if (rightMissing) return -1;

    if (typeof left === "string" || typeof right === "string") {
      return String(left).localeCompare(String(right)) * order;
    }

    return (Number(left) - Number(right)) * order;
  };

  const sortedStocks = useMemo(() => {
    const getStockSortValue = (stock, key) => {
      const currentPrice = Number(stock.current_price || 0);
      const maxPrice = Number(stock.high_52w || 0);
      const predictedPriceRaw = predictions[stock.id]?.price_predict;
      const predictedPrice = predictedPriceRaw !== null && predictedPriceRaw !== undefined
        ? Number(predictedPriceRaw)
        : null;
      const predChangePct = predictedPrice !== null && currentPrice > 0
        ? ((predictedPrice - currentPrice) / currentPrice) * 100
        : null;

      switch (key) {
        case "symbol":
          return stock.ticker || "";
        case "company":
          return stock.company_name || "";
        case "current_price":
          return currentPrice;
        case "min_price":
          return stock.low_52w !== null && stock.low_52w !== undefined ? Number(stock.low_52w) : null;
        case "max_price":
          return stock.high_52w !== null && stock.high_52w !== undefined ? Number(stock.high_52w) : null;
        case "discount_pct":
          return maxPrice > 0 ? ((maxPrice - currentPrice) / maxPrice) * 100 : null;
        case "pe_ratio": {
          const pe = Number(stock.pe_ratio);
          return Number.isFinite(pe) && pe > 0 ? pe : null;
        }
        case "price_predict":
          return predictedPrice;
        case "up_down": {
          const label = logisticMap[stock.id]?.predicted_label;
          if (label === "UP") return 1;
          if (label === "DOWN") return 0;
          return null;
        }
        case "pred_change":
          return predChangePct;
        default:
          return stock.company_name || "";
      }
    };

    return [...stocks].sort((left, right) => {
      const leftValue = getStockSortValue(left, stockSort.key);
      const rightValue = getStockSortValue(right, stockSort.key);
      return compareValues(leftValue, rightValue, stockSort.direction);
    });
  }, [stocks, stockSort, predictions, logisticMap]);

  const sortedClusterRows = useMemo(() => {
    const getClusterSortValue = (row, key) => {
      switch (key) {
        case "ticker":
          return row.ticker || "";
        case "company":
          return row.company_name || "";
        case "vol_21":
          return Number(row.vol_21 || 0);
        case "max_drawdown_126":
          return Number(row.max_drawdown_126 || 0);
        case "discount_pct":
          return getDiscountPctForRow(row);
        case "risk_group":
          return RISK_ORDER[row.cluster] ?? 99;
        default:
          return row.ticker || "";
      }
    };

    return [...clusterRows].sort((left, right) => {
      const leftValue = getClusterSortValue(left, clusterSort.key);
      const rightValue = getClusterSortValue(right, clusterSort.key);
      const primarySort = compareValues(leftValue, rightValue, clusterSort.direction);
      if (primarySort !== 0) {
        return primarySort;
      }
      return String(left.ticker || "").localeCompare(String(right.ticker || ""));
    });
  }, [clusterRows, clusterSort, getDiscountPctForRow]);

  const toggleClusterSort = (key) => {
    setClusterSort((prev) => {
      if (prev.key === key) {
        return {
          key,
          direction: prev.direction === "asc" ? "desc" : "asc",
        };
      }
      return { key, direction: "asc" };
    });
  };

  const sortLabel = (activeSort, key) => {
    if (activeSort.key !== key) return "Sort";
    return activeSort.direction === "asc" ? "Asc" : "Desc";
  };

  if (portfolioLoading) return <div>Loading...</div>;
  if (!portfolio) return <div>{portfolioError || "Portfolio not found."}</div>;

  return (
    <div className="portfolio-container">
      <AppNavbar staffName={staffName} onLogout={handleLogout} />

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
          {clusterLoading ? (
            <p className="chart-note">Loading clustering data...</p>
          ) : clusterError ? (
            <p className="chart-note">{clusterError}</p>
          ) : clusterRows.length === 0 ? (
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
                  <th>
                    <button className="sort-header-btn" onClick={() => toggleClusterSort("ticker")}>
                      Symbol <span>{sortLabel(clusterSort, "ticker")}</span>
                    </button>
                  </th>
                  <th>
                    <button className="sort-header-btn" onClick={() => toggleClusterSort("company")}>
                      Company <span>{sortLabel(clusterSort, "company")}</span>
                    </button>
                  </th>
                  <th>
                    <button className="sort-header-btn" onClick={() => toggleClusterSort("vol_21")}>
                      Vol21 % <span>{sortLabel(clusterSort, "vol_21")}</span>
                    </button>
                  </th>
                  <th>
                    <button className="sort-header-btn" onClick={() => toggleClusterSort("max_drawdown_126")}>
                      MaxDrawdown126 % <span>{sortLabel(clusterSort, "max_drawdown_126")}</span>
                    </button>
                  </th>
                  <th>
                    <button className="sort-header-btn" onClick={() => toggleClusterSort("discount_pct")}>
                      Discount % <span>{sortLabel(clusterSort, "discount_pct")}</span>
                    </button>
                  </th>
                  <th>
                    <button className="sort-header-btn" onClick={() => toggleClusterSort("risk_group")}>
                      Risk Group <span>{sortLabel(clusterSort, "risk_group")}</span>
                    </button>
                  </th>
                </tr>
              </thead>
              <tbody>
                {!clusterLoading && clusterRows.length === 0 && (
                  <tr>
                    <td colSpan="6" className="empty-row">No clustering data available.</td>
                  </tr>
                )}
                {clusterLoading && (
                  <tr>
                    <td colSpan="6" className="empty-row">Loading clustering data...</td>
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
          <h3>Portfolio Stocks</h3>
          <div className="table-controls">
            <div className="stock-sort-controls">
              <label htmlFor="stock-sort-key">Sort by</label>
              <select
                id="stock-sort-key"
                value={stockSort.key}
                onChange={(e) => setStockSort((prev) => ({ ...prev, key: e.target.value }))}
              >
                {stockSortOptions.map((option) => (
                  <option key={option.key} value={option.key}>{option.label}</option>
                ))}
              </select>
              <select
                id="stock-sort-direction"
                value={stockSort.direction}
                onChange={(e) => setStockSort((prev) => ({ ...prev, direction: e.target.value }))}
              >
                <option value="asc">Ascending</option>
                <option value="desc">Descending</option>
              </select>
            </div>
            <button className="refresh-btn" onClick={handleRefreshPrices} disabled={refreshingPrices}>
              {refreshingPrices ? "Refreshing..." : "Refresh Prices"}
            </button>
          </div>
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
              {sortedStocks.map((stock) => (
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

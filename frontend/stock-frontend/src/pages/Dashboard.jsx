import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";
import "./Dashboard.css";

function Dashboard() {
  const [portfolios, setPortfolios] = useState([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const navigate = useNavigate();
  const staffId = localStorage.getItem("staff_id");
  const staffName = localStorage.getItem("staff_name") || "Admin";

  const loadPortfolios = () => {
    api.get("portfolio/")
      .then((res) => setPortfolios(res.data))
      .catch((err) => console.log(err));
  };

  useEffect(() => {
    if (!staffId) {
      navigate("/login");
      return;
    }
    loadPortfolios();
  }, [staffId, navigate]);

  const handleCreatePortfolio = async (e) => {
    e.preventDefault();
    if (!name.trim() || !staffId) return;

    setCreating(true);
    try {
      const res = await api.post("portfolio/", {
        name: name.trim(),
        description: description.trim(),
        created_by: Number(staffId),
      });
      setName("");
      setDescription("");
      loadPortfolios();
      navigate(`/portfolio/${res.data.id}`);
    } catch (err) {
      console.log(err);
      alert("Unable to create portfolio.");
    } finally {
      setCreating(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("staff_id");
    localStorage.removeItem("staff_name");
    navigate("/login");
  };

  const handleRemovePortfolio = async (e, portfolioId, portfolioName) => {
    e.stopPropagation();
    const yes = window.confirm(`Delete portfolio "${portfolioName}"?`);
    if (!yes) return;

    setDeletingId(portfolioId);
    try {
      await api.delete(`portfolio/${portfolioId}/`);
      setPortfolios((prev) => prev.filter((p) => p.id !== portfolioId));
    } catch (err) {
      console.log(err);
      alert("Unable to delete portfolio.");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="dashboard-container">
      <div className="dashboard-navbar">
        <div className="nav-left">
          <div className="app-name">Check.Stock</div>
          <button className="nav-link-btn" onClick={() => navigate("/dashboard")}>Dashboard</button>
          <button className="nav-link-btn" onClick={() => navigate("/metals")}>Gold-Silver</button>
          <button className="nav-link-btn" onClick={() => navigate("/timeseries")}>Time Series</button>
        </div>
        <div className="nav-right">
          <div className="admin-pill">Admin: {staffName}</div>
          <button className="logout-btn" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </div>

      <h1 className="dashboard-title">My Portfolios</h1>

      <form className="portfolio-card create-card" onSubmit={handleCreatePortfolio}>
        <h2>Create Portfolio</h2>
        <div className="portfolio-info">
          <input
            type="text"
            placeholder="Portfolio name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <textarea
            placeholder="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
          />
        </div>
        <button className="create-btn" type="submit" disabled={creating}>
          {creating ? "Creating..." : "Create Portfolio"}
        </button>
      </form>

      <div className="portfolio-grid">
        {portfolios.map((portfolio) => (
          <div
            key={portfolio.id}
            className="portfolio-card"
            onClick={() => navigate(`/portfolio/${portfolio.id}`)}
          >
            <h2>{portfolio.name}</h2>

            <div className="portfolio-info">
              <p><strong>Description:</strong> {portfolio.description || "-"}</p>
              <p>
                <strong>Total Stocks:</strong>{" "}
                {portfolio.stocks?.length || portfolio.stock_count || 0}
              </p>
            </div>

            <div className="view-btn">View Portfolio -&gt;</div>
            <button
              className="remove-portfolio-btn"
              onClick={(e) => handleRemovePortfolio(e, portfolio.id, portfolio.name)}
              disabled={deletingId === portfolio.id}
            >
              {deletingId === portfolio.id ? "Removing..." : "Remove Portfolio"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default Dashboard;

import { useLocation, useNavigate } from "react-router-dom";
import "./AppNavbar.css";

const privateLinks = [
  { label: "Dashboard", path: "/dashboard" },
  { label: "Gold-Silver", path: "/metals" },
  { label: "Time Series", path: "/timeseries" },
];

function AppNavbar({ staffName = "Admin", onLogout = () => {} }) {
  const navigate = useNavigate();
  const location = useLocation();
  const links = privateLinks;

  const isLinkActive = (path) => {
    if (path === "/dashboard") {
      return (
        location.pathname === "/dashboard" ||
        location.pathname.startsWith("/portfolio/") ||
        location.pathname.startsWith("/stock/")
      );
    }

    return location.pathname.startsWith(path);
  };

  return (
    <header className="app-navbar-wrap">
      <div className="app-navbar">
        <div className="app-navbar-left">
          <button className="app-brand" onClick={() => navigate("/dashboard")}>
            Check.Stock
          </button>
        </div>

        <div className="app-navbar-right">
          <nav className="app-nav-links" aria-label="Primary navigation">
            {links.map((link) => {
              const isActive = isLinkActive(link.path);
              return (
                <button
                  key={link.path}
                  className={`app-nav-link ${isActive ? "active" : ""}`}
                  onClick={() => navigate(link.path)}
                >
                  {link.label}
                </button>
              );
            })}
          </nav>
          <div className="app-admin-pill">Analyst: {staffName}</div>
          <button className="app-logout-btn" onClick={onLogout}>Logout</button>
        </div>
      </div>
    </header>
  );
}

export default AppNavbar;

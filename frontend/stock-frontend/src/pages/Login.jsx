import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";
import "./Login.css";

function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const res = await api.post("staff/login/", { email, password });
      localStorage.setItem("staff_id", String(res.data.staff_id));
      localStorage.setItem("staff_name", res.data.name || "");
      navigate("/dashboard");
    } catch (error) {
      console.log(error);
      alert("Invalid credentials");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-shell">
        <div className="login-container">
          <div className="login-card">
            <div className="auth-brand">Check.Stock</div>
            <h1>Welcome Back</h1>
            <p className="subtitle">Sign in to manage portfolios and analytics.</p>

            <form onSubmit={handleLogin} className="auth-form">
              <input
                type="email"
                placeholder="Enter email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />

              <input
                type="password"
                placeholder="Enter password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />

              <div className="auth-actions">
                <button className="auth-primary-btn" type="submit" disabled={loading}>
                  {loading ? "Logging in..." : "Login"}
                </button>
                <button
                  className="auth-secondary-btn"
                  type="button"
                  onClick={() => navigate("/signup")}
                >
                  Create account
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Login;

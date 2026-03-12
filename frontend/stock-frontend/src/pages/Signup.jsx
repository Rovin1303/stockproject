import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";
import "./Login.css";

function Signup() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSignup = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const res = await api.post("staff/register/", { name, email, password });
      localStorage.setItem("staff_id", String(res.data.staff_id));
      localStorage.setItem("staff_name", res.data.name || name);
      navigate("/dashboard");
    } catch (error) {
      console.log(error);
      alert("Unable to register. Email may already exist.");
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
            <h1>Create Admin Account</h1>
            <p className="subtitle">Register and continue to portfolio dashboard.</p>

            <form onSubmit={handleSignup} className="auth-form">
              <input
                type="text"
                placeholder="Enter name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />

              <input
                type="email"
                placeholder="Enter email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />

              <input
                type="password"
                placeholder="Create password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />

              <div className="auth-actions">
                <button className="auth-primary-btn" type="submit" disabled={loading}>
                  {loading ? "Creating..." : "Sign up"}
                </button>
                <button
                  className="auth-secondary-btn"
                  type="button"
                  onClick={() => navigate("/login")}
                >
                  Already have account
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Signup;

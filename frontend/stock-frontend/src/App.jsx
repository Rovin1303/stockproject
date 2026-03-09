// src/App.js

import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Dashboard from "./pages/Dashboard";
import PortfolioDetail from "./pages/PortfolioDetail";
import StockDetail from "./pages/StockDetail";
import MetalsCorrelationPage from "./pages/MetalsCorrelationPage";
import TimeSeriesForecast from "./pages/TimeSeriesForecast";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/portfolio/:portfolioId" element={<PortfolioDetail />} />
        <Route path="/stock/:stockId" element={<StockDetail />} />
        <Route path="/metals" element={<MetalsCorrelationPage />} />
        <Route path="/timeseries" element={<TimeSeriesForecast />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;

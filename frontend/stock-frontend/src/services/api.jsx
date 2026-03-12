import axios from "axios";

const configuredBaseUrl = process.env.REACT_APP_API_BASE_URL;
const defaultBaseUrl = `${window.location.protocol}//${window.location.hostname}/api/`;

const api = axios.create({
  baseURL: configuredBaseUrl || defaultBaseUrl,
  timeout: 15000,
});

api.interceptors.request.use((config) => {
  const staffId = window.localStorage.getItem("staff_id");
  const url = typeof config.url === "string" ? config.url : "";
  const isAuthRoute = url.includes("/staff/login/") || url.includes("/staff/register/");

  if (staffId && !isAuthRoute) {
    config.params = {
      ...(config.params || {}),
      staff_id: Number(staffId),
    };
  }

  return config;
});

export default api;
module.exports = {
  apps: [
    {
      name: "finance_backend",
      script: "cmd",
      args: "/c env\\Scripts\\python finance_backend\\manage.py runserver 0.0.0.0:8000",
      cwd: "./"
    },
    {
      name: "frontend",
      script: "cmd",
      args: "/c npm start",
      cwd: "./frontend/stock-frontend"
    }
  ]
};
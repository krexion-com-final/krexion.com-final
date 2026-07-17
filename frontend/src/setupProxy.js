// Krexion CRA dev-server proxy: forward /api → local FastAPI backend
// This ONLY runs during `craco start` / `react-scripts start` (preview mode).
// In production (VPS), nginx or the Docker Compose config handles /api routing.
const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function (app) {
  const target = process.env.REACT_APP_INTERNAL_BACKEND || 'http://localhost:8001';

  app.use(
    '/api',
    createProxyMiddleware({
      target,
      changeOrigin: true,
      ws: true,
      xfwd: true,
      logLevel: 'warn',
    })
  );

  // Also forward /ws websocket path if used anywhere
  app.use(
    '/ws',
    createProxyMiddleware({
      target,
      changeOrigin: true,
      ws: true,
      logLevel: 'warn',
    })
  );
};

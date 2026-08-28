import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// The API runs on 8000 (uvicorn). Proxying keeps the browser on one origin, so
// EventSource works without depending on the API's permissive CORS - which is
// a localhost-demo convenience and must not be what the app relies on.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // SSE must not be buffered, or Panel 2 shows nothing until the run ends.
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            proxyRes.headers['cache-control'] = 'no-cache'
          })
        },
      },
    },
  },
})

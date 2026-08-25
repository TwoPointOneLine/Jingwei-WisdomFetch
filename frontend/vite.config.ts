import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 阶段4：全部经网关统一入口（8080），前缀剥离由网关完成
      '/api/import': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      '/api/query': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      '/api/auth': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      '/api/user': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
    },
  },
})

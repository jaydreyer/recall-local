import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react()],
    server: {
      proxy: {
        '/v1': {
          target: env.VITE_RECALL_DEV_PROXY_TARGET || 'http://localhost:8090',
          changeOrigin: true,
        },
      },
    },
  }
})

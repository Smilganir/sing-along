import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const isProd = mode === 'production';
  const base = process.env.VITE_BASE_PATH ?? (isProd ? './' : '/');

  return {
    base,
    plugins: [react()],
    server: {
      port: 5175,
      strictPort: true,
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
          proxyTimeout: 600000,
        },
      },
    },
    preview: {
      port: 5175,
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
          proxyTimeout: 600000,
        },
      },
    },
  };
});

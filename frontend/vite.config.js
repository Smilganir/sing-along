import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const isProd = mode === 'production';
  const base = process.env.VITE_BASE_PATH ?? (isProd ? './' : '/');

  return {
    base,
    plugins: [react()],
    server: {
      host: '127.0.0.1',
      port: 5175,
      strictPort: true,
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
          proxyTimeout: 600000,
        },
        '/agc-proxy': {
          target: 'https://www.all-guitar-chords.com',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/agc-proxy/, ''),
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
        '/agc-proxy': {
          target: 'https://www.all-guitar-chords.com',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/agc-proxy/, ''),
        },
      },
    },
  };
});

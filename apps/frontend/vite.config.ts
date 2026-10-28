import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const base = process.env.MTRL_FRONTEND_BASE || '/preview/';
if (!['/app/', '/preview/'].includes(base)) throw new Error('Unsupported frontend base');

export default defineConfig({
  plugins: [react()],
  base,
  server: { proxy: { '/api': 'http://127.0.0.1:8037', '/static': 'http://127.0.0.1:8037', '/login': 'http://127.0.0.1:8037', '/m15': 'http://127.0.0.1:8037' } },
  build: { manifest: true },
});

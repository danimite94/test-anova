import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// In dev, /api is proxied to the backend; in the image, nginx does the same (ADR-0005).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': process.env.API_PROXY_TARGET ?? 'http://localhost:8000' },
  },
  test: {
    environment: 'jsdom',
    include: ['tests/unit/**/*.test.{ts,tsx}'],
    setupFiles: ['tests/unit/setup.ts'],
  },
});

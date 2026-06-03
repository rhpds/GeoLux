import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

const API_TARGET = process.env.GEOLUX_API_URL || 'http://localhost:8091';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3001,
    proxy: {
      '/health': API_TARGET,
      '/mode': API_TARGET,
      '/stability': API_TARGET,
      '/hypotheses': API_TARGET,
      '/classify': API_TARGET,
      '/mpc': API_TARGET,
      '/deepfield': API_TARGET,
      '/launchpad': API_TARGET,
      '/scenarios': API_TARGET,
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './vitest.setup.ts',
  },
});

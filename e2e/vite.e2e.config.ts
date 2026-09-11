import { defineConfig } from 'vite';
import baseConfig from '../vite.config.ts';
import { DJANGO_PORT } from './constants.ts';

// Misma configuración que vite.config.ts (intocable), solo cambia el destino
// del proxy al backend de pruebas en vez del Django de desarrollo real.
export default defineConfig({
  ...baseConfig,
  server: {
    ...baseConfig.server,
    proxy: {
      '/api': `http://127.0.0.1:${DJANGO_PORT}`,
      '/media': `http://127.0.0.1:${DJANGO_PORT}`,
    },
  },
});

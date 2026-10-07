import { defineConfig } from 'vitest/config';
import { svelte } from '@sveltejs/vite-plugin-svelte';
export default defineConfig({
  plugins: [svelte()],
  resolve: process.env.VITEST ? { conditions: ['browser'] } : undefined,
  server: { proxy: { '/api': 'http://localhost:8000' } },
  test: { environment: 'jsdom', include: ['tests/**/*.dom.test.ts'], setupFiles: ['tests/dom-setup.ts'] }
});

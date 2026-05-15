import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { defineConfig } from 'vite';

const host = process.env.TAURI_DEV_HOST;

// https://vitejs.dev/config/
export default defineConfig(async () => ({
  plugins: [sveltekit(), svelteTesting()],

  // Tauri expects a fixed port, fail if not available
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
    host: host || false,
    hmr: host
      ? {
          protocol: 'ws',
          host,
          port: 5174
        }
      : undefined,
    watch: {
      ignored: ['**/src-tauri/**']
    }
  },

  envPrefix: ['VITE_', 'TAURI_ENV_*'],

  build: {
    target: process.env.TAURI_ENV_PLATFORM === 'windows' ? 'chrome105' : 'safari13',
    minify: !process.env.TAURI_ENV_DEBUG ? 'esbuild' : false,
    sourcemap: !!process.env.TAURI_ENV_DEBUG,
    rollupOptions: {
      output: {
        // manualChunks: only split chart.js + svelte-i18n when they are
        // actually bundled (not treated as externals by plugins).
        // Using a function form avoids the "external module" error when
        // running `vite build` outside the full Tauri pipeline.
        manualChunks(id) {
          if (id.includes('node_modules/chart.js')) return 'chart';
          if (id.includes('node_modules/svelte-i18n')) return 'i18n';
        }
      }
    }
  },

  test: {
    environment: 'jsdom',
    globals: true,
    include: ['tests/unit/**/*.test.ts'],
    exclude: ['tests/e2e/**'],
    setupFiles: ['./tests/unit/setup.ts'],
    coverage: {
      reporter: ['text', 'html'],
      include: ['src/lib/**/*.{ts,svelte}']
    }
  }
}));

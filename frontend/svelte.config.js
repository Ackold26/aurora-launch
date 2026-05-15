import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      pages: 'build',
      assets: 'build',
      fallback: 'index.html',
      precompress: false,
      strict: true
    }),
    prerender: {
      // Dynamic routes like /project/[uuid]/history are never pre-crawled;
      // suppress the SvelteKit post-build error so CI bundle-size check
      // can read compiled output from .svelte-kit/output/client/.
      handleUnseenRoutes: 'warn',
    },
    alias: {
      $lib: 'src/lib',
      $types: 'src/lib/types',
      $ipc: 'src/lib/ipc'
    },
    csp: {
      mode: 'auto',
      directives: {
        'default-src': ['self'],
        'script-src': ['self'],
        'style-src': ['self', 'unsafe-inline'],
        'img-src': ['self', 'data:', 'asset:'],
        'connect-src': ['self', 'ipc:', 'http://ipc.localhost', 'https://updates.auroraai.pro']
      }
    }
  }
};

export default config;

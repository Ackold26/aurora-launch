// SvelteKit static-adapter compatibility — pre-render всё.
export const prerender = true;
export const ssr = false; // Tauri webview is client-side only
export const trailingSlash = 'never';

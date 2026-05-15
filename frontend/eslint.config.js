import sveltePlugin from 'eslint-plugin-svelte';
import svelteParser from 'svelte-eslint-parser';

/** @type {import('eslint').Linter.FlatConfig[]} */
export default [
  {
    ignores: [
      '.svelte-kit/**',
      'build/**',
      'node_modules/**',
      '**/*.d.ts',
      'scripts/**',
    ],
  },

  // JS / TS source files (no TypeScript parser required — basic ESLint rules)
  {
    files: ['src/**/*.{ts,js,mjs}'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
    },
    rules: {
      'no-console': ['warn', { allow: ['warn', 'error'] }],
      'prefer-const': 'error',
      eqeqeq: ['error', 'always'],
    },
  },

  // Svelte files — use flat/recommended from eslint-plugin-svelte
  ...sveltePlugin.configs['flat/recommended'],
  {
    files: ['**/*.svelte'],
    languageOptions: {
      parser: svelteParser,
    },
    rules: {
      'svelte/no-at-html-tags': 'error',
      'no-console': ['warn', { allow: ['warn', 'error'] }],
    },
  },
];

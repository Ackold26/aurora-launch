import { defineConfig } from 'histoire';
import { HstSvelte } from '@histoire/plugin-svelte';

export default defineConfig({
  plugins: [HstSvelte()],
  setupFile: 'src/lib/styles/histoire.setup.ts',
  storyMatch: ['src/**/*.story.svelte'],
  theme: {
    title: 'Aurora Launch — Component Gallery',
    favicon: '/favicon.svg',
    colors: {
      primary: {
        50: '#EFF4FF',
        100: '#D8E2FF',
        500: '#2E5BFF',
        600: '#1E4BEF',
        700: '#163ED4',
        900: '#0A1F8C'
      }
    }
  },
  defaultStoryProps: {
    autoPropsDisabled: false
  },
  tree: {
    groups: [
      { id: 'foundations', title: 'Foundations' },
      { id: 'tokens', title: 'Tokens' },
      { id: 'primitives', title: 'Primitives' },
      { id: 'components', title: 'Components' },
      { id: 'flows', title: 'Flows' }
    ]
  }
});

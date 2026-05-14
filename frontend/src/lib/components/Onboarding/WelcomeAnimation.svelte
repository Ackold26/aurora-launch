<!--
  WelcomeAnimation — 800ms brand intro for first-time users.
  Phase Premium P-01.

  Logo + tagline fade-in + slide-up. Respects prefers-reduced-motion (INV-14):
  reduced-motion users see static logo immediately without animation.

  Used by /onboarding route; emits `complete` event after animation duration.
-->

<script lang="ts">
  import { onMount } from 'svelte';

  interface Props {
    /** Skip animation entirely (e.g., for tests). */
    instant?: boolean;
    /** Callback fired when animation finishes (or immediately if instant). */
    oncomplete?: () => void;
  }

  let { instant = false, oncomplete }: Props = $props();

  let visible = $state(false);

  onMount(() => {
    // Set visible to trigger CSS transition. If reduced-motion, CSS shows static.
    requestAnimationFrame(() => {
      visible = true;
    });
    const t = instant ? 0 : 850;
    const timer = setTimeout(() => oncomplete?.(), t);
    return () => clearTimeout(timer);
  });
</script>

<div class="welcome-anim" class:visible aria-label="Загрузка приветствия">
  <div class="logo-mark" aria-hidden="true">
    <svg viewBox="0 0 64 64" width="64" height="64">
      <circle cx="32" cy="32" r="28" fill="none" stroke="currentColor" stroke-width="3" />
      <circle cx="32" cy="32" r="14" fill="currentColor" opacity="0.5" />
    </svg>
  </div>
  <h1 class="brand">Aurora</h1>
  <p class="tagline">Launch Planner</p>
</div>

<style>
  .welcome-anim {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--spacing-3, 0.75rem);
    min-height: 280px;
    color: var(--text-primary, #111827);
  }

  .logo-mark,
  .brand,
  .tagline {
    opacity: 0;
    transform: translateY(8px);
    transition: opacity 600ms ease-out, transform 600ms ease-out;
  }

  .welcome-anim.visible .logo-mark {
    opacity: 1;
    transform: translateY(0);
    transition-delay: 0ms;
  }

  .welcome-anim.visible .brand {
    opacity: 1;
    transform: translateY(0);
    transition-delay: 150ms;
  }

  .welcome-anim.visible .tagline {
    opacity: 1;
    transform: translateY(0);
    transition-delay: 300ms;
  }

  .brand {
    font-family: var(--font-display, var(--font-sans, sans-serif));
    font-size: 2.5rem;
    font-weight: 700;
    margin: 0;
    letter-spacing: -0.02em;
  }

  .tagline {
    color: var(--text-secondary, #6b7280);
    font-size: var(--typography-fontSize-ui-h3, 1.25rem);
    margin: 0;
  }

  .logo-mark {
    color: var(--accent, #2563eb);
  }

  /* INV-14 reduced-motion: skip transitions entirely */
  @media (prefers-reduced-motion: reduce) {
    .logo-mark,
    .brand,
    .tagline {
      opacity: 1;
      transform: none;
      transition: none;
    }
  }
</style>

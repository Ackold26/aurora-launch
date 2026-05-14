<!--
  SensitivityScenarios — 3 предзаданные scenario cards (Phase Π.3.2 Manager default).

  Closes audit P-07 (sensitivity dashboard 6 sliders = complexity inflation).
  Per INV-25 dual-mode UX: 3 cards default (Manager), 6-slider Expert mode opt-in.

  Each card shows forecast + CI under specific perturbation scenario:
    - Pessimistic (worst plausible case)
    - Base (current parameters)
    - Optimistic (best plausible case)
-->

<script lang="ts">
  interface ScenarioData {
    name: 'pessimistic' | 'base' | 'optimistic';
    title: string;
    description: string;
    pointForecastFormatted: string;
    ciLowerFormatted: string;
    ciUpperFormatted: string;
    deltaPctVsBase: number;
  }

  interface Props {
    scenarios: ScenarioData[];
    selected?: 'pessimistic' | 'base' | 'optimistic';
    onSelectScenario?: (name: string) => void;
    onSwitchToExpert?: () => void;
  }

  let { scenarios, selected = 'base', onSelectScenario, onSwitchToExpert }: Props = $props();

  function handleClick(name: 'pessimistic' | 'base' | 'optimistic') {
    onSelectScenario?.(name);
  }
</script>

<section class="sensitivity-scenarios" aria-label="Сценарии чувствительности прогноза">
  <header class="scenarios-header">
    <h3 class="scenarios-title">Сценарии прогноза</h3>
    <button type="button" class="expert-toggle" onclick={onSwitchToExpert}>
      ⚙ Expert mode (расширенные параметры)
    </button>
  </header>

  <div class="scenarios-grid">
    {#each scenarios as scenario (scenario.name)}
      <button
        type="button"
        class="scenario-card"
        class:selected={selected === scenario.name}
        data-tier={scenario.name}
        onclick={() => handleClick(scenario.name)}
        aria-pressed={selected === scenario.name}
      >
        <div class="scenario-tier-label">{scenario.title}</div>
        <p class="scenario-description">{scenario.description}</p>
        <div class="scenario-forecast">
          <div class="scenario-point">{scenario.pointForecastFormatted}</div>
          <div class="scenario-ci">
            CI: {scenario.ciLowerFormatted} — {scenario.ciUpperFormatted}
          </div>
        </div>
        {#if scenario.name !== 'base'}
          <div
            class="scenario-delta"
            data-direction={scenario.deltaPctVsBase >= 0 ? 'up' : 'down'}
          >
            {scenario.deltaPctVsBase >= 0 ? '+' : ''}{scenario.deltaPctVsBase.toFixed(1)}% vs Base
          </div>
        {/if}
      </button>
    {/each}
  </div>
</section>

<style>
  .sensitivity-scenarios {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3);
  }

  .scenarios-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--spacing-3);
  }

  .scenarios-title {
    font-size: var(--typography-fontSize-ui-h3);
    font-weight: 500;
    color: var(--text-primary);
    margin: 0;
  }

  .expert-toggle {
    background: transparent;
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-md);
    padding: var(--spacing-1) var(--spacing-3);
    font-size: var(--typography-fontSize-ui-sm);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--motion-fast) var(--easing-smooth);
  }
  .expert-toggle:hover {
    color: var(--text-primary);
    border-color: var(--accent);
  }

  .scenarios-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--spacing-3);
  }

  .scenario-card {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
    padding: var(--spacing-4);
    background: var(--bg-surface);
    border: 2px solid var(--border-subtle);
    border-radius: var(--border-radius-lg);
    cursor: pointer;
    text-align: left;
    color: inherit;
    font-family: inherit;
    transition:
      transform var(--motion-default) var(--easing-spring),
      border-color var(--motion-default) var(--easing-smooth),
      box-shadow var(--motion-default) var(--easing-smooth);
  }

  .scenario-card:hover:not(.selected) {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
  }

  .scenario-card[data-tier='pessimistic'] {
    border-top: 4px solid var(--color-danger);
  }
  .scenario-card[data-tier='base'] {
    border-top: 4px solid var(--color-info);
  }
  .scenario-card[data-tier='optimistic'] {
    border-top: 4px solid var(--color-success);
  }

  .scenario-card.selected {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 20%, transparent);
  }

  .scenario-tier-label {
    font-size: var(--typography-fontSize-ui-sm);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-secondary);
    font-weight: 600;
  }

  .scenario-description {
    font-size: var(--typography-fontSize-ui-sm);
    color: var(--text-secondary);
    margin: 0;
    min-height: 2.5em;
  }

  .scenario-forecast {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1);
    margin-top: var(--spacing-2);
  }

  .scenario-point {
    font-size: var(--typography-fontSize-ui-h2);
    font-weight: 600;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
  }

  .scenario-ci {
    font-size: var(--typography-fontSize-ui-xs);
    color: var(--text-secondary);
    font-variant-numeric: tabular-nums;
  }

  .scenario-delta {
    font-size: var(--typography-fontSize-ui-xs);
    font-weight: 500;
    margin-top: var(--spacing-1);
    padding: var(--spacing-1) var(--spacing-2);
    border-radius: var(--border-radius-sm);
    align-self: flex-start;
  }
  .scenario-delta[data-direction='up'] {
    color: var(--color-success);
    background: color-mix(in srgb, var(--color-success) 12%, transparent);
  }
  .scenario-delta[data-direction='down'] {
    color: var(--color-danger);
    background: color-mix(in srgb, var(--color-danger) 12%, transparent);
  }

  /* Reduced motion respect — INV-14 */
  @media (prefers-reduced-motion: reduce) {
    .scenario-card {
      transition: none;
    }
    .scenario-card:hover:not(.selected) {
      transform: none;
    }
  }

  /* Responsive: stack on narrow viewports */
  @media (max-width: 720px) {
    .scenarios-grid {
      grid-template-columns: 1fr;
    }
  }
</style>

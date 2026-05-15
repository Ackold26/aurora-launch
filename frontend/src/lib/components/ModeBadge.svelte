<!--
  ModeBadge — engine mode honest disclosure (Phase Π R-09 audit fix).

  Closes audit P-09 (4-mode router shows 1 real mode but customer-facing UI
  says "Bayesian-режим"). This badge shows actual engine + transparency about
  fallback paths.

  Mode mapping:
    pure_transfer              → "Pure Transfer" — green (no fallback, exact math)
    transfer_with_bias_check   → "Transfer + Bias Check" — green
    ols_with_proxy_priors      → "OLS + Proxy Priors (fallback)" — amber + tooltip
    bayesian_with_proxy_priors → "Bayesian + Proxy Priors (fallback)" — amber + tooltip

  Per INV-25 dual-mode UX: Manager mode shows colour + short label; Expert mode
  exposes full mode value + fallback explanation в tooltip.
-->

<script lang="ts">
	import { _ } from 'svelte-i18n';

	interface Props {
		mode:
			| 'pure_transfer'
			| 'transfer_with_bias_check'
			| 'ols_with_proxy_priors'
			| 'bayesian_with_proxy_priors';
		warnings?: string[];
		showFullDetails?: boolean;
	}

	let { mode, warnings = [], showFullDetails = false }: Props = $props();

	const modeInfo = $derived.by(() => {
		switch (mode) {
			case 'pure_transfer':
				return {
					label: $_('modeBadge.pure_transfer.label'),
					sublabel: $_('modeBadge.pure_transfer.sublabel'),
					tone: 'success' as const,
					isFallback: false,
					explanation: $_('modeBadge.pure_transfer.explanation'),
				};
			case 'transfer_with_bias_check':
				return {
					label: $_('modeBadge.transfer_bias.label'),
					sublabel: $_('modeBadge.transfer_bias.sublabel'),
					tone: 'success' as const,
					isFallback: false,
					explanation: $_('modeBadge.transfer_bias.explanation'),
				};
			case 'ols_with_proxy_priors':
				return {
					label: $_('modeBadge.ols_priors.label'),
					sublabel: $_('modeBadge.ols_priors.sublabel'),
					tone: 'warning' as const,
					isFallback: true,
					explanation: $_('modeBadge.ols_priors.explanation'),
				};
			case 'bayesian_with_proxy_priors':
				return {
					label: $_('modeBadge.bayesian_priors.label'),
					sublabel: $_('modeBadge.bayesian_priors.sublabel'),
					tone: 'warning' as const,
					isFallback: true,
					explanation: $_('modeBadge.bayesian_priors.explanation'),
				};
		}
	});

	let tooltipOpen = $state(false);
	function toggleTooltip() {
		tooltipOpen = !tooltipOpen;
	}

	// PI-RESCUE-05 audit fix: Escape key dismisses tooltip when open.
	// Improves accessibility — keyboard users can close без mouse.
	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && tooltipOpen) {
			e.preventDefault();
			tooltipOpen = false;
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="mode-badge-wrapper">
	<button
		type="button"
		class="mode-badge"
		data-tone={modeInfo.tone}
		data-fallback={modeInfo.isFallback}
		aria-describedby="mode-badge-tooltip"
		aria-expanded={tooltipOpen}
		onclick={toggleTooltip}
	>
		<span class="mode-badge-label">{modeInfo.label}</span>
		<span class="mode-badge-sub">{modeInfo.sublabel}</span>
		{#if modeInfo.isFallback}
			<span class="mode-badge-fallback-icon" aria-hidden="true">⚠</span>
		{/if}
		<span class="mode-badge-info-icon" aria-hidden="true">ⓘ</span>
	</button>

	{#if tooltipOpen}
		<div id="mode-badge-tooltip" class="mode-badge-tooltip" role="tooltip">
			<p class="mode-badge-explanation">{modeInfo.explanation}</p>
			{#if warnings.length > 0}
				<details class="mode-badge-warnings">
					<summary>{$_('modeBadge.warnings_summary')}</summary>
					<ul>
						{#each warnings as w}
							<li>{w}</li>
						{/each}
					</ul>
				</details>
			{/if}
			{#if showFullDetails}
				<p class="mode-badge-mode-value">
					Mode identifier: <code>{mode}</code>
				</p>
			{/if}
		</div>
	{/if}
</div>

<style>
	.mode-badge-wrapper {
		position: relative;
		display: inline-block;
	}

	.mode-badge {
		display: inline-flex;
		align-items: center;
		gap: var(--spacing-2, 0.5rem);
		padding: var(--spacing-1, 0.25rem) var(--spacing-3, 0.75rem);
		background: var(--bg-elevated, #1c1f26);
		border: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.1));
		border-radius: var(--border-radius-md, 6px);
		color: inherit;
		font-family: inherit;
		font-size: var(--typography-fontSize-ui-sm, 0.875rem);
		cursor: pointer;
		transition: all var(--motion-fast, 150ms) var(--easing-smooth, ease);
	}

	.mode-badge[data-tone='success'] {
		border-left: 3px solid var(--color-success, #34d399);
	}
	.mode-badge[data-tone='warning'] {
		border-left: 3px solid var(--color-warning, #fbbf24);
	}

	.mode-badge:hover {
		border-color: var(--accent, #60a5fa);
	}

	.mode-badge-label {
		font-weight: 500;
	}

	.mode-badge-sub {
		color: var(--text-secondary, rgba(255, 255, 255, 0.65));
		font-size: var(--typography-fontSize-ui-xs, 0.75rem);
	}

	.mode-badge-fallback-icon {
		color: var(--color-warning, #fbbf24);
		font-size: 1rem;
	}

	.mode-badge-info-icon {
		color: var(--text-secondary, rgba(255, 255, 255, 0.5));
		font-size: 0.875rem;
		margin-left: var(--spacing-1, 0.25rem);
	}

	.mode-badge-tooltip {
		position: absolute;
		top: calc(100% + var(--spacing-1, 0.25rem));
		left: 0;
		z-index: 100;
		min-width: 280px;
		max-width: 400px;
		padding: var(--spacing-3, 0.75rem);
		background: var(--bg-elevated, #1c1f26);
		border: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.1));
		border-radius: var(--border-radius-md, 6px);
		box-shadow: var(--shadow-lg, 0 8px 24px rgba(0, 0, 0, 0.5));
	}

	.mode-badge-explanation {
		margin: 0 0 var(--spacing-2, 0.5rem) 0;
		font-size: var(--typography-fontSize-ui-sm, 0.875rem);
		line-height: 1.5;
	}

	.mode-badge-warnings {
		margin-top: var(--spacing-2, 0.5rem);
		font-size: var(--typography-fontSize-ui-xs, 0.75rem);
	}

	.mode-badge-warnings summary {
		cursor: pointer;
		color: var(--text-secondary, rgba(255, 255, 255, 0.65));
	}

	.mode-badge-warnings ul {
		margin: var(--spacing-1, 0.25rem) 0 0 var(--spacing-3, 0.75rem);
		padding: 0;
		color: var(--text-secondary, rgba(255, 255, 255, 0.65));
	}

	.mode-badge-warnings li {
		margin-bottom: var(--spacing-1, 0.25rem);
	}

	.mode-badge-mode-value {
		margin-top: var(--spacing-2, 0.5rem);
		font-size: var(--typography-fontSize-ui-xs, 0.75rem);
		color: var(--text-secondary, rgba(255, 255, 255, 0.5));
	}

	.mode-badge-mode-value code {
		font-family: ui-monospace, monospace;
		background: var(--bg-surface, #0f1115);
		padding: 1px 4px;
		border-radius: 3px;
	}

	@media (prefers-reduced-motion: reduce) {
		.mode-badge {
			transition: none;
		}
	}
</style>

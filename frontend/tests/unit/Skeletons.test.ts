// Vitest tests for per-route skeleton components (Phase Premium P-10).

import { describe, expect, it, beforeEach } from 'vitest';
import { render, cleanup } from '@testing-library/svelte';

import ProjectsListSkeleton from '../../src/lib/components/skeletons/ProjectsListSkeleton.svelte';
import ForecastHistorySkeleton from '../../src/lib/components/skeletons/ForecastHistorySkeleton.svelte';
import WizardStepSkeleton from '../../src/lib/components/skeletons/WizardStepSkeleton.svelte';
import InspectorSkeleton from '../../src/lib/components/skeletons/InspectorSkeleton.svelte';

beforeEach(() => cleanup());

// ---------------------------------------------------------------------------
// ProjectsListSkeleton
// ---------------------------------------------------------------------------

describe('ProjectsListSkeleton', () => {
  it('renders 5 skeleton cards', () => {
    const { container } = render(ProjectsListSkeleton);
    const cards = container.querySelectorAll('.skeleton-card');
    expect(cards.length).toBe(5);
  });

  it('each card has a name-bar, meta-bar and button placeholder', () => {
    const { container } = render(ProjectsListSkeleton);
    const cards = container.querySelectorAll('.skeleton-card');
    cards.forEach((card) => {
      expect(card.querySelector('.name-bar')).toBeTruthy();
      expect(card.querySelector('.meta-bar')).toBeTruthy();
      expect(card.querySelector('.skeleton-btn')).toBeTruthy();
    });
  });

  it('root element has aria-hidden="true"', () => {
    const { container } = render(ProjectsListSkeleton);
    const root = container.querySelector('.projects-skeleton');
    expect(root?.getAttribute('aria-hidden')).toBe('true');
  });
});

// ---------------------------------------------------------------------------
// ForecastHistorySkeleton
// ---------------------------------------------------------------------------

describe('ForecastHistorySkeleton', () => {
  it('renders exactly 3 skeleton rows', () => {
    const { container } = render(ForecastHistorySkeleton);
    const rows = container.querySelectorAll('.skeleton-row');
    expect(rows.length).toBe(3);
  });

  it('each row has a checkbox placeholder and meta block', () => {
    const { container } = render(ForecastHistorySkeleton);
    const rows = container.querySelectorAll('.skeleton-row');
    rows.forEach((row) => {
      expect(row.querySelector('.skeleton-checkbox')).toBeTruthy();
      expect(row.querySelector('.skeleton-meta')).toBeTruthy();
    });
  });

  it('root element has aria-hidden="true"', () => {
    const { container } = render(ForecastHistorySkeleton);
    const root = container.querySelector('.fh-skeleton');
    expect(root?.getAttribute('aria-hidden')).toBe('true');
  });
});

// ---------------------------------------------------------------------------
// WizardStepSkeleton
// ---------------------------------------------------------------------------

describe('WizardStepSkeleton', () => {
  it('renders title bar', () => {
    const { container } = render(WizardStepSkeleton);
    expect(container.querySelector('.title-bar')).toBeTruthy();
  });

  it('renders 3 form rows', () => {
    const { container } = render(WizardStepSkeleton);
    const rows = container.querySelectorAll('.form-row');
    expect(rows.length).toBe(3);
  });

  it('renders button row with 2 button placeholders', () => {
    const { container } = render(WizardStepSkeleton);
    const btns = container.querySelectorAll('.btn-row .skeleton-btn');
    expect(btns.length).toBe(2);
  });

  it('root element has aria-hidden="true"', () => {
    const { container } = render(WizardStepSkeleton);
    const root = container.querySelector('.wizard-skeleton');
    expect(root?.getAttribute('aria-hidden')).toBe('true');
  });
});

// ---------------------------------------------------------------------------
// InspectorSkeleton
// ---------------------------------------------------------------------------

describe('InspectorSkeleton', () => {
  it('renders 5 tab placeholders', () => {
    const { container } = render(InspectorSkeleton);
    const tabs = container.querySelectorAll('.skeleton-tab');
    expect(tabs.length).toBe(5);
  });

  it('renders 4 metadata rows in content area', () => {
    const { container } = render(InspectorSkeleton);
    const rows = container.querySelectorAll('.meta-row');
    expect(rows.length).toBe(4);
  });

  it('root element has aria-hidden="true"', () => {
    const { container } = render(InspectorSkeleton);
    const root = container.querySelector('.inspector-skeleton');
    expect(root?.getAttribute('aria-hidden')).toBe('true');
  });
});

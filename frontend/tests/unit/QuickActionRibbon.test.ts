import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/svelte';

// Mock SvelteKit navigation before importing the component.
vi.mock('$app/navigation', () => ({
  goto: vi.fn(),
}));

import QuickActionRibbon from '../../src/lib/components/welcome/QuickActionRibbon.svelte';
import { goto } from '$app/navigation';

const mockedGoto = vi.mocked(goto);

beforeEach(() => {
  mockedGoto.mockReset();
  mockedGoto.mockResolvedValue(undefined);
});

afterEach(() => cleanup());

describe('QuickActionRibbon', () => {
  it('renders 3 actions by default (refresh hidden когда onRefresh undefined)', () => {
    render(QuickActionRibbon);
    const buttons = document.querySelectorAll('.action');
    expect(buttons.length).toBe(3); // new / inspector / settings (no refresh)
  });

  it('renders 4 actions when onRefresh prop provided', () => {
    const onRefresh = vi.fn();
    render(QuickActionRibbon, { onRefresh });
    const buttons = document.querySelectorAll('.action');
    expect(buttons.length).toBe(4);
  });

  it('new project CTA has sigil styling (sacred lime)', () => {
    render(QuickActionRibbon);
    const sigil = document.querySelector('.action--sigil');
    expect(sigil).toBeTruthy();
    expect(sigil?.textContent?.toLowerCase()).toContain('новый прогноз');
  });

  it('clicking new project navigates к /wizard', async () => {
    render(QuickActionRibbon);
    const newCta = screen.getByRole('button', { name: /новый прогноз/i });
    await fireEvent.click(newCta);
    expect(mockedGoto).toHaveBeenCalledWith('/wizard');
  });

  it('clicking inspector CTA navigates к /inspector by default', async () => {
    render(QuickActionRibbon);
    const inspectorCta = screen.getByRole('button', { name: /открыть inspector/i });
    await fireEvent.click(inspectorCta);
    expect(mockedGoto).toHaveBeenCalledWith('/inspector');
  });

  it('respects inspectorHref prop override', async () => {
    render(QuickActionRibbon, { inspectorHref: '/inspector?project=xyz' });
    const inspectorCta = screen.getByRole('button', { name: /открыть inspector/i });
    await fireEvent.click(inspectorCta);
    expect(mockedGoto).toHaveBeenCalledWith('/inspector?project=xyz');
  });

  it('clicking settings navigates к /settings', async () => {
    render(QuickActionRibbon);
    const settingsCta = screen.getByRole('button', { name: /настройки/i });
    await fireEvent.click(settingsCta);
    expect(mockedGoto).toHaveBeenCalledWith('/settings');
  });

  it('refresh CTA calls onRefresh + disables button during async work', async () => {
    let resolveRefresh: () => void = () => {};
    const refreshPromise = new Promise<void>((res) => {
      resolveRefresh = res;
    });
    const onRefresh = vi.fn(() => refreshPromise);
    render(QuickActionRibbon, { onRefresh });

    const refreshCta = screen.getByRole('button', { name: /обновить/i });
    await fireEvent.click(refreshCta);

    // Should be disabled and aria-busy while promise pending
    await waitFor(() => {
      expect(refreshCta.hasAttribute('disabled')).toBe(true);
      expect(refreshCta.getAttribute('aria-busy')).toBe('true');
    });

    expect(onRefresh).toHaveBeenCalled();

    // After resolve, button becomes enabled again
    resolveRefresh();
    await waitFor(() => {
      expect(refreshCta.hasAttribute('disabled')).toBe(false);
    });
  });

  it('exposes <section> с localized aria-label', () => {
    render(QuickActionRibbon);
    const region = screen.getByRole('region', { name: /быстрые действия/i });
    expect(region.tagName.toLowerCase()).toBe('section');
  });
});

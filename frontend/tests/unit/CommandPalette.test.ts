import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';

import CommandPalette from '../../src/lib/components/CommandPalette.svelte';

beforeEach(() => cleanup());

// Sample commands fixture
const COMMANDS = [
  {
    id: 'new-project',
    label: 'Новый проект',
    description: 'Создать новый проект',
    category: 'Файл',
    shortcut: 'Ctrl+N',
    icon: '📁',
    action: vi.fn(),
  },
  {
    id: 'open-file',
    label: 'Открыть файл',
    description: 'Открыть существующий файл',
    category: 'Файл',
    shortcut: 'Ctrl+O',
    action: vi.fn(),
  },
  {
    id: 'settings',
    label: 'Настройки',
    description: 'Открыть настройки приложения',
    category: 'Система',
    action: vi.fn(),
  },
];

function freshCommands() {
  // Return commands with fresh vi.fn() so action mocks are clean per test
  return COMMANDS.map((c) => ({ ...c, action: vi.fn() }));
}

function defaultProps(overrides: Record<string, unknown> = {}) {
  return {
    commands: freshCommands(),
    open: true,
    onClose: vi.fn(),
    ...overrides,
  };
}

describe('CommandPalette', () => {
  // ---------- open/close ----------

  it('open=false → palette not rendered', () => {
    render(CommandPalette, defaultProps({ open: false }));
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('open=true → role=dialog backdrop visible', () => {
    render(CommandPalette, defaultProps());
    expect(screen.getByRole('dialog')).toBeTruthy();
  });

  it('open=true → search input visible', () => {
    render(CommandPalette, defaultProps());
    expect(screen.getByLabelText('Поиск действий')).toBeTruthy();
  });

  it('open=true → list of commands visible', () => {
    render(CommandPalette, defaultProps());
    expect(screen.getByRole('listbox')).toBeTruthy();
  });

  // ---------- search filtering ----------

  it('empty query → all commands shown', async () => {
    render(CommandPalette, defaultProps());
    const items = screen.getAllByRole('option');
    expect(items).toHaveLength(3);
  });

  it('search by label substring → filters results', async () => {
    render(CommandPalette, defaultProps());
    const input = screen.getByLabelText('Поиск действий');
    await fireEvent.input(input, { target: { value: 'файл' } });
    // Only "Новый проект" (category Файл) and "Открыть файл" match "файл"
    const items = screen.getAllByRole('option');
    expect(items.length).toBeGreaterThanOrEqual(1);
    expect(items.length).toBeLessThan(3);
  });

  it('search matches description substring', async () => {
    render(CommandPalette, defaultProps());
    const input = screen.getByLabelText('Поиск действий');
    await fireEvent.input(input, { target: { value: 'настройки приложения' } });
    const items = screen.getAllByRole('option');
    expect(items).toHaveLength(1);
    expect(items[0].textContent).toContain('Настройки');
  });

  it('no matches → "Ничего не найдено" displayed', async () => {
    render(CommandPalette, defaultProps());
    const input = screen.getByLabelText('Поиск действий');
    await fireEvent.input(input, { target: { value: 'zzzznotexists' } });
    expect(screen.getByText('Ничего не найдено')).toBeTruthy();
  });

  // ---------- keyboard navigation ----------

  it('ArrowDown increments selectedIndex (second item gets aria-selected=true)', async () => {
    render(CommandPalette, defaultProps());
    const backdrop = screen.getByRole('dialog');
    await fireEvent.keyDown(backdrop, { key: 'ArrowDown' });
    const items = screen.getAllByRole('option');
    // After one ArrowDown: index 1 is selected
    expect(items[1].getAttribute('aria-selected')).toBe('true');
    expect(items[0].getAttribute('aria-selected')).toBe('false');
  });

  it('ArrowUp at index 0 clamps to 0 (no change)', async () => {
    render(CommandPalette, defaultProps());
    const backdrop = screen.getByRole('dialog');
    await fireEvent.keyDown(backdrop, { key: 'ArrowUp' });
    const items = screen.getAllByRole('option');
    // Still index 0
    expect(items[0].getAttribute('aria-selected')).toBe('true');
  });

  it('ArrowDown then ArrowUp → back to first item selected', async () => {
    render(CommandPalette, defaultProps());
    const backdrop = screen.getByRole('dialog');
    await fireEvent.keyDown(backdrop, { key: 'ArrowDown' });
    await fireEvent.keyDown(backdrop, { key: 'ArrowUp' });
    const items = screen.getAllByRole('option');
    expect(items[0].getAttribute('aria-selected')).toBe('true');
    expect(items[1].getAttribute('aria-selected')).toBe('false');
  });

  it('Enter executes selected command action + calls onClose', async () => {
    const onClose = vi.fn();
    const commands = freshCommands();
    render(CommandPalette, { commands, open: true, onClose });
    const backdrop = screen.getByRole('dialog');
    // Default selectedIndex=0 → first command
    await fireEvent.keyDown(backdrop, { key: 'Enter' });
    expect(commands[0].action).toHaveBeenCalledOnce();
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('Escape → onClose called', async () => {
    const onClose = vi.fn();
    render(CommandPalette, { commands: freshCommands(), open: true, onClose });
    const backdrop = screen.getByRole('dialog');
    await fireEvent.keyDown(backdrop, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledOnce();
  });

  // ---------- backdrop click ----------

  it('backdrop click (target===currentTarget) → onClose called', async () => {
    const onClose = vi.fn();
    render(CommandPalette, { commands: freshCommands(), open: true, onClose });
    const backdrop = screen.getByRole('dialog');
    // Simulate click where target === currentTarget (click on backdrop itself)
    await fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledOnce();
  });

  // ---------- item click ----------

  it('click item button → action executed + onClose called', async () => {
    const onClose = vi.fn();
    const commands = freshCommands();
    render(CommandPalette, { commands, open: true, onClose });
    const itemButtons = screen.getAllByRole('button');
    await fireEvent.click(itemButtons[0]);
    expect(commands[0].action).toHaveBeenCalledOnce();
    expect(onClose).toHaveBeenCalledOnce();
  });

  // ---------- ARIA ----------

  it('aria-modal="true" present on dialog', () => {
    render(CommandPalette, defaultProps());
    const dialog = screen.getByRole('dialog');
    expect(dialog.getAttribute('aria-modal')).toBe('true');
  });

  it('role="dialog" on backdrop element', () => {
    render(CommandPalette, defaultProps());
    // getByRole('dialog') confirms role=dialog exists
    expect(screen.getByRole('dialog')).toBeTruthy();
  });

  // ---------- ARIA combobox pattern (WAI-ARIA 1.2 §3.8) ----------

  it('input has role="combobox" with aria-expanded=true when open', () => {
    render(CommandPalette, defaultProps({ open: true }));
    const input = screen.getByRole('combobox');
    expect(input.getAttribute('aria-expanded')).toBe('true');
  });

  it('input aria-controls references listbox by id', () => {
    render(CommandPalette, defaultProps());
    const input = screen.getByRole('combobox');
    const listboxId = input.getAttribute('aria-controls');
    expect(listboxId).toBeTruthy();
    const listbox = document.getElementById(listboxId!);
    expect(listbox).toBeTruthy();
    expect(listbox!.getAttribute('role')).toBe('listbox');
  });

  it('each option has unique id matching palette-option-<cmd.id> pattern', () => {
    render(CommandPalette, defaultProps());
    const options = screen.getAllByRole('option');
    const ids = options.map((o) => o.getAttribute('id') ?? '');
    // All IDs present and start with "palette-option-"
    expect(ids.every((id) => id.startsWith('palette-option-'))).toBe(true);
    // All IDs unique
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('aria-activedescendant on input matches first option id initially', () => {
    render(CommandPalette, defaultProps());
    const input = screen.getByRole('combobox');
    const options = screen.getAllByRole('option');
    const firstOptionId = options[0].getAttribute('id');
    expect(input.getAttribute('aria-activedescendant')).toBe(firstOptionId);
  });

  it('aria-activedescendant updates after ArrowDown navigation', async () => {
    render(CommandPalette, defaultProps());
    const backdrop = screen.getByRole('dialog');
    await fireEvent.keyDown(backdrop, { key: 'ArrowDown' });
    const input = screen.getByRole('combobox');
    const options = screen.getAllByRole('option');
    // After one ArrowDown: index 1 selected
    const secondOptionId = options[1].getAttribute('id');
    expect(input.getAttribute('aria-activedescendant')).toBe(secondOptionId);
  });

  it('aria-selected reflects current highlight: selected=true only on active option', () => {
    render(CommandPalette, defaultProps());
    const options = screen.getAllByRole('option');
    const selected = options.filter((o) => o.getAttribute('aria-selected') === 'true');
    const deselected = options.filter((o) => o.getAttribute('aria-selected') === 'false');
    expect(selected).toHaveLength(1);
    expect(deselected).toHaveLength(options.length - 1);
  });

  // ---------- mouse hover ----------

  it('mouseenter on item → that item becomes selected', async () => {
    render(CommandPalette, defaultProps());
    const items = screen.getAllByRole('option');
    // Hover over the third item (index 2)
    const thirdItemBtn = items[2].querySelector('button')!;
    await fireEvent.mouseEnter(thirdItemBtn);
    expect(items[2].getAttribute('aria-selected')).toBe('true');
    expect(items[0].getAttribute('aria-selected')).toBe('false');
  });
});

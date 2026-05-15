<!--
  CommandPalette — Cmd+K universal action search (Phase Π.3.4 premium UX).

  Per Plan v3.0 §A.5 UX-04 premium pattern. Powered user feature что
  отделяет premium-class apps от commodity. Triggered by Ctrl+K (Windows/Linux)
  or Cmd+K (macOS). Fuzzy search across all registered commands.

  INV-14 prefers-reduced-motion respect.
-->

<script lang="ts">
  interface Command {
    id: string;
    label: string;
    description?: string;
    shortcut?: string;
    category?: string;
    icon?: string;
    action: () => void | Promise<void>;
  }

  interface Props {
    commands: Command[];
    open: boolean;
    onClose: () => void;
  }

  let { commands, open, onClose }: Props = $props();

  let searchInput = $state('');
  let selectedIndex = $state(0);
  let inputRef = $state<HTMLInputElement | null>(null);

  // Stable listbox + option IDs for ARIA combobox pattern (WAI-ARIA 1.2 §3.8)
  const LISTBOX_ID = 'palette-listbox';
  const optionId = (cmdId: string) => `palette-option-${cmdId}`;

  // Fuzzy filter: substring match w/ case-insensitive, label + description + category
  const filteredCommands = $derived.by(() => {
    const query = searchInput.toLowerCase().trim();
    if (!query) return commands;
    return commands.filter((c) => {
      const haystack = [c.label, c.description ?? '', c.category ?? ''].join(' ').toLowerCase();
      return haystack.includes(query);
    });
  });

  // Active-descendant ID for screen-reader tracking of keyboard selection (WAI-ARIA 1.2 §3.8)
  const activeDescendant = $derived(
    filteredCommands.length > 0 ? optionId(filteredCommands[selectedIndex]?.id ?? '') : undefined
  );

  $effect(() => {
    if (open) {
      // Focus search input on open
      requestAnimationFrame(() => inputRef?.focus());
      // Reset state on open
      searchInput = '';
      selectedIndex = 0;
    }
  });

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      selectedIndex = Math.min(selectedIndex + 1, filteredCommands.length - 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      selectedIndex = Math.max(selectedIndex - 1, 0);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const cmd = filteredCommands[selectedIndex];
      if (cmd) {
        void cmd.action();
        onClose();
      }
    }
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) {
      onClose();
    }
  }
</script>

{#if open}
  <div
    class="palette-backdrop"
    onclick={handleBackdropClick}
    onkeydown={handleKeydown}
    role="dialog"
    aria-modal="true"
    aria-label="Палитра команд"
    tabindex="-1"
  >
    <div class="palette">
      <header class="palette-header">
        <div class="palette-icon" aria-hidden="true">⌘</div>
        <input
          bind:this={inputRef}
          bind:value={searchInput}
          type="text"
          placeholder="Поиск действий…"
          aria-label="Поиск действий"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={LISTBOX_ID}
          aria-activedescendant={activeDescendant}
          role="combobox"
          class="palette-search"
          autocomplete="off"
          spellcheck="false"
        />
        <kbd class="palette-shortcut-hint">Esc</kbd>
      </header>

      <ul id={LISTBOX_ID} class="palette-list" role="listbox" aria-label="Команды">
        {#if filteredCommands.length === 0}
          <li class="palette-empty" role="presentation">Ничего не найдено</li>
        {:else}
          {#each filteredCommands as cmd, i (cmd.id)}
            <!--
              PA-A05 fix: WAI-ARIA 1.2 §6.6.11 — <li role="option"> must not
              contain interactive children (button) because that breaks
              activedescendant focus model. Click + mouseenter handlers attach
              directly to the <li>. Keyboard activation drives через combobox
              input + aria-activedescendant pointing here.
            -->
            <li
              id={optionId(cmd.id)}
              class="palette-item"
              class:selected={i === selectedIndex}
              role="option"
              aria-selected={i === selectedIndex}
              onclick={() => {
                void cmd.action();
                onClose();
              }}
              onmouseenter={() => (selectedIndex = i)}
            >
              {#if cmd.icon}
                <span class="palette-item-icon" aria-hidden="true">{cmd.icon}</span>
              {/if}
              <div class="palette-item-content">
                <div class="palette-item-label">{cmd.label}</div>
                {#if cmd.description}
                  <div class="palette-item-description">{cmd.description}</div>
                {/if}
              </div>
              {#if cmd.shortcut}
                <kbd class="palette-item-shortcut">{cmd.shortcut}</kbd>
              {/if}
            </li>
          {/each}
        {/if}
      </ul>

      <footer class="palette-footer">
        <kbd>↑↓</kbd> навигация
        <kbd>↵</kbd> выполнить
        <kbd>Esc</kbd> закрыть
      </footer>
    </div>
  </div>
{/if}

<style>
  .palette-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.55);
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
    z-index: 9999;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding-top: 10vh;
    animation: fadeIn 0.15s ease-out;
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  .palette {
    width: 100%;
    max-width: 640px;
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-lg);
    box-shadow: var(--shadow-lg);
    display: flex;
    flex-direction: column;
    max-height: 70vh;
    overflow: hidden;
    animation: slideDown 0.2s var(--easing-spring);
  }

  @keyframes slideDown {
    from { transform: translateY(-10px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
  }

  .palette-header {
    display: flex;
    align-items: center;
    gap: var(--spacing-2);
    padding: var(--spacing-3) var(--spacing-4);
    border-bottom: 1px solid var(--border-subtle);
  }

  .palette-icon {
    font-size: 1.25rem;
    color: var(--text-secondary);
  }

  .palette-search {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    font-size: var(--typography-fontSize-ui-base);
    color: var(--text-primary);
    font-family: inherit;
  }
  .palette-search::placeholder {
    color: var(--text-secondary);
  }

  .palette-shortcut-hint {
    font-size: var(--typography-fontSize-ui-xs);
    color: var(--text-secondary);
    background: var(--bg-surface);
    padding: 2px 6px;
    border-radius: var(--border-radius-sm);
    border: 1px solid var(--border-subtle);
  }

  .palette-list {
    list-style: none;
    margin: 0;
    padding: var(--spacing-2);
    overflow-y: auto;
    flex: 1;
  }

  .palette-empty {
    text-align: center;
    color: var(--text-secondary);
    padding: var(--spacing-4);
  }

  .palette-item {
    margin: 0;
  }

  .palette-item-button {
    display: flex;
    align-items: center;
    gap: var(--spacing-2);
    width: 100%;
    padding: var(--spacing-2) var(--spacing-3);
    background: transparent;
    border: none;
    border-radius: var(--border-radius-md);
    cursor: pointer;
    text-align: left;
    color: var(--text-primary);
    font-family: inherit;
    transition: background var(--motion-fast) var(--easing-smooth);
  }

  .palette-item.selected .palette-item-button {
    background: color-mix(in srgb, var(--accent) 18%, transparent);
  }

  .palette-item-icon {
    font-size: 1.1rem;
    width: 24px;
    text-align: center;
  }

  .palette-item-content {
    flex: 1;
  }

  .palette-item-label {
    font-size: var(--typography-fontSize-ui-base);
    color: var(--text-primary);
  }

  .palette-item-description {
    font-size: var(--typography-fontSize-ui-xs);
    color: var(--text-secondary);
    margin-top: 2px;
  }

  .palette-item-shortcut {
    font-size: var(--typography-fontSize-ui-xs);
    color: var(--text-secondary);
    background: var(--bg-surface);
    padding: 2px 6px;
    border-radius: var(--border-radius-sm);
    border: 1px solid var(--border-subtle);
    flex-shrink: 0;
  }

  .palette-footer {
    padding: var(--spacing-2) var(--spacing-4);
    border-top: 1px solid var(--border-subtle);
    background: var(--bg-surface);
    font-size: var(--typography-fontSize-ui-xs);
    color: var(--text-secondary);
    display: flex;
    gap: var(--spacing-3);
  }
  .palette-footer kbd {
    background: var(--bg-elevated);
    padding: 1px 4px;
    border-radius: 3px;
    border: 1px solid var(--border-subtle);
    font-size: var(--typography-fontSize-ui-xs);
    margin-right: var(--spacing-1);
  }

  @media (prefers-reduced-motion: reduce) {
    .palette-backdrop,
    .palette {
      animation: none;
    }
    .palette-item-button {
      transition: none;
    }
  }
</style>

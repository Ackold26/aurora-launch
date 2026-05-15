/**
 * Keyboard shortcuts global service (Phase Π R-07 audit fix).
 *
 * Closes audit FE-01: CommandPalette shipped без shortcut binding logic —
 * Cmd+K / Ctrl+K never opens palette. This service hooks document keydown
 * events globally и dispatches к registered handlers.
 *
 * Pattern: Singleton service mounted в +layout.svelte. Components register
 * handlers via `registerShortcut(combo, handler)` и unregister on destroy.
 *
 * OS-aware: meta key (Cmd) on macOS; ctrl key (Ctrl) on Windows/Linux.
 *
 * Per INV-14: respect prefers-reduced-motion (no effect on shortcuts themselves;
 * documented для consistency).
 */

export type ShortcutHandler = (e: KeyboardEvent) => void;

interface ShortcutBinding {
	combo: string;
	handler: ShortcutHandler;
}

/**
 * Platform-aware modifier key check.
 * On macOS: meta (Cmd). On Windows/Linux: ctrl.
 */
function platformModifier(e: KeyboardEvent): boolean {
	const isMac = typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.platform);
	return isMac ? e.metaKey : e.ctrlKey;
}

/**
 * Normalise key combo string.
 * Format: "mod+k", "shift+mod+f", "alt+enter"
 * "mod" auto-resolves к ctrl on Win/Linux / cmd on macOS.
 */
function comboMatches(combo: string, e: KeyboardEvent): boolean {
	const parts = combo.toLowerCase().split('+').map((s) => s.trim());
	const key = parts[parts.length - 1];
	const modifiers = parts.slice(0, -1);

	// key is always defined: parts is a non-empty split result and last element exists.
	if (!key || e.key.toLowerCase() !== key.toLowerCase()) return false;

	const requireMod = modifiers.includes('mod');
	const requireShift = modifiers.includes('shift');
	const requireAlt = modifiers.includes('alt');
	const requireMeta = modifiers.includes('meta');
	const requireCtrl = modifiers.includes('ctrl');

	if (requireMod && !platformModifier(e)) return false;
	if (requireShift !== e.shiftKey) return false;
	if (requireAlt !== e.altKey) return false;
	if (requireMeta && !e.metaKey) return false;
	if (requireCtrl && !e.ctrlKey) return false;

	return true;
}

class KeyboardShortcutsService {
	private bindings: ShortcutBinding[] = [];
	private installed = false;

	private handleKeydown = (e: KeyboardEvent): void => {
		// Skip if focused в input / textarea / contenteditable (allow native shortcuts)
		const target = e.target as HTMLElement | null;
		if (target) {
			const tag = target.tagName?.toLowerCase();
			const editable = target.isContentEditable;
			if (tag === 'input' || tag === 'textarea' || editable) {
				// Exception: Cmd/Ctrl+K should still work in inputs (palette UX expectation)
				const isCmdK = (e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k';
				if (!isCmdK) return;
			}
		}

		for (const binding of this.bindings) {
			if (comboMatches(binding.combo, e)) {
				e.preventDefault();
				binding.handler(e);
				return;
			}
		}
	};

	install(): void {
		if (this.installed) return;
		if (typeof document === 'undefined') return; // SSR safety
		document.addEventListener('keydown', this.handleKeydown);
		this.installed = true;
	}

	uninstall(): void {
		if (!this.installed) return;
		if (typeof document === 'undefined') return;
		document.removeEventListener('keydown', this.handleKeydown);
		this.installed = false;
	}

	registerShortcut(combo: string, handler: ShortcutHandler): () => void {
		const binding: ShortcutBinding = { combo, handler };
		this.bindings.push(binding);
		// Return unregister function
		return () => {
			const idx = this.bindings.indexOf(binding);
			if (idx >= 0) this.bindings.splice(idx, 1);
		};
	}

	clearAll(): void {
		this.bindings = [];
	}

	/**
	 * For testing: simulate а keydown event против current bindings.
	 */
	__test_dispatch(event: KeyboardEvent): void {
		this.handleKeydown(event);
	}
}

export const keyboardShortcuts = new KeyboardShortcutsService();

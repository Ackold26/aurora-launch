// Wizard session store — Phase 1.C.1 BTA-2.
//
// Single Svelte 5 $state runes object для всего wizard state. Autosaved
// в ProjectDB._kv_store (v003) через sidecar wizard_session_save IPC.
// Debounced 500ms — не hot path, customer не должен ждать sync на каждое
// поле.
//
// Recovery flow: на mount wizard page вызывает .loadDraft() — если есть
// recoverable session (см. WizardSession.is_recoverable) → показывается
// recovery dialog (UX-3).

import { ipc } from '$ipc/client';
import type { WizardSession } from '$types/aurora-schemas';

const AUTOSAVE_DEBOUNCE_MS = 500;

/** Создаёт пустой wizard session с свежим UUID + timestamp. */
function makeBlankSession(): WizardSession {
  const now = new Date().toISOString();
  return {
    session_id: crypto.randomUUID(),
    step: 0,
    imported_file_path: null,
    imported_adapter_id: null,
    imported_record_count: null,
    imported_columns: null,
    column_roles: [],
    validation_done: false,
    selected_proxy_path: null,
    selected_proxy_label: null,
    similarity_result: null,
    anchors_draft: null,
    anchors_done: false,
    forecast_handle_id: null,
    forecast_completed: false,
    forecast_horizon: 26,
    cert_signed: false,
    saved_bundle_path: null,
    created_at: now,
    last_saved_at: now,
  } satisfies WizardSession;
}

class WizardSessionStore {
  // Single reactive source of truth — $state класс field автоматически tracked.
  session: WizardSession = $state(makeBlankSession());

  // Status indicators (для UI)
  loading = $state(false);
  saving = $state(false);
  lastSaveError: string | null = $state(null);

  // Pending draft из ProjectDB (для recovery dialog)
  pendingDraft: WizardSession | null = $state(null);

  // Internal debounce timer
  private _saveTimer: ReturnType<typeof setTimeout> | null = null;

  /** Mark dirty + schedule debounced save. Вызывается из mutator wrapping методов. */
  private _scheduleSave(): void {
    if (this._saveTimer !== null) {
      clearTimeout(this._saveTimer);
    }
    this._saveTimer = setTimeout(() => {
      void this._persistNow();
    }, AUTOSAVE_DEBOUNCE_MS);
  }

  private async _persistNow(): Promise<void> {
    this.saving = true;
    this.lastSaveError = null;
    try {
      this.session.last_saved_at = new Date().toISOString();
      await ipc.wizardSessionSave(this.session);
    } catch (e) {
      this.lastSaveError = e instanceof Error ? e.message : String(e);
      console.warn('[wizardSession] autosave failed:', e);
    } finally {
      this.saving = false;
    }
  }

  /** Read session.draft из sidecar. Заполняет pendingDraft если is_recoverable. */
  async loadDraft(): Promise<void> {
    this.loading = true;
    try {
      const result = await ipc.wizardSessionLoad();
      if (result.session) {
        // Heuristic: показываем recovery если customer достиг хоть какого-то
        // прогресса (импортировал файл ИЛИ перешёл за step 0).
        const recoverable =
          (result.session.imported_file_path !== null &&
            result.session.imported_file_path !== undefined) ||
          (result.session.step ?? 0) > 0;
        if (recoverable) {
          this.pendingDraft = result.session;
        }
      }
    } catch (e) {
      console.warn('[wizardSession] loadDraft failed:', e);
    } finally {
      this.loading = false;
    }
  }

  /** Customer confirmed recovery → swap текущий session на pendingDraft. */
  acceptRecovery(): void {
    if (this.pendingDraft) {
      this.session = this.pendingDraft;
      this.pendingDraft = null;
    }
  }

  /** Customer dismissed recovery → clear pendingDraft + erase saved draft. */
  async dismissRecovery(): Promise<void> {
    this.pendingDraft = null;
    try {
      await ipc.wizardSessionClear();
    } catch (e) {
      console.warn('[wizardSession] dismissRecovery clear failed:', e);
    }
  }

  /** Wrapper: mutate session field + schedule save. */
  update(mutator: (s: WizardSession) => void): void {
    mutator(this.session);
    this._scheduleSave();
  }

  /** Reset to blank — customer завершил wizard (saved bundle) или начал новый. */
  async reset(): Promise<void> {
    if (this._saveTimer !== null) {
      clearTimeout(this._saveTimer);
      this._saveTimer = null;
    }
    this.session = makeBlankSession();
    try {
      await ipc.wizardSessionClear();
    } catch (e) {
      console.warn('[wizardSession] reset clear failed:', e);
    }
  }

  /** Force-save сейчас (на критических моментах: cert signed, bundle saved). */
  async flush(): Promise<void> {
    if (this._saveTimer !== null) {
      clearTimeout(this._saveTimer);
      this._saveTimer = null;
    }
    await this._persistNow();
  }
}

/** Singleton instance — wizard page subscribes. */
export const wizardSession = new WizardSessionStore();

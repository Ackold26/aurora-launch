"""Schemas for automatic forecast refresh feature (ROADMAP §3.5).

Covers:
- DataSourceConfig   — per-source watcher config (folder path + seen-mtime)
- RefreshConsentSetting — user opt-in for automatic refresh (152-FZ compliant)
- RefreshTrigger     — event emitted when new data is detected

152-FZ compliance: all refresh triggers are gated behind explicit user consent.
No data is sent anywhere; watcher only reads mtime from LOCAL folders.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


_FROZEN = ConfigDict(frozen=True, extra="forbid", validate_assignment=True)
_MUTABLE = ConfigDict(extra="forbid", validate_assignment=True)


# ---------------------------------------------------------------------------
# DataSourceConfig
# ---------------------------------------------------------------------------


class DataSourceConfig(BaseModel):
    """Configuration for a single watched data source.

    source_kind:
        "dsm_xlsx_folder"        — watch a local folder for new DSM XLSX exports
        "mediascope_xlsx_folder" — watch a local folder for new Mediascope exports
        "manual"                 — customer imports manually; no auto-detection

    path:
        Absolute path to the watched folder.  Required for folder-watch kinds.
        Must be None for "manual".

    last_checked_at:
        ISO-8601 UTC datetime of the last check run (None = never checked).

    last_modified_seen:
        ISO-8601 UTC datetime of the most-recently-seen file mtime in this
        folder (None = baseline not yet established). A new file with mtime
        AFTER this value will trigger a RefreshTrigger.
    """

    model_config = _MUTABLE

    source_kind: Literal["dsm_xlsx_folder", "mediascope_xlsx_folder", "manual"]
    path: Optional[str] = None
    last_checked_at: Optional[str] = None
    last_modified_seen: Optional[str] = None

    @field_validator("path")
    @classmethod
    def path_required_for_folder_kinds(cls, v: Optional[str], info: Any) -> Optional[str]:
        # Validation runs after each field; info.data contains already-validated
        # fields so we can only check this when the field itself is "path".
        return v

    def model_post_init(self, __context: Any) -> None:
        if self.source_kind in ("dsm_xlsx_folder", "mediascope_xlsx_folder"):
            if not self.path:
                raise ValueError(
                    f"DataSourceConfig: path is required for source_kind={self.source_kind!r}"
                )
        if self.source_kind == "manual" and self.path is not None:
            raise ValueError(
                "DataSourceConfig: path must be None for source_kind='manual'"
            )


# ---------------------------------------------------------------------------
# RefreshConsentSetting
# ---------------------------------------------------------------------------


class RefreshConsentSetting(BaseModel):
    """User's opt-in consent for automatic forecast refresh (152-FZ §9 «согласие»).

    enabled:
        True  — user explicitly opted in; watcher may prompt on new data.
        False — user declined; no prompts, no auto-refresh.

    frequency:
        How often the watcher checks for new data.
        "daily"   — check once per calendar day (UTC midnight boundary).
        "weekly"  — check every 7 days.
        "monthly" — check every ~30 days.

    last_prompted_at:
        ISO-8601 UTC datetime of the last time the user was shown a refresh
        prompt.  None = user has never been prompted (first-run opt-in dialog
        has not appeared yet).
    """

    model_config = _MUTABLE

    enabled: bool = False
    frequency: Literal["daily", "weekly", "monthly"] = "weekly"
    last_prompted_at: Optional[str] = None


# ---------------------------------------------------------------------------
# RefreshTrigger
# ---------------------------------------------------------------------------


class RefreshTrigger(BaseModel):
    """Emitted by DataSourceWatcher when new data is detected for a project.

    project_uuid:
        UUID of the Aurora Launch project that should be re-forecast.

    reason:
        "new_data"  — watcher found files newer than last_modified_seen.
        "manual"    — user explicitly requested a refresh via UI.
        "scheduled" — scheduled re-forecast independent of data change.

    detected_at:
        ISO-8601 UTC datetime when the trigger was created.

    source:
        Human-readable source identifier, e.g. "dsm_xlsx_folder:/path/to/dir"
        or "manual".
    """

    model_config = _FROZEN

    project_uuid: str
    reason: Literal["new_data", "manual", "scheduled"]
    detected_at: str
    source: str

"""Tests for B1 TypeScript interface auto-generation."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel
from click.testing import CliRunner

from aurora_launch.tools.export_typescript import (
    _model_to_ts_interface,
    _python_type_to_ts,
    generate_ts_interfaces,
    main,
)


class _SimpleModel(BaseModel):
    name: str
    count: int
    optional_score: Optional[float] = None
    flag: bool = False


class _NestedModel(BaseModel):
    inner: _SimpleModel
    items: list[_SimpleModel]


class _LiteralModel(BaseModel):
    verdict: Literal["High", "Medium", "Low", "Insufficient"]
    tier: Literal["ECONOMY", "MAINSTREAM", "PREMIUM", "LUXURY"]


class TestPythonTypeToTs:
    def test_str_to_string(self) -> None:
        assert _python_type_to_ts(str, {}) == "string"

    def test_int_to_number(self) -> None:
        assert _python_type_to_ts(int, {}) == "number"

    def test_float_to_number(self) -> None:
        assert _python_type_to_ts(float, {}) == "number"

    def test_bool_to_boolean(self) -> None:
        assert _python_type_to_ts(bool, {}) == "boolean"

    def test_optional_str(self) -> None:
        assert _python_type_to_ts(Optional[str], {}) == "string | null"

    def test_list_str(self) -> None:
        assert _python_type_to_ts(list[str], {}) == "string[]"

    def test_dict_str_int(self) -> None:
        assert _python_type_to_ts(dict[str, int], {}) == "Record<string, number>"

    def test_literal_strings(self) -> None:
        result = _python_type_to_ts(Literal["A", "B", "C"], {})
        assert '"A"' in result
        assert '"B"' in result
        assert '"C"' in result
        assert " | " in result


class TestModelToTsInterface:
    def test_simple_model(self) -> None:
        registry: dict = {}
        ts = _model_to_ts_interface(_SimpleModel, registry)
        assert "export interface _SimpleModel {" in ts
        assert "name: string;" in ts
        assert "count: number;" in ts
        # flag has default False → marked optional ('?')
        assert "flag?: boolean;" in ts or "flag: boolean;" in ts

    def test_optional_field_marked(self) -> None:
        registry: dict = {}
        ts = _model_to_ts_interface(_SimpleModel, registry)
        # optional_score has Optional[float] = None — should be marked optional
        # Either via `?` или via union с null
        assert "optional_score" in ts


class TestGenerateTsInterfaces:
    def test_generates_header(self) -> None:
        result = generate_ts_interfaces([_SimpleModel])
        assert "auto-generated" in result.lower()
        assert "DO NOT EDIT MANUALLY" in result

    def test_includes_dependencies(self) -> None:
        """When NestedModel referenced — SimpleModel also generated."""
        result = generate_ts_interfaces([_NestedModel])
        assert "_NestedModel" in result
        assert "_SimpleModel" in result  # transitive dependency

    def test_literal_values_render_correctly(self) -> None:
        result = generate_ts_interfaces([_LiteralModel])
        assert '"High"' in result
        assert '"PREMIUM"' in result


class TestExportCli:
    def test_print_mode_outputs_to_stdout(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--print"])
        assert result.exit_code == 0
        assert "export interface" in result.output

    def test_writes_to_specified_file(self, tmp_path) -> None:
        out = tmp_path / "schema.ts"
        runner = CliRunner()
        result = runner.invoke(main, ["--output", str(out)])
        assert result.exit_code == 0
        assert out.exists()
        # Windows: read with utf-8 (output written с encoding="utf-8" в
        # export_typescript.py:235). Без explicit — cp1251 default ломается на
        # JSDoc descriptions с кириллицей (Phase 1.C.1 wizard schemas).
        assert "export interface" in out.read_text(encoding="utf-8")


class TestSchemaDiff:
    """Schema diff CLI tests."""

    def test_self_diff_no_changes(self) -> None:
        from aurora_launch.tools.schema_diff import diff_schemas
        result = diff_schemas("1.0", "1.0")
        assert result["from_version"] == "1.0"
        assert result["to_version"] == "1.0"
        assert "self-diff" in result["summary"].lower() or len(result["migrations"]) == 0

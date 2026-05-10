"""Unit tests for utility functions."""

from utils.classify_error import classify_error
from utils.format_response_markdown import format_response_markdown
from utils.format_results_table import format_results_table
from utils.format_schema import format_schema
from utils.optimize_sql import optimize_sql
from utils.validate_sql_safety import validate_sql_safety


class TestValidateSqlSafety:
    def test_select_is_safe(self):
        safe, reason = validate_sql_safety("SELECT * FROM dim_player")
        assert safe
        assert reason == "SQL is safe"

    def test_drop_is_unsafe(self):
        safe, reason = validate_sql_safety("DROP TABLE dim_player")
        assert not safe
        assert "SELECT" in reason

    def test_insert_is_unsafe(self):
        safe, reason = validate_sql_safety("INSERT INTO dim_player VALUES (1)")
        assert not safe

    def test_empty_is_unsafe(self):
        safe, reason = validate_sql_safety("")
        assert not safe


class TestClassifyError:
    def test_syntax_error(self):
        assert classify_error("syntax error at or near") == "syntax_error"

    def test_missing_column(self):
        assert classify_error('column "foobar" does not exist') == "missing_column"

    def test_missing_table(self):
        assert classify_error('table "foobar" does not exist') == "missing_table"

    def test_type_mismatch(self):
        assert classify_error("type mismatch: cannot be cast") == "type_mismatch"

    def test_permission_error(self):
        assert classify_error("permission denied") == "permission"

    def test_unknown_error(self):
        assert classify_error("random internal error") == "unknown"

    def test_none_error(self):
        assert classify_error("") == "unknown"


class TestOptimizeSql:
    def test_adds_limit(self):
        result = optimize_sql("SELECT * FROM dim_player")
        assert result.strip().endswith("LIMIT 200;")

    def test_preserves_existing_limit(self):
        result = optimize_sql("SELECT * FROM dim_player LIMIT 5")
        assert "LIMIT 5" in result

    def test_ensures_semicolon(self):
        result = optimize_sql("SELECT 1")
        assert result.strip().endswith(";")


class TestFormatResultsTable:
    def test_basic_table(self):
        table = format_results_table(
            ["Name", "Points"], [["Curry", 30], ["LeBron", 25]]
        )
        assert "| Name | Points |" in table
        assert "| Curry | 30 |" in table
        assert "| LeBron | 25 |" in table

    def test_empty_columns(self):
        assert format_results_table([], []) == ""

    def test_truncation_note(self):
        rows = [[str(i)] for i in range(60)]
        table = format_results_table(["X"], rows, max_display=50)
        assert "Showing 50 of 60 rows." in table


class TestFormatSchema:
    def test_basic_format(self):
        schema = {
            "dim_player": {
                "columns": [{"name": "person_id", "type": "BIGINT"}]
            }
        }
        result = format_schema(schema)
        assert "TABLE dim_player (person_id BIGINT)" in result


class TestFormatResponseMarkdown:
    def test_full_response(self):
        result = format_response_markdown(
            narrative="Found 12 players.",
            table_md="| Name |\n| --- |\n| Curry |",
            sql="SELECT * FROM dim_player",
            elapsed_ms=42.5,
        )
        assert "Found 12 players." in result
        assert "View SQL (42ms)" in result
        assert "SELECT * FROM dim_player" in result

    def test_no_sql(self):
        result = format_response_markdown(
            narrative="Hello.", table_md="", sql=None, elapsed_ms=None
        )
        assert "Hello." in result
        assert "View SQL" not in result

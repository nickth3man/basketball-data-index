"""Test that entry-point modules import correctly and edge cases in nodes."""

import os
from unittest.mock import patch

import pytest


class TestEntryPoints:
    def test_app_imports(self):
        with (
            patch.dict(
                os.environ, {"OPENROUTER_API_KEY": "test", "OPENROUTER_MODEL": "test"}
            ),
            patch("utils.get_full_schema.get_full_schema", return_value={}),
        ):
            import app

            assert app is not None

    def test_main_imports(self):
        with (
            patch.dict(
                os.environ, {"OPENROUTER_API_KEY": "test", "OPENROUTER_MODEL": "test"}
            ),
            patch("utils.get_full_schema.get_full_schema", return_value={}),
        ):
            import main

            assert main is not None


class TestSQLGeneratorSafetyCheck:
    def test_exec_raises_on_sql_with_embedded_ddl(self, mock_call_llm_structured):
        """SQL starting with SELECT but containing DDL should raise ValueError."""
        mock_call_llm_structured.return_value = {
            "thinking": "oops embedded drop",
            "sql": "SELECT * FROM t; DROP TABLE t",
        }
        from nodes import SQLGeneratorNode

        node = SQLGeneratorNode()
        prep_res = {
            "clean_message": "test",
            "schema_context": "",
            "query_plan": "",
            "history_context": "",
            "api_key": "k",
            "model": "m",
            "system_prompt": "",
            "execution_error": None,
            "error_type": None,
            "error_analysis": None,
            "schema_recheck": None,
        }
        with pytest.raises(ValueError, match="SQL safety check failed"):
            node.exec(prep_res)

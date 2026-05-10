"""Tests for YAML extraction in call_llm_structured (no API calls)."""

from utils.call_llm_structured import _extract_yaml_block, _rebuild_yaml


class TestYamlExtraction:
    def test_extract_from_code_fence(self):
        text = 'Here is the answer:\n```yaml\nkey: value\nfoo: bar\n```'
        result = _extract_yaml_block(text)
        assert result is not None
        assert "key: value" in result

    def test_extract_from_plain_fence(self):
        text = '```\nkey: value\n```'
        result = _extract_yaml_block(text)
        assert result is not None
        assert "key: value" in result

    def test_extract_no_fence_but_yaml(self):
        text = "some intro text\nclean_message: hello\nentities: []"
        result = _extract_yaml_block(text)
        assert result is not None
        assert "clean_message: hello" in result

    def test_extract_pure_yaml(self):
        text = "key: value\nnested:\n  sub: 42"
        result = _extract_yaml_block(text)
        assert result is not None
        assert "key: value" in result

    def test_rebuild_yaml_with_colons(self):
        text = (
            "thinking: The user question is not a date, you need to either: "
            "(1) add a table\nsql: SELECT 1"
        )
        result = _rebuild_yaml(text, ["thinking", "sql"])
        import yaml
        parsed = yaml.safe_load(result)
        assert isinstance(parsed, dict)
        assert "thinking" in parsed
        assert "sql" in parsed

    def test_rebuild_fallback_missing_fields(self):
        text = "just some random text without yaml keys"
        result = _rebuild_yaml(text, ["required_field"])
        assert result == text

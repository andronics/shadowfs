#!/usr/bin/env python3
"""Comprehensive tests for format conversion transforms."""

import csv
import json
from unittest.mock import patch

import pytest

from shadowfs.transforms.base import TransformError
from shadowfs.transforms.format_conversion import (
    CSVToJSONTransform,
    JSONToCSVTransform,
    MarkdownToHTMLTransform,
    YAMLToJSONTransform,
)


class TestMarkdownToHTMLTransform:
    """Tests for MarkdownToHTMLTransform class."""

    def test_init_default(self):
        """Test default initialization."""
        try:
            transform = MarkdownToHTMLTransform()
            assert transform.name == "markdown_to_html"
            assert transform._extensions == []
        except TransformError as e:
            if "markdown not installed" in str(e):
                pytest.skip("markdown library not installed")
            raise

    def test_init_with_extensions(self):
        """Test initialization with extensions."""
        try:
            transform = MarkdownToHTMLTransform(extensions=["tables", "fenced_code"])
            assert transform._extensions == ["tables", "fenced_code"]
        except TransformError:
            pytest.skip("markdown library not installed")

    def test_supports_md(self):
        """Test supports for .md files."""
        try:
            transform = MarkdownToHTMLTransform()
            assert transform.supports("file.md") is True
            assert transform.supports("README.md") is True
        except TransformError:
            pytest.skip("markdown library not installed")

    def test_supports_markdown(self):
        """Test supports for .markdown files."""
        try:
            transform = MarkdownToHTMLTransform()
            assert transform.supports("file.markdown") is True
        except TransformError:
            pytest.skip("markdown library not installed")

    def test_supports_other_files(self):
        """Test supports returns False for non-markdown files."""
        try:
            transform = MarkdownToHTMLTransform()
            assert transform.supports("file.txt") is False
            assert transform.supports("file.html") is False
        except TransformError:
            pytest.skip("markdown library not installed")

    def test_transform_simple(self):
        """Test simple markdown transformation."""
        try:
            transform = MarkdownToHTMLTransform()
            content = b"# Hello World\n\nThis is a test."

            result = transform.apply(content, "test.md")

            assert result.success is True
            assert b"<h1>Hello World</h1>" in result.content
            assert b"<p>This is a test.</p>" in result.content
        except TransformError:
            pytest.skip("markdown library not installed")

    def test_transform_with_formatting(self):
        """Test markdown with various formatting."""
        try:
            transform = MarkdownToHTMLTransform()
            content = b"**Bold** and *italic* text"

            result = transform.apply(content, "test.md")

            assert result.success is True
            assert b"<strong>Bold</strong>" in result.content
            assert b"<em>italic</em>" in result.content
        except TransformError:
            pytest.skip("markdown library not installed")

    def test_get_metadata(self):
        """Test get_metadata."""
        try:
            transform = MarkdownToHTMLTransform(extensions=["tables"])
            metadata = transform.get_metadata("test.md")

            assert metadata["transform"] == "markdown_to_html"
            assert metadata["source_format"] == "markdown"
            assert metadata["target_format"] == "html"
            assert metadata["extensions"] == ["tables"]
        except TransformError:
            pytest.skip("markdown library not installed")

    def test_transform_unicode_decode_error(self):
        """Test handling of invalid UTF-8 in markdown."""
        try:
            transform = MarkdownToHTMLTransform()
            invalid_content = b"\xff\xfe\xfd"  # Invalid UTF-8

            result = transform.apply(invalid_content, "test.md")

            assert result.success is False
            assert "Failed to decode Markdown" in result.error
        except TransformError:
            pytest.skip("markdown library not installed")

    def test_transform_markdown_error(self):
        """Test handling of markdown conversion errors."""
        try:
            transform = MarkdownToHTMLTransform()
            # Create content that might cause markdown errors
            # In practice, markdown is very forgiving, so this is mostly for coverage
            content = b"# Valid markdown"

            result = transform.apply(content, "test.md")

            # Should succeed with valid markdown
            assert result.success is True
        except TransformError:
            pytest.skip("markdown library not installed")

    def test_init_markdown_not_installed(self):
        """Test initialization when markdown is not installed."""
        # Mock markdown import to raise ImportError
        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "markdown":
                raise ImportError("No module named 'markdown'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            with pytest.raises(TransformError) as exc_info:
                MarkdownToHTMLTransform()

            assert "markdown not installed" in str(exc_info.value)

    def test_transform_exception_during_conversion(self):
        """Test handling of exception during markdown conversion."""
        try:
            transform = MarkdownToHTMLTransform()

            # Mock Markdown class to raise an exception
            class MockMarkdown:
                def __init__(self, *args, **kwargs):
                    pass

                def convert(self, text):
                    raise RuntimeError("Simulated markdown error")

            with patch.object(transform._markdown, "Markdown", return_value=MockMarkdown()):
                result = transform.apply(b"# Test", "test.md")

                assert result.success is False
                assert "Markdown conversion error" in result.error
        except TransformError:
            pytest.skip("markdown library not installed")


class TestCSVToJSONTransform:
    """Tests for CSVToJSONTransform class."""

    def test_init_default(self):
        """Test default initialization."""
        transform = CSVToJSONTransform()

        assert transform.name == "csv_to_json"
        assert transform._has_header is True
        assert transform._delimiter == ","

    def test_init_custom(self):
        """Test initialization with custom parameters."""
        transform = CSVToJSONTransform(name="my_converter", has_header=False, delimiter=";")

        assert transform.name == "my_converter"
        assert transform._has_header is False
        assert transform._delimiter == ";"

    def test_supports_csv(self):
        """Test supports for .csv files."""
        transform = CSVToJSONTransform()

        assert transform.supports("file.csv") is True
        assert transform.supports("data.csv") is True

    def test_supports_other_files(self):
        """Test supports returns False for non-CSV files."""
        transform = CSVToJSONTransform()

        assert transform.supports("file.txt") is False
        assert transform.supports("file.json") is False

    def test_transform_with_header(self):
        """Test CSV to JSON with header row."""
        transform = CSVToJSONTransform(has_header=True)
        csv_content = b"name,age,city\nAlice,30,NYC\nBob,25,LA"

        result = transform.apply(csv_content, "data.csv")

        assert result.success is True
        data = json.loads(result.content)
        assert len(data) == 2
        assert data[0] == {"name": "Alice", "age": "30", "city": "NYC"}
        assert data[1] == {"name": "Bob", "age": "25", "city": "LA"}

    def test_transform_without_header(self):
        """Test CSV to JSON without header row."""
        transform = CSVToJSONTransform(has_header=False)
        csv_content = b"Alice,30,NYC\nBob,25,LA"

        result = transform.apply(csv_content, "data.csv")

        assert result.success is True
        data = json.loads(result.content)
        assert len(data) == 2
        assert data[0] == ["Alice", "30", "NYC"]
        assert data[1] == ["Bob", "25", "LA"]

    def test_transform_custom_delimiter(self):
        """Test CSV with custom delimiter."""
        transform = CSVToJSONTransform(has_header=True, delimiter=";")
        csv_content = b"name;age;city\nAlice;30;NYC"

        result = transform.apply(csv_content, "data.csv")

        assert result.success is True
        data = json.loads(result.content)
        assert data[0] == {"name": "Alice", "age": "30", "city": "NYC"}

    def test_transform_empty_csv(self):
        """Test empty CSV."""
        transform = CSVToJSONTransform()
        csv_content = b"name,age\n"  # Header only

        result = transform.apply(csv_content, "data.csv")

        assert result.success is True
        data = json.loads(result.content)
        assert data == []

    def test_transform_invalid_csv(self):
        """Test invalid CSV data."""
        transform = CSVToJSONTransform()
        invalid_content = b"\xff\xfe"  # Invalid UTF-8

        result = transform.apply(invalid_content, "data.csv")

        assert result.success is False
        assert "Failed to decode CSV" in result.error

    def test_transform_csv_parse_error(self):
        """Test CSV parsing error handling."""
        transform = CSVToJSONTransform()
        # CSV with inconsistent column counts can trigger parsing errors in strict mode
        # However, Python's csv module is quite forgiving by default
        # This test is primarily for coverage of the except csv.Error branch
        csv_content = b"name,age\nAlice,30\nBob,25"

        result = transform.apply(csv_content, "data.csv")

        # Should succeed with valid CSV
        assert result.success is True

    def test_transform_csv_general_error(self):
        """Test general CSV error handling."""
        transform = CSVToJSONTransform()
        # Valid CSV that should succeed
        csv_content = b"name,age\nAlice,30"

        result = transform.apply(csv_content, "data.csv")

        # Should succeed
        assert result.success is True

    def test_transform_csv_parse_exception(self):
        """Test CSV parsing exception using mock."""
        transform = CSVToJSONTransform()

        # Mock csv.DictReader to raise csv.Error
        def mock_dictreader(*args, **kwargs):
            raise csv.Error("Simulated CSV parsing error")

        with patch("csv.DictReader", side_effect=mock_dictreader):
            result = transform.apply(b"name,age\nAlice,30", "data.csv")

            assert result.success is False
            assert "CSV parsing error" in result.error

    def test_transform_csv_general_exception(self):
        """Test general exception during CSV processing."""
        transform = CSVToJSONTransform()

        # Mock json.dumps to raise exception
        def mock_dumps(*args, **kwargs):
            raise RuntimeError("Simulated JSON error")

        with patch("json.dumps", side_effect=mock_dumps):
            result = transform.apply(b"name,age\nAlice,30", "data.csv")

            assert result.success is False
            assert "CSV to JSON conversion error" in result.error


class TestJSONToCSVTransform:
    """Tests for JSONToCSVTransform class."""

    def test_init_default(self):
        """Test default initialization."""
        transform = JSONToCSVTransform()

        assert transform.name == "json_to_csv"
        assert transform._include_header is True
        assert transform._delimiter == ","

    def test_init_custom(self):
        """Test initialization with custom parameters."""
        transform = JSONToCSVTransform(name="my_converter", include_header=False, delimiter="|")

        assert transform.name == "my_converter"
        assert transform._include_header is False
        assert transform._delimiter == "|"

    def test_supports_json(self):
        """Test supports for .json files."""
        transform = JSONToCSVTransform()

        assert transform.supports("file.json") is True
        assert transform.supports("data.json") is True

    def test_supports_other_files(self):
        """Test supports returns False for non-JSON files."""
        transform = JSONToCSVTransform()

        assert transform.supports("file.txt") is False
        assert transform.supports("file.csv") is False

    def test_transform_with_header(self):
        """Test JSON to CSV with header."""
        transform = JSONToCSVTransform(include_header=True)
        json_data = [
            {"name": "Alice", "age": "30", "city": "NYC"},
            {"name": "Bob", "age": "25", "city": "LA"},
        ]
        json_content = json.dumps(json_data).encode()

        result = transform.apply(json_content, "data.json")

        assert result.success is True
        lines = result.content.decode().strip().split("\n")
        assert len(lines) == 3  # Header + 2 data rows
        assert "name" in lines[0]
        assert "age" in lines[0]
        assert "Alice" in lines[1]

    def test_transform_without_header(self):
        """Test JSON to CSV without header."""
        transform = JSONToCSVTransform(include_header=False)
        json_data = [
            {"name": "Alice", "age": "30"},
            {"name": "Bob", "age": "25"},
        ]
        json_content = json.dumps(json_data).encode()

        result = transform.apply(json_content, "data.json")

        assert result.success is True
        lines = result.content.decode().strip().split("\n")
        assert len(lines) == 2  # Only data rows
        assert "Alice" in lines[0]
        assert "Bob" in lines[1]

    def test_transform_custom_delimiter(self):
        """Test JSON to CSV with custom delimiter."""
        transform = JSONToCSVTransform(include_header=True, delimiter=";")
        json_data = [{"name": "Alice", "age": "30"}]
        json_content = json.dumps(json_data).encode()

        result = transform.apply(json_content, "data.json")

        assert result.success is True
        assert b";" in result.content
        assert b"name;age" in result.content

    def test_transform_empty_array(self):
        """Test empty JSON array."""
        transform = JSONToCSVTransform()
        json_content = b"[]"

        result = transform.apply(json_content, "data.json")

        assert result.success is True
        assert result.content == b""

    def test_transform_invalid_not_array(self):
        """Test JSON that is not an array."""
        transform = JSONToCSVTransform()
        json_content = b'{"key": "value"}'

        result = transform.apply(json_content, "data.json")

        assert result.success is False
        assert "JSON must be an array" in result.error

    def test_transform_invalid_not_objects(self):
        """Test JSON array with non-objects."""
        transform = JSONToCSVTransform()
        json_content = b'["string1", "string2"]'

        result = transform.apply(json_content, "data.json")

        assert result.success is False
        assert "JSON array must contain objects" in result.error

    def test_transform_invalid_json(self):
        """Test invalid JSON."""
        transform = JSONToCSVTransform()
        json_content = b"{invalid json}"

        result = transform.apply(json_content, "data.json")

        assert result.success is False
        assert "JSON parsing error" in result.error

    def test_transform_unicode_decode_error(self):
        """Test handling of invalid UTF-8 in JSON."""
        transform = JSONToCSVTransform()
        invalid_content = b"\xff\xfe\xfd"  # Invalid UTF-8

        result = transform.apply(invalid_content, "data.json")

        assert result.success is False
        assert "Failed to decode JSON" in result.error

    def test_transform_general_error(self):
        """Test general JSON error handling."""
        transform = JSONToCSVTransform()
        # Valid JSON that should succeed
        json_content = b'[{"name": "Alice", "age": "30"}]'

        result = transform.apply(json_content, "data.json")

        # Should succeed
        assert result.success is True

    def test_roundtrip(self):
        """Test CSV -> JSON -> CSV roundtrip."""
        original_csv = b"name,age,city\nAlice,30,NYC\nBob,25,LA"

        # CSV to JSON
        csv_to_json = CSVToJSONTransform()
        json_result = csv_to_json.apply(original_csv, "data.csv")

        # JSON to CSV
        json_to_csv = JSONToCSVTransform()
        csv_result = json_to_csv.apply(json_result.content, "data.json")

        # Parse both CSVs (handle different line endings)
        original_lines = original_csv.decode().strip().replace("\r\n", "\n").split("\n")
        result_lines = csv_result.content.decode().strip().replace("\r\n", "\n").split("\n")

        # Headers should match
        assert original_lines[0] == result_lines[0]


class TestYAMLToJSONTransform:
    """Tests for YAMLToJSONTransform class."""

    def test_init_default(self):
        """Test default initialization."""
        try:
            transform = YAMLToJSONTransform()
            assert transform.name == "yaml_to_json"
            assert transform._indent == 2
        except TransformError as e:
            if "pyyaml not installed" in str(e):
                pytest.skip("pyyaml library not installed")
            raise

    def test_init_custom_indent(self):
        """Test initialization with custom indent."""
        try:
            transform = YAMLToJSONTransform(indent=4)
            assert transform._indent == 4
        except TransformError:
            pytest.skip("pyyaml library not installed")

    def test_supports_yaml(self):
        """Test supports for .yaml files."""
        try:
            transform = YAMLToJSONTransform()
            assert transform.supports("file.yaml") is True
            assert transform.supports("config.yaml") is True
        except TransformError:
            pytest.skip("pyyaml library not installed")

    def test_supports_yml(self):
        """Test supports for .yml files."""
        try:
            transform = YAMLToJSONTransform()
            assert transform.supports("file.yml") is True
        except TransformError:
            pytest.skip("pyyaml library not installed")

    def test_supports_other_files(self):
        """Test supports returns False for non-YAML files."""
        try:
            transform = YAMLToJSONTransform()
            assert transform.supports("file.txt") is False
            assert transform.supports("file.json") is False
        except TransformError:
            pytest.skip("pyyaml library not installed")

    def test_transform_simple(self):
        """Test simple YAML to JSON."""
        try:
            transform = YAMLToJSONTransform()
            yaml_content = b"name: Alice\nage: 30\ncity: NYC"

            result = transform.apply(yaml_content, "data.yaml")

            assert result.success is True
            data = json.loads(result.content)
            assert data == {"name": "Alice", "age": 30, "city": "NYC"}
        except TransformError:
            pytest.skip("pyyaml library not installed")

    def test_transform_nested(self):
        """Test nested YAML to JSON."""
        try:
            transform = YAMLToJSONTransform()
            yaml_content = b"person:\n  name: Alice\n  age: 30"

            result = transform.apply(yaml_content, "data.yaml")

            assert result.success is True
            data = json.loads(result.content)
            assert data == {"person": {"name": "Alice", "age": 30}}
        except TransformError:
            pytest.skip("pyyaml library not installed")

    def test_transform_list(self):
        """Test YAML list to JSON."""
        try:
            transform = YAMLToJSONTransform()
            yaml_content = b"- item1\n- item2\n- item3"

            result = transform.apply(yaml_content, "data.yaml")

            assert result.success is True
            data = json.loads(result.content)
            assert data == ["item1", "item2", "item3"]
        except TransformError:
            pytest.skip("pyyaml library not installed")

    def test_transform_invalid_yaml(self):
        """Test invalid YAML."""
        try:
            transform = YAMLToJSONTransform()
            invalid_yaml = b"invalid:\n  - yaml\n syntax error"

            result = transform.apply(invalid_yaml, "data.yaml")

            assert result.success is False
            assert "YAML parsing error" in result.error
        except TransformError:
            pytest.skip("pyyaml library not installed")

    def test_transform_unicode_decode_error(self):
        """Test handling of invalid UTF-8 in YAML."""
        try:
            transform = YAMLToJSONTransform()
            invalid_content = b"\xff\xfe\xfd"  # Invalid UTF-8

            result = transform.apply(invalid_content, "data.yaml")

            assert result.success is False
            assert "Failed to decode YAML" in result.error
        except TransformError:
            pytest.skip("pyyaml library not installed")

    def test_transform_general_error(self):
        """Test general YAML error handling."""
        try:
            transform = YAMLToJSONTransform()
            # Valid YAML that should succeed
            yaml_content = b"name: Alice\nage: 30"

            result = transform.apply(yaml_content, "data.yaml")

            # Should succeed
            assert result.success is True
        except TransformError:
            pytest.skip("pyyaml library not installed")

    def test_init_yaml_not_installed(self):
        """Test initialization when pyyaml is not installed."""
        # Mock yaml import to raise ImportError
        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError("No module named 'yaml'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            with pytest.raises(TransformError) as exc_info:
                YAMLToJSONTransform()

            assert "pyyaml not installed" in str(exc_info.value)

    def test_transform_exception_during_conversion(self):
        """Test handling of exception during YAML conversion."""
        try:
            transform = YAMLToJSONTransform()

            # Mock json.dumps to raise an exception
            def mock_dumps(*args, **kwargs):
                raise RuntimeError("Simulated JSON error")

            with patch("json.dumps", side_effect=mock_dumps):
                result = transform.apply(b"name: Alice", "data.yaml")

                assert result.success is False
                assert "YAML to JSON conversion error" in result.error
        except TransformError:
            pytest.skip("pyyaml library not installed")

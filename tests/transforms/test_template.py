#!/usr/bin/env python3
"""Comprehensive tests for TemplateTransform."""

from unittest.mock import patch

import pytest

from shadowfs.transforms.base import TransformError
from shadowfs.transforms.template import TemplateTransform


class TestTemplateTransform:
    """Tests for TemplateTransform class."""

    def test_init_default(self):
        """Test default initialization."""
        try:
            transform = TemplateTransform()

            assert transform.name == "template"
            assert transform._context == {}
            assert transform._patterns == ["*.j2", "*.jinja2", "*.tmpl"]
            assert transform._env is None  # Lazy creation
        except TransformError as e:
            if "jinja2 not installed" in str(e):
                pytest.skip("jinja2 library not installed")
            raise

    def test_init_with_context(self):
        """Test initialization with context."""
        try:
            context = {"name": "World", "count": 42}
            transform = TemplateTransform(context=context)

            assert transform._context == context
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_init_with_patterns(self):
        """Test initialization with custom patterns."""
        try:
            patterns = ["*.template", "*.tpl"]
            transform = TemplateTransform(patterns=patterns)

            assert transform._patterns == patterns
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_init_with_jinja_options(self):
        """Test initialization with Jinja2 options."""
        try:
            transform = TemplateTransform(
                trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True
            )

            assert transform._jinja_options["trim_blocks"] is True
            assert transform._jinja_options["lstrip_blocks"] is True
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_init_jinja2_not_installed(self):
        """Test initialization when jinja2 is not installed."""
        # Mock jinja2 import to raise ImportError
        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "jinja2":
                raise ImportError("No module named 'jinja2'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            with pytest.raises(TransformError) as exc_info:
                TemplateTransform()

            assert "jinja2 not installed" in str(exc_info.value)

    def test_supports_j2(self):
        """Test supports for .j2 files."""
        try:
            transform = TemplateTransform()

            assert transform.supports("template.j2") is True
            assert transform.supports("path/to/config.j2") is True
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_supports_jinja2(self):
        """Test supports for .jinja2 files."""
        try:
            transform = TemplateTransform()

            assert transform.supports("template.jinja2") is True
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_supports_tmpl(self):
        """Test supports for .tmpl files."""
        try:
            transform = TemplateTransform()

            assert transform.supports("template.tmpl") is True
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_supports_other_files(self):
        """Test supports returns False for non-template files."""
        try:
            transform = TemplateTransform()

            assert transform.supports("file.txt") is False
            assert transform.supports("file.py") is False
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_supports_custom_patterns(self):
        """Test supports with custom patterns."""
        try:
            transform = TemplateTransform(patterns=["*.template"])

            assert transform.supports("file.template") is True
            assert transform.supports("file.j2") is False
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_transform_simple(self):
        """Test simple template rendering."""
        try:
            context = {"name": "World"}
            transform = TemplateTransform(context=context)

            content = b"Hello {{ name }}!"
            result = transform.apply(content, "template.j2")

            assert result.success is True
            assert result.content == b"Hello World!"
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_transform_with_variables(self):
        """Test template with multiple variables."""
        try:
            context = {"name": "Alice", "age": 30, "city": "NYC"}
            transform = TemplateTransform(context=context)

            content = b"{{ name }} is {{ age }} years old and lives in {{ city }}."
            result = transform.apply(content, "template.j2")

            assert result.success is True
            assert result.content == b"Alice is 30 years old and lives in NYC."
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_transform_with_loop(self):
        """Test template with loops."""
        try:
            context = {"items": ["apple", "banana", "cherry"]}
            transform = TemplateTransform(context=context)

            content = b"{% for item in items %}{{ item }}\n{% endfor %}"
            result = transform.apply(content, "template.j2")

            assert result.success is True
            assert b"apple" in result.content
            assert b"banana" in result.content
            assert b"cherry" in result.content
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_transform_with_conditional(self):
        """Test template with conditionals."""
        try:
            context = {"show_message": True, "message": "Hello"}
            transform = TemplateTransform(context=context)

            content = b"{% if show_message %}{{ message }}{% endif %}"
            result = transform.apply(content, "template.j2")

            assert result.success is True
            assert result.content == b"Hello"
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_transform_with_metadata(self):
        """Test template with metadata merged into context."""
        try:
            context = {"base_key": "base_value"}
            transform = TemplateTransform(context=context)

            content = b"Base: {{ base_key }}, Meta: {{ meta_key }}"
            metadata = {"meta_key": "meta_value"}
            result = transform.apply(content, "template.j2", metadata=metadata)

            assert result.success is True
            assert result.content == b"Base: base_value, Meta: meta_value"
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_transform_metadata_override(self):
        """Test that metadata overrides context."""
        try:
            context = {"key": "original"}
            transform = TemplateTransform(context=context)

            content = b"Value: {{ key }}"
            metadata = {"key": "overridden"}
            result = transform.apply(content, "template.j2", metadata=metadata)

            assert result.success is True
            assert result.content == b"Value: overridden"
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_transform_unicode_decode_error(self):
        """Test handling of invalid UTF-8."""
        try:
            transform = TemplateTransform()
            invalid_content = b"\xff\xfe\xfd"  # Invalid UTF-8

            result = transform.apply(invalid_content, "template.j2")

            assert result.success is False
            assert "Failed to decode template" in result.error
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_transform_template_error(self):
        """Test handling of Jinja2 template errors."""
        try:
            transform = TemplateTransform()

            # Template with undefined variable
            content = b"{{ undefined_variable }}"
            result = transform.apply(content, "template.j2")

            # Should succeed with empty value (Jinja2 default behavior)
            # Or fail if strict mode is enabled
            assert result.success is True or "Template error" in result.error
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_transform_template_syntax_error(self):
        """Test handling of template syntax errors."""
        try:
            transform = TemplateTransform()

            # Template with syntax error
            content = b"{% if missing_endif %}"
            result = transform.apply(content, "template.j2")

            assert result.success is False
            assert "Template error" in result.error
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_transform_general_exception(self):
        """Test handling of general exceptions."""
        try:
            transform = TemplateTransform()

            # Mock template.render to raise exception
            def mock_render(*args, **kwargs):
                raise RuntimeError("Simulated render error")

            # Create environment first
            env = transform._get_environment()

            with patch.object(env, "from_string") as mock_from_string:
                mock_template = mock_from_string.return_value
                mock_template.render.side_effect = mock_render

                result = transform.apply(b"{{ test }}", "template.j2")

                assert result.success is False
                assert "Unexpected error" in result.error
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_get_environment_lazy_creation(self):
        """Test that environment is created lazily."""
        try:
            transform = TemplateTransform()

            assert transform._env is None

            env = transform._get_environment()
            assert env is not None
            assert transform._env is not None

            # Second call returns same environment
            env2 = transform._get_environment()
            assert env2 is env
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_set_context(self):
        """Test set_context replaces context."""
        try:
            transform = TemplateTransform(context={"old": "value"})

            new_context = {"new": "value"}
            transform.set_context(new_context)

            assert transform._context == new_context
            assert "old" not in transform._context
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_update_context(self):
        """Test update_context merges context."""
        try:
            transform = TemplateTransform(context={"key1": "value1"})

            transform.update_context(key2="value2", key3="value3")

            assert transform._context == {"key1": "value1", "key2": "value2", "key3": "value3"}
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_update_context_override(self):
        """Test update_context can override existing keys."""
        try:
            transform = TemplateTransform(context={"key": "old"})

            transform.update_context(key="new")

            assert transform._context["key"] == "new"
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_get_metadata(self):
        """Test get_metadata."""
        try:
            context = {"var1": "value1", "var2": "value2"}
            transform = TemplateTransform(name="my_template", context=context)

            metadata = transform.get_metadata("template.j2")

            assert metadata["transform"] == "my_template"
            assert metadata["template_engine"] == "jinja2"
            assert set(metadata["context_keys"]) == {"var1", "var2"}
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_jinja_options_applied(self):
        """Test that Jinja2 options are applied to environment."""
        try:
            transform = TemplateTransform(trim_blocks=True, lstrip_blocks=True)

            env = transform._get_environment()

            assert env.trim_blocks is True
            assert env.lstrip_blocks is True
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_empty_template(self):
        """Test rendering empty template."""
        try:
            transform = TemplateTransform()

            result = transform.apply(b"", "template.j2")

            assert result.success is True
            assert result.content == b""
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_template_with_filters(self):
        """Test template with Jinja2 filters."""
        try:
            context = {"name": "alice"}
            transform = TemplateTransform(context=context)

            content = b"Hello {{ name|upper }}!"
            result = transform.apply(content, "template.j2")

            assert result.success is True
            assert result.content == b"Hello ALICE!"
        except TransformError:
            pytest.skip("jinja2 library not installed")

    def test_template_with_whitespace_control(self):
        """Test template with whitespace control."""
        try:
            transform = TemplateTransform(trim_blocks=True, lstrip_blocks=True)

            content = b"{% if True %}\nTest\n{% endif %}"
            result = transform.apply(content, "template.j2")

            assert result.success is True
            # With trim_blocks and lstrip_blocks, whitespace should be controlled
            assert b"Test" in result.content
        except TransformError:
            pytest.skip("jinja2 library not installed")

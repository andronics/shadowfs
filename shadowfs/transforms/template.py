#!/usr/bin/env python3
"""Template transformation using Jinja2.

This module provides template expansion for files:
- Jinja2 template rendering
- Variable substitution
- Context from metadata
- Safe template evaluation

Example:
    >>> transform = TemplateTransform(context={"name": "World"})
    >>> result = transform.apply(b"Hello {{ name }}!", "template.j2")
    >>> result.content
    b'Hello World!'
"""

from typing import Any, Dict, Optional

from shadowfs.transforms.base import Transform, TransformError


class TemplateTransform(Transform):
    """Transform for Jinja2 template expansion.

    Renders Jinja2 templates with provided context variables.
    """

    def __init__(
        self,
        name: str = "template",
        context: Optional[Dict[str, Any]] = None,
        patterns: Optional[list] = None,
        **kwargs,
    ):
        """Initialize template transform.

        Args:
            name: Transform name
            context: Template context variables
            patterns: File patterns to match (default: *.j2, *.jinja2)
            **kwargs: Additional Jinja2 environment options
        """
        super().__init__(name=name)
        self._context = context or {}
        self._patterns = patterns or ["*.j2", "*.jinja2", "*.tmpl"]
        self._jinja_options = kwargs

        # Lazy import jinja2
        try:
            import jinja2

            self._jinja2 = jinja2
            self._env = None  # Create environment on first use
        except ImportError:
            raise TransformError(
                "jinja2 not installed. Install with: pip install jinja2",
                transform_name=name,
            )

    def _get_environment(self):
        """Get or create Jinja2 environment.

        Returns:
            Jinja2 Environment
        """
        if self._env is None:
            self._env = self._jinja2.Environment(**self._jinja_options)
        return self._env

    def supports(self, path: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Check if path matches template patterns.

        Args:
            path: File path
            metadata: Optional metadata

        Returns:
            True if path should be templated
        """
        import fnmatch

        for pattern in self._patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
        return False

    def transform(
        self, content: bytes, path: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """Render Jinja2 template.

        Args:
            content: Template content
            path: File path
            metadata: Optional metadata (merged into context)

        Returns:
            Rendered content

        Raises:
            TransformError: If template rendering fails
        """
        try:
            # Decode content
            template_str = content.decode("utf-8")

            # Build context
            context = self._context.copy()
            if metadata:
                context.update(metadata)

            # Render template
            env = self._get_environment()
            template = env.from_string(template_str)
            rendered = template.render(**context)

            return rendered.encode("utf-8")

        except UnicodeDecodeError as e:
            raise TransformError(f"Failed to decode template: {e}", self.name)
        except self._jinja2.TemplateError as e:
            raise TransformError(f"Template error: {e}", self.name)
        except Exception as e:
            raise TransformError(f"Unexpected error: {e}", self.name)

    def set_context(self, context: Dict[str, Any]) -> None:
        """Update template context.

        Args:
            context: New context variables
        """
        self._context = context

    def update_context(self, **kwargs) -> None:
        """Update template context with keyword arguments.

        Args:
            **kwargs: Context variables to update
        """
        self._context.update(kwargs)

    def get_metadata(
        self, path: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get transform metadata.

        Args:
            path: File path
            metadata: Input metadata

        Returns:
            Metadata with template info
        """
        return {
            "transform": self.name,
            "template_engine": "jinja2",
            "context_keys": list(self._context.keys()),
        }

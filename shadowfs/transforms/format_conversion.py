#!/usr/bin/env python3
"""Format conversion transformations.

This module provides format conversion transforms:
- Markdown to HTML
- CSV to JSON
- JSON to CSV
- YAML to JSON
- Extensible converter registry

Example:
    >>> transform = MarkdownToHTMLTransform()
    >>> result = transform.apply(b"# Hello\\nWorld", "README.md")
"""

import csv
import io
import json
from typing import Any, Dict, List, Optional

from shadowfs.transforms.base import Transform, TransformError


class MarkdownToHTMLTransform(Transform):
    """Convert Markdown to HTML.

    Uses the markdown library for conversion.
    """

    def __init__(
        self,
        name: str = "markdown_to_html",
        extensions: Optional[List[str]] = None,
        **kwargs,
    ):
        """Initialize Markdown to HTML transform.

        Args:
            name: Transform name
            extensions: Markdown extensions to enable
            **kwargs: Additional markdown options
        """
        super().__init__(name=name)
        self._extensions = extensions or []
        self._markdown_options = kwargs

        # Lazy import markdown
        try:
            import markdown

            self._markdown = markdown
        except ImportError:
            raise TransformError(
                "markdown not installed. Install with: pip install markdown",
                transform_name=name,
            )

    def supports(self, path: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Check if file is Markdown.

        Args:
            path: File path
            metadata: Optional metadata

        Returns:
            True for .md, .markdown files
        """
        return path.endswith((".md", ".markdown"))

    def transform(
        self, content: bytes, path: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """Convert Markdown to HTML.

        Args:
            content: Markdown content
            path: File path
            metadata: Optional metadata

        Returns:
            HTML content

        Raises:
            TransformError: If conversion fails
        """
        try:
            # Decode content
            md_text = content.decode("utf-8")

            # Convert to HTML
            md = self._markdown.Markdown(
                extensions=self._extensions, **self._markdown_options
            )
            html = md.convert(md_text)

            return html.encode("utf-8")

        except UnicodeDecodeError as e:
            raise TransformError(f"Failed to decode Markdown: {e}", self.name)
        except Exception as e:
            raise TransformError(f"Markdown conversion error: {e}", self.name)

    def get_metadata(
        self, path: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get transform metadata.

        Args:
            path: File path
            metadata: Input metadata

        Returns:
            Metadata with conversion info
        """
        return {
            "transform": self.name,
            "source_format": "markdown",
            "target_format": "html",
            "extensions": self._extensions,
        }


class CSVToJSONTransform(Transform):
    """Convert CSV to JSON.

    Converts CSV rows to JSON array of objects.
    """

    def __init__(
        self,
        name: str = "csv_to_json",
        has_header: bool = True,
        delimiter: str = ",",
        **kwargs,
    ):
        """Initialize CSV to JSON transform.

        Args:
            name: Transform name
            has_header: CSV has header row
            delimiter: CSV delimiter
            **kwargs: Additional csv.DictReader options
        """
        super().__init__(name=name)
        self._has_header = has_header
        self._delimiter = delimiter
        self._csv_options = kwargs

    def supports(self, path: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Check if file is CSV.

        Args:
            path: File path
            metadata: Optional metadata

        Returns:
            True for .csv files
        """
        return path.endswith(".csv")

    def transform(
        self, content: bytes, path: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """Convert CSV to JSON.

        Args:
            content: CSV content
            path: File path
            metadata: Optional metadata

        Returns:
            JSON content

        Raises:
            TransformError: If conversion fails
        """
        try:
            # Decode content
            csv_text = content.decode("utf-8")

            # Parse CSV
            csv_file = io.StringIO(csv_text)

            if self._has_header:
                reader = csv.DictReader(
                    csv_file, delimiter=self._delimiter, **self._csv_options
                )
                rows = list(reader)
            else:
                reader = csv.reader(
                    csv_file, delimiter=self._delimiter, **self._csv_options
                )
                rows = [list(row) for row in reader]

            # Convert to JSON
            json_text = json.dumps(rows, indent=2)

            return json_text.encode("utf-8")

        except UnicodeDecodeError as e:
            raise TransformError(f"Failed to decode CSV: {e}", self.name)
        except csv.Error as e:
            raise TransformError(f"CSV parsing error: {e}", self.name)
        except Exception as e:
            raise TransformError(f"CSV to JSON conversion error: {e}", self.name)


class JSONToCSVTransform(Transform):
    """Convert JSON to CSV.

    Converts JSON array of objects to CSV.
    """

    def __init__(
        self,
        name: str = "json_to_csv",
        include_header: bool = True,
        delimiter: str = ",",
        **kwargs,
    ):
        """Initialize JSON to CSV transform.

        Args:
            name: Transform name
            include_header: Include CSV header row
            delimiter: CSV delimiter
            **kwargs: Additional csv.DictWriter options
        """
        super().__init__(name=name)
        self._include_header = include_header
        self._delimiter = delimiter
        self._csv_options = kwargs

    def supports(self, path: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Check if file is JSON.

        Args:
            path: File path
            metadata: Optional metadata

        Returns:
            True for .json files
        """
        return path.endswith(".json")

    def transform(
        self, content: bytes, path: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """Convert JSON to CSV.

        Args:
            content: JSON content
            path: File path
            metadata: Optional metadata

        Returns:
            CSV content

        Raises:
            TransformError: If conversion fails
        """
        try:
            # Decode and parse JSON
            json_text = content.decode("utf-8")
            data = json.loads(json_text)

            # Validate data is list of dicts
            if not isinstance(data, list):
                raise TransformError("JSON must be an array", self.name)

            if not data:
                return b""

            if not isinstance(data[0], dict):
                raise TransformError("JSON array must contain objects", self.name)

            # Write CSV
            output = io.StringIO()
            fieldnames = data[0].keys()
            writer = csv.DictWriter(
                output, fieldnames=fieldnames, delimiter=self._delimiter, **self._csv_options
            )

            if self._include_header:
                writer.writeheader()

            writer.writerows(data)

            return output.getvalue().encode("utf-8")

        except UnicodeDecodeError as e:
            raise TransformError(f"Failed to decode JSON: {e}", self.name)
        except json.JSONDecodeError as e:
            raise TransformError(f"JSON parsing error: {e}", self.name)
        except Exception as e:
            raise TransformError(f"JSON to CSV conversion error: {e}", self.name)


class YAMLToJSONTransform(Transform):
    """Convert YAML to JSON.

    Parses YAML and outputs formatted JSON.
    """

    def __init__(self, name: str = "yaml_to_json", indent: int = 2):
        """Initialize YAML to JSON transform.

        Args:
            name: Transform name
            indent: JSON indentation
        """
        super().__init__(name=name)
        self._indent = indent

        # Lazy import yaml
        try:
            import yaml

            self._yaml = yaml
        except ImportError:
            raise TransformError(
                "pyyaml not installed. Install with: pip install pyyaml",
                transform_name=name,
            )

    def supports(self, path: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Check if file is YAML.

        Args:
            path: File path
            metadata: Optional metadata

        Returns:
            True for .yaml, .yml files
        """
        return path.endswith((".yaml", ".yml"))

    def transform(
        self, content: bytes, path: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """Convert YAML to JSON.

        Args:
            content: YAML content
            path: File path
            metadata: Optional metadata

        Returns:
            JSON content

        Raises:
            TransformError: If conversion fails
        """
        try:
            # Decode and parse YAML
            yaml_text = content.decode("utf-8")
            data = self._yaml.safe_load(yaml_text)

            # Convert to JSON
            json_text = json.dumps(data, indent=self._indent)

            return json_text.encode("utf-8")

        except UnicodeDecodeError as e:
            raise TransformError(f"Failed to decode YAML: {e}", self.name)
        except self._yaml.YAMLError as e:
            raise TransformError(f"YAML parsing error: {e}", self.name)
        except Exception as e:
            raise TransformError(f"YAML to JSON conversion error: {e}", self.name)

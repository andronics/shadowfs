"""ShadowFS Transforms - Content transformation system.

This module provides content transformation capabilities:
- TransformPipeline: Chain multiple transforms together
- Base transform classes and types
- Template transformation (Jinja2)
- Compression (gzip, bz2, lzma)
- Format conversion (Markdown, CSV, JSON, YAML)
"""

from .base import Transform, TransformError, TransformResult, TransformType
from .compression import (
    AutoDecompressTransform,
    CompressionAlgorithm,
    CompressionMode,
    CompressionTransform,
)
from .format_conversion import (
    CSVToJSONTransform,
    JSONToCSVTransform,
    MarkdownToHTMLTransform,
    YAMLToJSONTransform,
)
from .pipeline import TransformPipeline
from .template import TemplateTransform

__all__ = [
    # Pipeline
    "TransformPipeline",
    # Base classes
    "Transform",
    "TransformResult",
    "TransformError",
    "TransformType",
    # Template
    "TemplateTransform",
    # Compression
    "CompressionTransform",
    "CompressionAlgorithm",
    "CompressionMode",
    "AutoDecompressTransform",
    # Format conversion
    "MarkdownToHTMLTransform",
    "CSVToJSONTransform",
    "JSONToCSVTransform",
    "YAMLToJSONTransform",
]

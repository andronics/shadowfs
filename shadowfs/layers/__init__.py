"""
ShadowFS Layers - Virtual filesystem organization.

This package provides layer functionality for creating multiple
organizational views over the same set of files without duplication.

Public API:
-----------

Base Classes:
    FileInfo: Immutable file metadata container
    Layer: Abstract base class for all layers

Layer Implementations:
    ClassifierLayer: Organize files by property-based classification
    DateLayer: Organize files by date in YYYY/MM/DD hierarchy
    TagLayer: Organize files by metadata tags
    HierarchicalLayer: Multi-level hierarchical organization

Manager:
    LayerManager: Central coordinator for all layers
    LayerFactory: Factory functions for common layer configurations

Built-in Utilities:
    ClassifierBuiltins: Built-in classifiers for ClassifierLayer
    HierarchicalBuiltins: Built-in classifiers for HierarchicalLayer
    TagExtractors: Built-in tag extractors for TagLayer

Usage Example:
--------------

    from shadowfs.layers import (
        LayerManager,
        LayerFactory,
    )

    # Create manager
    manager = LayerManager(["/data/projects"])

    # Add layers using factory
    manager.add_layer(LayerFactory.create_extension_layer("by-type"))
    manager.add_layer(LayerFactory.create_date_layer("by-date"))

    # Scan and index
    manager.scan_sources()
    manager.rebuild_indexes()

    # Resolve virtual paths
    real_path = manager.resolve_path("by-type/python/file.py")

    # List virtual directories
    types = manager.list_directory("by-type")
"""

# Base classes
from shadowfs.layers.base import FileInfo, Layer

# Layer implementations
from shadowfs.layers.classifier import BuiltinClassifiers as ClassifierBuiltins
from shadowfs.layers.classifier import ClassifierLayer
from shadowfs.layers.date import DateLayer
from shadowfs.layers.hierarchical import BuiltinClassifiers as HierarchicalBuiltins
from shadowfs.layers.hierarchical import HierarchicalLayer
from shadowfs.layers.manager import LayerFactory, LayerManager
from shadowfs.layers.tag import BuiltinExtractors as TagExtractors
from shadowfs.layers.tag import TagLayer

__all__ = [
    # Base classes
    "FileInfo",
    "Layer",
    # Layer implementations
    "ClassifierLayer",
    "DateLayer",
    "TagLayer",
    "HierarchicalLayer",
    # Manager and factory
    "LayerManager",
    "LayerFactory",
    # Built-in utilities
    "ClassifierBuiltins",
    "HierarchicalBuiltins",
    "TagExtractors",
]

# Version info
__version__ = "1.0.0"

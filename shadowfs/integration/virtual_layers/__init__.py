"""
ShadowFS Virtual Layers - Virtual filesystem organization.

This package provides virtual layer functionality for creating multiple
organizational views over the same set of files without duplication.

Public API:
-----------

Base Classes:
    FileInfo: Immutable file metadata container
    VirtualLayer: Abstract base class for all virtual layers

Layer Implementations:
    ClassifierLayer: Organize files by property-based classification
    DateLayer: Organize files by date in YYYY/MM/DD hierarchy
    TagLayer: Organize files by metadata tags
    HierarchicalLayer: Multi-level hierarchical organization

Manager:
    VirtualLayerManager: Central coordinator for all virtual layers
    LayerFactory: Factory functions for common layer configurations

Built-in Utilities:
    ClassifierBuiltins: Built-in classifiers for ClassifierLayer
    HierarchicalBuiltins: Built-in classifiers for HierarchicalLayer
    TagExtractors: Built-in tag extractors for TagLayer

Usage Example:
--------------

    from shadowfs.integration.virtual_layers import (
        VirtualLayerManager,
        LayerFactory,
    )

    # Create manager
    manager = VirtualLayerManager(["/data/projects"])

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
from shadowfs.integration.virtual_layers.base import FileInfo, VirtualLayer

# Layer implementations
from shadowfs.integration.virtual_layers.classifier_layer import (
    BuiltinClassifiers as ClassifierBuiltins,
)
from shadowfs.integration.virtual_layers.classifier_layer import ClassifierLayer
from shadowfs.integration.virtual_layers.date_layer import DateLayer
from shadowfs.integration.virtual_layers.hierarchical_layer import (
    BuiltinClassifiers as HierarchicalBuiltins,
)
from shadowfs.integration.virtual_layers.hierarchical_layer import HierarchicalLayer
from shadowfs.integration.virtual_layers.manager import LayerFactory, VirtualLayerManager
from shadowfs.integration.virtual_layers.tag_layer import BuiltinExtractors as TagExtractors
from shadowfs.integration.virtual_layers.tag_layer import TagLayer

__all__ = [
    # Base classes
    "FileInfo",
    "VirtualLayer",
    # Layer implementations
    "ClassifierLayer",
    "DateLayer",
    "TagLayer",
    "HierarchicalLayer",
    # Manager and factory
    "VirtualLayerManager",
    "LayerFactory",
    # Built-in utilities
    "ClassifierBuiltins",
    "HierarchicalBuiltins",
    "TagExtractors",
]

# Version info
__version__ = "1.0.0"

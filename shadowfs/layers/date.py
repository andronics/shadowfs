"""
ShadowFS Virtual Layers: Date Layer.

This module provides date-based virtual layers that organize files
by timestamps in a hierarchical YYYY/MM/DD structure.

Example structure:
    by-date/
        2024/
            11/
                12/
                    document.pdf
                    photo.jpg
            10/
                15/
                    report.txt
        2023/
            12/
                25/
                    holiday.jpg
"""

from datetime import datetime
from typing import Dict, List, Literal, Optional

from shadowfs.layers.base import FileInfo, Layer

DateField = Literal["mtime", "ctime", "atime"]


class DateLayer(Layer):
    """
    Virtual layer that organizes files by date in YYYY/MM/DD hierarchy.

    Files are organized into a 3-level date hierarchy based on a
    configurable timestamp field (mtime, ctime, or atime).

    Attributes:
        name: Layer name (used as root directory)
        date_field: Which timestamp to use ("mtime", "ctime", or "atime")
        index: Nested dictionary mapping year → month → day → list of files
    """

    def __init__(self, name: str, date_field: DateField = "mtime"):
        """
        Initialize the date layer.

        Args:
            name: Layer name (e.g., "by-date", "by-modified")
            date_field: Timestamp field to use for organization
                       - "mtime": modification time (default)
                       - "ctime": creation/status change time
                       - "atime": access time
        """
        super().__init__(name)
        self.date_field = date_field
        # Nested index: year → month → day → [files]
        self.index: Dict[str, Dict[str, Dict[str, List[FileInfo]]]] = {}

    def build_index(self, files: List[FileInfo]) -> None:
        """
        Build the date hierarchy index from a list of files.

        Each file is placed in the appropriate year/month/day based on
        its timestamp. Creates a 3-level nested dictionary structure.

        Args:
            files: List of files to index
        """
        # Clear existing index
        self.index = {}

        # Index each file by date
        for file_info in files:
            # Skip directories (only index regular files)
            if not file_info.is_file:
                continue

            try:
                # Get the appropriate timestamp
                timestamp = self._get_timestamp(file_info)

                # Convert to datetime and extract year/month/day
                dt = datetime.fromtimestamp(timestamp)
                year = str(dt.year)
                month = f"{dt.month:02d}"  # Zero-padded (01-12)
                day = f"{dt.day:02d}"  # Zero-padded (01-31)

                # Create nested structure if needed
                if year not in self.index:
                    self.index[year] = {}
                if month not in self.index[year]:
                    self.index[year][month] = {}
                if day not in self.index[year][month]:
                    self.index[year][month][day] = []

                # Add file to the appropriate day
                self.index[year][month][day].append(file_info)

            except (ValueError, OSError):
                # Skip files with invalid timestamps
                continue

    def resolve(self, virtual_path: str) -> Optional[str]:
        """
        Resolve a virtual path to a real filesystem path.

        Virtual path format: "YYYY/MM/DD/filename"

        Args:
            virtual_path: Path relative to this layer (e.g., "2024/11/12/file.txt")

        Returns:
            Absolute path to the real file, or None if not found
        """
        # Split path into components
        parts = virtual_path.split("/")

        # Must be exactly 4 parts: year/month/day/filename
        if len(parts) != 4:
            return None

        year, month, day, filename = parts

        # Check if path exists in index
        if year not in self.index:
            return None
        if month not in self.index[year]:
            return None
        if day not in self.index[year][month]:
            return None

        # Find file in the day
        for file_info in self.index[year][month][day]:
            if file_info.name == filename:
                return file_info.real_path

        return None

    def list_directory(self, subpath: str = "") -> List[str]:
        """
        List contents of a virtual directory.

        Args:
            subpath: Path relative to this layer
                    "" lists years (root)
                    "2024" lists months in 2024
                    "2024/11" lists days in November 2024
                    "2024/11/12" lists files on November 12, 2024

        Returns:
            List of names (directories or files) in the virtual directory
        """
        if not subpath:
            # Root: list all years
            return sorted(self.index.keys())

        # Split path into components
        parts = subpath.split("/")

        if len(parts) == 1:
            # List months in a year
            year = parts[0]
            if year in self.index:
                return sorted(self.index[year].keys())
            return []

        elif len(parts) == 2:
            # List days in a month
            year, month = parts
            if year in self.index and month in self.index[year]:
                return sorted(self.index[year][month].keys())
            return []

        elif len(parts) == 3:
            # List files in a day
            year, month, day = parts
            if year in self.index and month in self.index[year] and day in self.index[year][month]:
                return sorted([f.name for f in self.index[year][month][day]])
            return []

        else:
            # Invalid path depth
            return []

    def _get_timestamp(self, file_info: FileInfo) -> float:
        """
        Get the appropriate timestamp from a FileInfo.

        Args:
            file_info: File to get timestamp from

        Returns:
            Timestamp in seconds since epoch

        Raises:
            ValueError: If date_field is invalid
        """
        if self.date_field == "mtime":
            return file_info.mtime
        elif self.date_field == "ctime":
            return file_info.ctime
        elif self.date_field == "atime":
            return file_info.atime
        else:
            raise ValueError(f"Invalid date_field: {self.date_field}")

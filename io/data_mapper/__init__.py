"""Data Mapper — column mapping for tabular data files."""

from .config import DataMapperConfig, ColumnMapping, dispersion_config
from .core import DataMapperCore, parse_file
from .dialog import DataMapperDialog

__all__ = [
    "DataMapperConfig",
    "ColumnMapping",
    "dispersion_config",
    "DataMapperCore",
    "parse_file",
    "DataMapperDialog",
]

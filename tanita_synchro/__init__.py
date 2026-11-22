"""tanita-synchro: copy MyTanita body composition measurements to Garmin Connect."""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .garmin import GarminError
from .mytanita import Measurement, MyTanita, MyTanitaError, parse_csv

try:
    __version__ = version("tanita-synchro")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0+unknown"

__all__ = ["GarminError", "Measurement", "MyTanita", "MyTanitaError", "parse_csv"]

"""OpenPeakView - an open source viewer for SCIEX LC-MS data (.wiff)."""

__version__ = "0.4.0"

from .components import Component  # noqa: F401
from .method import ProcessingMethod  # noqa: F401
from .samples import SampleEntry  # noqa: F401
from .wiff import Channel, ChannelInfo, Sample, WiffFile  # noqa: F401

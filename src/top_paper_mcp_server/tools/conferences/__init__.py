"""Conference paper sources module."""

from .base import ConferenceSource, PaperMetadata
from .cvf import CVFSource
from .openreview import OpenReviewSource
from .eccv import ECCVSource
from .acm import ACMSource
from .mlanthology import MLAnthologySource

__all__ = [
    "ConferenceSource",
    "PaperMetadata",
    "CVFSource",
    "OpenReviewSource",
    "ECCVSource",
    "ACMSource",
    "MLAnthologySource",
]

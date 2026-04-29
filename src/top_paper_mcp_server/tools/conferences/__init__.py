"""Conference paper sources module."""

from .base import ConferenceSource, PaperMetadata
from .cvf import CVFSource
from .openreview import OpenReviewSource
from .neurips import NeurIPSSource
from .icml import ICMLSource
from .aaai_ijcai import AAAISource, IJCaiSource
from .eccv import ECCVSource
from .acm import ACMSource
from .mlanthology import MLAnthologySource

__all__ = [
    "ConferenceSource",
    "PaperMetadata",
    "CVFSource",
    "OpenReviewSource",
    "NeurIPSSource",
    "ICMLSource",
    "AAAISource",
    "IJCaiSource",
    "ECCVSource",
    "ACMSource",
    "MLAnthologySource",
]

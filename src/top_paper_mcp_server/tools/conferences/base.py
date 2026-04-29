"""Abstract base class for conference paper sources."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Optional


@dataclass
class PaperMetadata:
    """Standard metadata for conference papers."""

    paper_id: str
    title: str
    authors: List[str]
    abstract: str
    year: int
    conference: str
    url: str
    pdf_url: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.paper_id,
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "year": self.year,
            "conference": self.conference,
            "url": self.url,
            "pdf_url": self.pdf_url,
            "resource_uri": f"{self.conference.lower()}://{self.paper_id}",
        }


class ConferenceSource(ABC):
    """Abstract base class for conference paper sources."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Conference source name."""
        pass

    @property
    @abstractmethod
    def conferences(self) -> List[str]:
        """List of supported conference acronyms."""
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        conference: str,
        year: int,
        max_results: int = 10,
    ) -> List[PaperMetadata]:
        """Search for papers in a conference."""
        pass

    @abstractmethod
    async def get_paper(
        self, paper_id: str, conference: str
    ) -> Optional[PaperMetadata]:
        """Get metadata for a specific paper."""
        pass

    @abstractmethod
    async def download_paper(self, paper_id: str, conference: str) -> Dict[str, Any]:
        """Download paper content and return text."""
        pass

    @staticmethod
    def normalize_query(query: str) -> str:
        """Normalize search query."""
        return query.strip()

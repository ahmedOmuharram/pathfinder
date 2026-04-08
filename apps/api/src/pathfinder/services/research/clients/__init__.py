"""Literature search API clients."""

from pathfinder.services.research.clients.arxiv import ArxivClient
from pathfinder.services.research.clients.crossref import CrossrefClient
from pathfinder.services.research.clients.europepmc import EuropePmcClient
from pathfinder.services.research.clients.openalex import OpenAlexClient
from pathfinder.services.research.clients.preprint import PreprintClient
from pathfinder.services.research.clients.pubmed import PubmedClient
from pathfinder.services.research.clients.semanticscholar import (
    SemanticScholarClient,
)

__all__ = [
    "ArxivClient",
    "CrossrefClient",
    "EuropePmcClient",
    "OpenAlexClient",
    "PreprintClient",
    "PubmedClient",
    "SemanticScholarClient",
]

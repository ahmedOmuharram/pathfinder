"""Literature search API clients."""

from veupath_chatbot.services.research.clients.arxiv import ArxivClient
from veupath_chatbot.services.research.clients.crossref import CrossrefClient
from veupath_chatbot.services.research.clients.europepmc import EuropePmcClient
from veupath_chatbot.services.research.clients.openalex import OpenAlexClient
from veupath_chatbot.services.research.clients.preprint import PreprintClient
from veupath_chatbot.services.research.clients.pubmed import PubmedClient
from veupath_chatbot.services.research.clients.semanticscholar import (
    SemanticScholarClient,
)

__all__ = [
    "EuropePmcClient",
    "CrossrefClient",
    "OpenAlexClient",
    "SemanticScholarClient",
    "PubmedClient",
    "ArxivClient",
    "PreprintClient",
]

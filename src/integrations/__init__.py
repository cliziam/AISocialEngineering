"""
Moduli di integrazione con servizi esterni
Contiene client per Ollama, WhatsApp e ricerca web
"""

from .ollama_client import OllamaClient
from .whatsapp_client import WhatsAppClient
from .web_searcher import WebSearcher

__all__ = ['OllamaClient', 'WhatsAppClient', 'WebSearcher']

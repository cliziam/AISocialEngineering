"""
Formattatori per output e display
"""

import re
from datetime import datetime
from typing import List, Dict, Any, Optional
import json


def format_search_results(results: List[Dict[str, Any]],
                          max_results: int = 10,
                          include_metadata: bool = True) -> str:
    """Formatta i risultati di ricerca per la visualizzazione"""

    if not results:
        return " Nessun risultato trovato."

    # Limita i risultati
    results = results[:max_results]

    formatted = " RISULTATI RICERCA\n"
    formatted += "=" * 50 + "\n\n"

    for i, result in enumerate(results, 1):
        formatted += f"{i}. {result.get('title', 'Nessun titolo')}\n"
        formatted += f" {result.get('snippet', 'Nessuna descrizione')}\n"
        formatted += f" {result.get('url', 'N/A')}\n"

        if include_metadata:
            formatted += f" Fonte: {result.get('source', 'N/A')}\n"
            if result.get('search_term'):
                formatted += f" Termine: {result['search_term']}\n"

        formatted += "\n"

    if include_metadata:
        formatted += f" Trovati {len(results)} risultati\n"

    return formatted


def format_system_info(info: Dict[str, Any], detailed: bool = False) -> str:
    """Formatta le informazioni del sistema"""

    formatted = " INFORMAZIONI SISTEMA\n"
    formatted += "=" * 40 + "\n"

    # Info di base
    formatted += f"CPU: {info.get('cpu_count', 'N/A')} core\n"
    formatted += f"RAM: {info.get('memory_total', 0) / (1024**3):.1f}GB\n"
    formatted += f"Utilizzo RAM: {info.get('memory_percent', 0):.1f}%\n"

    if detailed:
        formatted += f"Utilizzo CPU: {info.get('cpu_percent', 0):.1f}%\n"
        formatted += f"Utilizzo Disco: {info.get('disk_usage', 0):.1f}%\n"

    # Info GPU
    gpu_count = info.get('gpu_count', 0)
    if gpu_count > 0:
        formatted += f"GPU: {gpu_count} dispositivi\n"
        if detailed and 'gpus' in info:
            for i, gpu in enumerate(info['gpus']):
                formatted += f" GPU {i}: {gpu.get('name', 'N/A')}\n"
                formatted += f" VRAM: {gpu.get('memory_total', 0)}MB\n"
                formatted += f" Temperatura: {gpu.get('temperature', 0)}°C\n"
    else:
        formatted += "GPU: Nessuna GPU rilevata\n"

    return formatted



"""
Utility per manipolazione e pulizia testo
"""

import re
from typing import List


def clean_whatsapp_message(message: str) -> str:
    """
    Pulisce un messaggio per WhatsApp rimuovendo caratteri problematici
    
    Args:
        message: Messaggio da pulire
        
    Returns:
        Messaggio pulito
    """
    if not message:
        return ""
    
    # Rimuovi prefissi meta-testuali comuni
    prefixes_to_remove = [
        "Messaggio:", "WhatsApp:", "Ecco il messaggio:",
        "Ecco un messaggio:", "Testo:", "Output:"
    ]
    
    cleaned = message.strip()
    
    for prefix in prefixes_to_remove:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    
    # Rimuovi virgolette se presenti all'inizio e alla fine
    if (cleaned.startswith('"') and cleaned.endswith('"')) or \
       (cleaned.startswith("'") and cleaned.endswith("'")):
        cleaned = cleaned[1:-1]
    
    return cleaned


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Tronca un testo alla lunghezza massima aggiungendo un suffisso
    
    Args:
        text: Testo da troncare
        max_length: Lunghezza massima
        suffix: Suffisso da aggiungere (default: "...")
        
    Returns:
        Testo troncato
    """
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def extract_name_from_title(title: str, remove_parts: List[str] = None) -> str:
    """
    Estrae il nome pulito da un titolo di pagina web
    
    Args:
        title: Titolo della pagina
        remove_parts: Parti da rimuovere dal titolo
        
    Returns:
        Nome estratto e pulito
    """
    if not title:
        return "sconosciuto"
    
    if remove_parts is None:
        from src.constants import ExtractionKeywords
        remove_parts = ExtractionKeywords.TITLE_REMOVE_PARTS
    
    cleaned_title = title
    for part in remove_parts:
        if part in cleaned_title:
            cleaned_title = cleaned_title.split(part)[0]
    
    return cleaned_title.strip() or "sconosciuto"


def format_phone_number(phone: str) -> str:
    """
    Formatta un numero di telefono per WhatsApp
    (Delegato a helpers.normalize_phone_number per consistenza)
    
    Args:
        phone: Numero di telefono
        
    Returns:
        Numero formattato
    """
    from src.utils.helpers import normalize_phone_number
    return normalize_phone_number(phone, country_code="+39")


def remove_emoji(text: str) -> str:
    """
    Rimuove tutte le emoji dal testo (ChromeDriver supporta solo caratteri BMP)
    
    Args:
        text: Testo da pulire
        
    Returns:
        Testo senza emoji
    """
    if not text:
        return ""
    
    # Pattern completo per rimuovere tutte le emoji Unicode
    # ChromeDriver supporta solo caratteri BMP (Basic Multilingual Plane)
    emoji_pattern = re.compile(
        r'[\U0001F600-\U0001F64F]'  # Emoticons
        r'|[\U0001F300-\U0001F5FF]'  # Symbols & Pictographs
        r'|[\U0001F680-\U0001F6FF]'  # Transport & Map
        r'|[\U0001F1E0-\U0001F1FF]'  # Flags
        r'|[\U00002702-\U000027B0]'  # Dingbats
        r'|[\U000024C2-\U0001F251]'  # Enclosed characters
        r'|[\U0001F900-\U0001F9FF]'  # Supplemental Symbols
        r'|[\U0001FA00-\U0001FA6F]'  # Chess Symbols
        r'|[\U0001FA70-\U0001FAFF]'  # Symbols and Pictographs Extended-A
        r'|[\U00002600-\U000026FF]'  # Miscellaneous Symbols
        r'|[\U00002700-\U000027BF]'  # Dingbats
        r'|[\U0001F700-\U0001F77F]'  # Alchemical Symbols
        r'|[\U0001F780-\U0001F7FF]'  # Geometric Shapes Extended
        r'|[\U0001F800-\U0001F8FF]',  # Supplemental Arrows-C
        flags=re.UNICODE
    )
    
    # Rimuovi emoji
    cleaned = emoji_pattern.sub('', text)
    
    # Rimuovi anche marker di emoji convertiti (es: [BYE], [PLEASE], ecc.)
    marker_pattern = re.compile(
        r'\[(?:BYE|PLEASE|HAPPY|SAD|NEUTRAL|THINK|TARGET|START|OK|ERROR|WARN|TIP|'
        r'WHATSAPP|AI|SEARCH|STATS|REPORT|MESSAGE|RETRY|DOWNLOAD|SEND|SAVE|SOCIAL|'
        r'FILE|LINK|CONFIG|CLEANUP|CLOSE|FOLDER|READ|INPUT|HOME|PIN|STOP|TIME|'
        r'USER|WORK|LOCATION|NOTE|TAG)\]',
        flags=re.IGNORECASE
    )
    cleaned = marker_pattern.sub('', cleaned)
    
    # Normalizza spazi multipli
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned


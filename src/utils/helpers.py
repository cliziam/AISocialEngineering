"""
Funzioni helper e utilità comuni
"""

import os
import re
import time
from datetime import datetime
from typing import Optional, Union
from pathlib import Path

def get_timestamp(format_str: str = "%Y%m%d_%H%M%S") -> str:
    """Ottiene un timestamp formattato"""
    return datetime.now().strftime(format_str)

def get_iso_timestamp() -> str:
    """Ottiene un timestamp ISO 8601"""
    return datetime.now().isoformat()

def clean_text(text: str, 
              remove_html: bool = True,
              remove_extra_spaces: bool = True,
              max_length: Optional[int] = None) -> str:
    """Pulisce il testo rimuovendo caratteri indesiderati"""
    
    if not text or not isinstance(text, str):
        return ""
        
    # Rimuovi HTML tags se richiesto
    if remove_html:
        text = re.sub(r'<[^>]+>', '', text)
        
    # Rimuovi caratteri di controllo
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    
    # Rimuovi spazi extra se richiesto
    if remove_extra_spaces:
        text = re.sub(r'\s+', ' ', text)
        
    # Rimuovi spazi iniziali e finali
    text = text.strip()
    
    # Limita lunghezza se specificato
    if max_length and len(text) > max_length:
        text = text[:max_length-3] + "..."
        
    return text

def ensure_directory(path: Union[str, Path]) -> Path:
    """Assicura che la directory esista"""
    
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_file_extension(filename: str) -> str:
    """Ottiene l'estensione del file"""
    return Path(filename).suffix.lower()

def is_safe_filename(filename: str) -> bool:
    """Controlla se il nome del file è sicuro"""
    
    # Caratteri pericolosi
    dangerous_chars = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']
    
    for char in dangerous_chars:
        if char in filename:
            return False
            
    return True

def retry_on_failure(max_retries: int = 3, 
                    delay: float = 1.0,
                    backoff_factor: float = 2.0):
    """Decorator per riprovare una funzione in caso di fallimento"""
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        raise e
                        
                    print(f"[WARN] Tentativo {attempt + 1} fallito: {e}")
                    print(f"[RETRY] Riprovo tra {current_delay} secondi...")
                    
                    time.sleep(current_delay)
                    current_delay *= backoff_factor
                    
        return wrapper
    return decorator

def normalize_phone_number(phone: str, country_code: str = "+39") -> str:
    """Normalizza un numero di telefono"""
    
    if not phone:
        return ""
        
    # Rimuovi tutti i caratteri non numerici tranne +
    phone = re.sub(r'[^\d+]', '', phone)
    
    # Se non inizia con +, aggiungi il country code
    if not phone.startswith('+'):
        if phone.startswith('39'):
            phone = '+' + phone
        else:
            phone = country_code + phone
            
    return phone

def extract_domain_from_url(url: str) -> str:
    """Estrae il dominio da un URL"""
    
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except:
        return ""

def get_user_agent() -> str:
    """Ottiene un User-Agent string appropriato"""
    
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    )


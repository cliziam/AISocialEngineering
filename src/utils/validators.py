"""
Validatori per input e dati
"""

import os
import re
import ipaddress
from typing import Any, Optional, Union, Tuple
from urllib.parse import urlparse

def validate_phone_number(phone: str, country_code: str = "+39") -> bool:
    """Valida un numero di telefono"""
    if not phone:
        return False
        
    # Rimuovi spazi, punti, trattini
    clean_phone = re.sub(r'[\s\.\-\(\)]', '', phone)
    
    # Se inizia con +, usa così, altrimenti aggiungi country code
    if not clean_phone.startswith('+'):
        clean_phone = country_code + clean_phone
        
    # Pattern per numero italiano
    pattern = r'^\+39\d{9,10}$'
    
    return bool(re.match(pattern, clean_phone))

def validate_email(email: str) -> bool:
    """Valida un indirizzo email"""
    if not email:
        return False
        
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_url(url: str, allowed_schemes: list = None) -> bool:
    """Valida un URL"""
    if not url:
        return False
        
    if allowed_schemes is None:
        allowed_schemes = ['http', 'https']
        
    try:
        parsed = urlparse(url)
        return (parsed.scheme in allowed_schemes and 
                parsed.netloc and 
                len(parsed.netloc) > 0)
    except:
        return False

def validate_ip_address(ip: str, version: Optional[int] = None) -> bool:
    """Valida un indirizzo IP"""
    if not ip:
        return False
        
    try:
        ip_obj = ipaddress.ip_address(ip)
        if version:
            return ip_obj.version == version
        return True
    except ValueError:
        return False

def validate_search_term(term: str, max_length: int = 100) -> bool:
    """Valida un termine di ricerca"""
    if not term or not isinstance(term, str):
        return False
        
    # Controlla lunghezza
    if len(term) > max_length:
        return False
        
    # Controlla caratteri pericolosi
    dangerous_chars = ['<', '>', '"', "'", '&', ';', '(', ')', '|', '`', '$']
    if any(char in term for char in dangerous_chars):
        return False
        
    # Deve contenere almeno un carattere alfanumerico
    if not re.search(r'[a-zA-Z0-9]', term):
        return False
        
    return True

def validate_model_name(model: str) -> bool:
    """Valida un nome di modello Ollama"""
    if not model or not isinstance(model, str):
        return False
        
    # Pattern per nomi modello validi
    pattern = r'^[a-zA-Z0-9][a-zA-Z0-9\-_\.]*[a-zA-Z0-9]$'
    
    # Controlla lunghezza
    if len(model) < 2 or len(model) > 50:
        return False
        
    return bool(re.match(pattern, model))

def validate_file_path(path: str, must_exist: bool = False) -> bool:
    """Valida un percorso file"""
    if not path or not isinstance(path, str):
        return False
        
    # Controlla caratteri pericolosi
    dangerous_chars = ['..', '~', '*', '?', '[', ']', '{', '}']
    if any(char in path for char in dangerous_chars):
        return False
        
    # Controlla se il file deve esistere
    if must_exist:
        from pathlib import Path
        return Path(path).exists()
        
    return True

def validate_config_value(key: str, value: Any) -> Tuple[bool, str]:
    """Valida un valore di configurazione"""
    
    # Validatori specifici per chiavi
    validators = {
        'ollama_host': lambda v: isinstance(v, str) and validate_url(v),
        'ollama_model': lambda v: isinstance(v, str) and validate_model_name(v),
        'ollama_timeout': lambda v: isinstance(v, int) and 1 <= v <= 300,
        'max_search_results': lambda v: isinstance(v, int) and 1 <= v <= 100,
        'search_timeout': lambda v: isinstance(v, int) and 1 <= v <= 60,
        'gpu_enabled': lambda v: isinstance(v, bool),
        'max_memory_usage': lambda v: isinstance(v, int) and 10 <= v <= 100,
        'log_level': lambda v: isinstance(v, str) and v.upper() in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        'output_dir': lambda v: isinstance(v, str) and validate_file_path(v),
        'backup_dir': lambda v: isinstance(v, str) and validate_file_path(v),
        'log_dir': lambda v: isinstance(v, str) and validate_file_path(v)
    }
    
    if key in validators:
        try:
            is_valid = validators[key](value)
            return is_valid, "Valid" if is_valid else f"Invalid value for {key}"
        except Exception as e:
            return False, f"Validation error for {key}: {e}"
    else:
        # Validazione generica
        if value is None:
            return True, "Valid (None)"
        elif isinstance(value, (str, int, float, bool, list, dict)):
            return True, "Valid"
        else:
            return False, f"Unsupported type for {key}: {type(value)}"

def validate_whatsapp_number(phone: str) -> Tuple[bool, str]:
    """Valida e formatta un numero WhatsApp"""
    if not phone:
        return False, "Numero vuoto"
        
    # Pulisci il numero
    clean_phone = re.sub(r'[\s\.\-\(\)\+]', '', phone)
    
    # Controlla se contiene solo cifre
    if not clean_phone.isdigit():
        return False, "Il numero deve contenere solo cifre"
        
    # Controlla lunghezza (8-15 cifre)
    if len(clean_phone) < 8 or len(clean_phone) > 15:
        return False, "Numero troppo corto o troppo lungo"
        
    # Aggiungi prefisso internazionale se mancante
    if not phone.startswith('+'):
        clean_phone = '+39' + clean_phone if not clean_phone.startswith('39') else '+' + clean_phone
        
    return True, clean_phone


def sanitize_input(text: str, max_length: int = 1000, allow_special_chars: bool = False) -> str:
    """
    Sanitizza input utente per prevenire injection e altri problemi
    
    Args:
        text: Testo da sanitizzare
        max_length: Lunghezza massima permessa
        allow_special_chars: Se True, permette caratteri speciali
        
    Returns:
        Testo sanitizzato
    """
    if not text:
        return ""
    
    # Limita lunghezza
    text = text[:max_length]
    
    # Rimuovi caratteri di controllo pericolosi
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    # Se non permettiamo caratteri speciali, mantieni solo alfanumerici e spazi
    if not allow_special_chars:
        text = re.sub(r'[^\w\s\-\.\,\!\?\@]', '', text, flags=re.UNICODE)
    
    # Rimuovi spazi multipli
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def sanitize_search_term(search_term: str) -> str:
    """
    Sanitizza un termine di ricerca
    
    Args:
        search_term: Termine da sanitizzare
        
    Returns:
        Termine sanitizzato
    """
    if not search_term:
        return ""
    
    # Rimuovi caratteri pericolosi ma mantieni quelli utili per la ricerca
    sanitized = re.sub(r'[<>\"\'\\;]', '', search_term)
    
    # Limita lunghezza
    sanitized = sanitized[:200]
    
    # Rimuovi spazi multipli
    sanitized = re.sub(r'\s+', ' ', sanitized)
    
    return sanitized.strip()


def sanitize_filename(filename: str) -> str:
    """
    Sanitizza un nome file per evitare path traversal e caratteri non validi
    
    Args:
        filename: Nome file da sanitizzare
        
    Returns:
        Nome file sanitizzato
    """
    if not filename:
        return "unnamed"
    
    # Rimuovi path separators e caratteri pericolosi
    sanitized = re.sub(r'[/\\:*?"<>|]', '_', filename)
    
    # Rimuovi .. per prevenire path traversal
    sanitized = sanitized.replace('..', '_')
    
    # Rimuovi punti multipli
    sanitized = re.sub(r'\.+', '.', sanitized)
    
    # Rimuovi spazi iniziali/finali
    sanitized = sanitized.strip()
    
    # Limita lunghezza (255 è il limite standard per nomi file)
    if len(sanitized) > 255:
        name, ext = os.path.splitext(sanitized)
        sanitized = name[:255-len(ext)] + ext if ext else sanitized[:255]
    
    return sanitized or "unnamed"


def validate_and_sanitize_phone(phone: str) -> Tuple[bool, str]:
    """
    Valida e sanitizza un numero di telefono
    
    Args:
        phone: Numero da validare e sanitizzare
        
    Returns:
        Tupla (is_valid, sanitized_phone)
    """
    if not phone:
        return False, ""
    
    # Sanitizza: rimuovi tutto tranne numeri, +, spazi, parentesi, trattini
    sanitized = re.sub(r'[^\d\+\s\(\)\-]', '', phone)
    
    # Valida
    is_valid = validate_phone_number(sanitized)
    
    return is_valid, sanitized


def detect_sql_injection(text: str) -> bool:
    """
    Rileva potenziali tentativi di SQL injection
    
    Args:
        text: Testo da controllare
        
    Returns:
        True se rileva pattern sospetti
    """
    if not text:
        return False
    
    # Pattern comuni di SQL injection
    sql_patterns = [
        r"(\bUNION\b.*\bSELECT\b)",
        r"(\bSELECT\b.*\bFROM\b)",
        r"(\bINSERT\b.*\bINTO\b)",
        r"(\bDELETE\b.*\bFROM\b)",
        r"(\bDROP\b.*\bTABLE\b)",
        r"(--|\#|\/\*)",
        r"(\bOR\b.*=.*)",
        r"(\bAND\b.*=.*)",
        r"('.*OR.*'.*=.*')",
    ]
    
    text_upper = text.upper()
    
    for pattern in sql_patterns:
        if re.search(pattern, text_upper, re.IGNORECASE):
            return True
    
    return False


def detect_xss_attempt(text: str) -> bool:
    """
    Rileva potenziali tentativi di XSS
    
    Args:
        text: Testo da controllare
        
    Returns:
        True se rileva pattern sospetti
    """
    if not text:
        return False
    
    # Pattern comuni di XSS
    xss_patterns = [
        r"<script[^>]*>.*</script>",
        r"javascript:",
        r"onerror\s*=",
        r"onload\s*=",
        r"onclick\s*=",
        r"<iframe[^>]*>",
        r"<embed[^>]*>",
        r"<object[^>]*>",
    ]
    
    text_lower = text.lower()
    
    for pattern in xss_patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    
    return False

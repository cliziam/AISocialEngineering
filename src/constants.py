"""
Costanti e configurazioni centralizzate per il Social Engineering Tool
"""

from typing import Dict, List

# ============================================================================
# WHATSAPP SELETTORI CSS
# ============================================================================

class WhatsAppSelectors:
    """Selettori CSS per elementi WhatsApp Web"""
    
    # Autenticazione
    CHAT_LIST = "[data-testid='chat-list']"
    QR_CODE = "[data-ref='qr-code']"
    MENU = "[data-testid='menu']"
    CONVERSATION_HEADER = "header[data-testid='conversation-header']"
    
    # Ricerca
    SEARCH_BOX = [
        "[data-testid='chat-list-search']",
        "div[contenteditable='true'][data-tab='3']",
        "div[title='Cerca o inizia una nuova chat']",
        "div._2vDPL",
        "input[type='text'][title='Cerca o inizia una nuova chat']"
    ]
    
    # Chat e Contatti
    CELL_FRAME_CONTAINER = "[data-testid='cell-frame-container']"
    CELL_FRAME_TITLE = "[data-testid='cell-frame-title']"
    LIST_ITEM = "div[role='listitem']"
    
    # Input Box Messaggio
    MESSAGE_INPUT = [
        "[data-testid='conversation-compose-box-input']",
        "div[contenteditable='true'][data-tab='10']",
        "div[contenteditable='true'][role='textbox']",
        "div[title='Scrivi un messaggio']",
        "div[title='Type a message']",
        "div._3Uu1_",
        "footer div[contenteditable='true']",
        "div[data-tab='10']",
        "div[data-tab='6']",
        "footer div[role='textbox']",
        "div.copyable-text[contenteditable='true']",
        "div._1awRl.copyable-text[contenteditable='true']"
    ]
    
    # Pulsante Invio
    SEND_BUTTON = [
        "[data-testid='send']",
        "button[aria-label='Invia']",
        "button[aria-label='Send']",
        "span[data-icon='send']",
        "button._1U1xa",
        "button[data-testid='compose-btn-send']",
        "button[data-tab='11']",
        "span[data-testid='send']",
        "footer button[aria-label='Invia']",
        "footer button[aria-label='Send']"
    ]


# ============================================================================
# SOCIAL ENGINEERING SCENARI E CONTESTI
# ============================================================================

class SocialEngineeringScenarios:
    """Scenari predefiniti per messaggi di social engineering"""
    
    SCENARIOS: Dict[str, str] = {
        "richiesta_aiuto": "chiede un piccolo favore urgente",
        "conferma_identità": "vuole confermare alcuni dettagli personali",
        "urgenza": "ha bisogno urgente di assistenza",
        "opportunità": "propone un'opportunità interessante",
        "riconnessione": "si riconnette dopo tempo",
        "problema_tecnico": "ha un problema tecnico e chiede aiuto"
    }
    
    CONTEXTS: Dict[str, str] = {
        "collega": "collega di lavoro",
        "amico": "amico/conoscente",
        "familiare": "parente",
        "fornitore": "fornitore/partner commerciale"
    }
    
    @staticmethod
    def get_scenario_description(scenario: str) -> str:
        """Ottiene la descrizione di uno scenario"""
        return SocialEngineeringScenarios.SCENARIOS.get(
            scenario, 
            scenario
        )
    
    @staticmethod
    def get_context_description(context: str) -> str:
        """Ottiene la descrizione di un contesto"""
        return SocialEngineeringScenarios.CONTEXTS.get(
            context,
            context
        )


# ============================================================================
# NICKNAME E VARIANTI NOMI
# ============================================================================

class NameVariations:
    """Database di diminutivi e varianti di nomi comuni"""
    
    COMMON_NICKNAMES: Dict[str, List[str]] = {
        'simo': ['simone', 'Simone'],
        'ale': ['alessandro', 'alessandra', 'Alessandro', 'Alessandra'],
        'gianni': ['giovanni', 'Giovanni'],
        'luca': ['luciano', 'Luciano'],
        'max': ['massimo', 'massimiliano', 'Massimo', 'Massimiliano'],
        'fede': ['federico', 'federica', 'Federico', 'Federica'],
        'fra': ['francesco', 'francesca', 'Francesco', 'Francesca'],
        'ste': ['stefano', 'stefania', 'Stefano', 'Stefania'],
        'roby': ['roberto', 'roberta', 'Roberto', 'Roberta'],
        'vale': ['valentina', 'valentino', 'Valentina', 'Valentino'],
        'cri': ['cristina', 'cristiano', 'Cristina', 'Cristiano'],
        'dani': ['daniele', 'daniela', 'Daniele', 'Daniela'],
        'mari': ['maria', 'mario', 'Maria', 'Mario'],
        'anto': ['antonio', 'antonella', 'Antonio', 'Antonella'],
        'gio': ['giovanni', 'giovanna', 'Giorgio', 'Giovanni', 'Giovanna'],
        'marco': ['marcello', 'Marcello'],
        'manu': ['manuel', 'manuela', 'Manuel', 'Manuela'],
        'gabri': ['gabriele', 'gabriella', 'Gabriele', 'Gabriella'],
        'lori': ['lorenzo', 'loredana', 'Lorenzo', 'Loredana'],
        'beppe': ['giuseppe', 'Giuseppe'],
        'peppe': ['giuseppe', 'Giuseppe'],
        'pippo': ['giuseppe', 'Giuseppe'],
        'pino': ['giuseppe', 'Giuseppe'],
        'giu': ['giulia', 'giulio', 'giuseppe', 'Giulia', 'Giulio', 'Giuseppe'],
        'toni': ['antonio', 'Antonio'],
        'nino': ['antonino', 'Antonino'],
        'salvo': ['salvatore', 'Salvatore'],
        'fabio': ['fabrizio', 'Fabrizio'],
        'ricky': ['riccardo', 'Riccardo'],
        'vitto': ['vittorio', 'vittoria', 'Vittorio', 'Vittoria'],
        'paola': ['paolo', 'Paolo'],
        'paolo': ['paola', 'Paola'],
        'massi': ['massimo', 'massimiliano', 'Massimo', 'Massimiliano'],
        'massimo': ['massi', 'Massi']
    }
    
    @staticmethod
    def generate_variations(name: str) -> List[str]:
        """Genera tutte le variazioni possibili di un nome"""
        variations = [
            name,                   # Originale
            name.capitalize(),      # Prima lettera maiuscola
            name.lower(),          # Tutto minuscolo
            name.upper(),          # Tutto maiuscolo
            name.title(),          # Title Case
        ]
        
        # Aggiungi varianti da dizionario
        name_lower = name.lower()
        if name_lower in NameVariations.COMMON_NICKNAMES:
            for full_name in NameVariations.COMMON_NICKNAMES[name_lower]:
                if full_name not in variations:
                    variations.append(full_name)
        
        # Rimuovi duplicati mantenendo l'ordine
        seen = set()
        return [x for x in variations if not (x in seen or seen.add(x))]


# ============================================================================
# KEYWORDS PER ESTRAZIONE INFORMAZIONI
# ============================================================================

class ExtractionKeywords:
    """Keywords per estrarre informazioni dai risultati di ricerca"""
    
    WORK_KEYWORDS = [
        'lavora', 'works', 'presso', 'at', 'CEO', 'Manager', 
        'Developer', 'Engineer', 'Designer', 'Consulente', 
        'Director', 'Founder', 'Co-founder'
    ]
    
    LOCATION_KEYWORDS = [
        'Milano', 'Roma', 'Torino', 'Napoli', 'Bologna', 'Firenze',
        'Italy', 'Italia', 'Venezia', 'Genova', 'Palermo', 'Bari',
        'Catania', 'Verona', 'Padova', 'Trieste', 'Brescia'
    ]
    
    TITLE_REMOVE_PARTS = [
        ' - LinkedIn', ' | LinkedIn', ' - Facebook', ' | Facebook',
        ' - Twitter', ' - Instagram', ' (@', ' profile', ' profilo',
        ' | Twitter', ' - YouTube', ' | YouTube'
    ]


# ============================================================================
# CONFIGURAZIONI AI/OLLAMA
# ============================================================================

class OllamaConfig:
    """Configurazioni di connessione per Ollama"""
    
    # Host e porta di default
    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 11434
    DEFAULT_SCHEME = "http"
    
    # URL completo di default
    DEFAULT_URL = f"{DEFAULT_SCHEME}://{DEFAULT_HOST}:{DEFAULT_PORT}"
    
    # Timeout
    LIST_TIMEOUT = 5  # Timeout per 'ollama list' subprocess


class AIConfig:
    """Configurazioni per il modello AI"""
    
    # Modelli disponibili
    DEFAULT_MODEL = 'gpt-oss-120b'  # Modello GPT-OSS 120B
    FALLBACK_MODELS = ['llama3.1:8b', 'llama3.2:1b', 'llama3.2', 'llama2', 'llama3:8b']
    
    # Limiti
    MAX_MESSAGE_LENGTH = 280
    MAX_CONTEXT_LENGTH = 2048
    MAX_SUMMARY_SENTENCES = 3
    
    # Temperature per diversi task
    CREATIVE_TEMPERATURE = 0.8  # Per creatività
    BALANCED_TEMPERATURE = 0.3  # Default bilanciato (basso per coerenza)
    PRECISE_TEMPERATURE = 0.2   # Per massima precisione/determinismo


# ============================================================================
# TIMEOUTS E RITARDI
# ============================================================================

class Timeouts:
    """Timeout e delay per operazioni asincrone"""
    
    # WhatsApp
    WHATSAPP_QR_TIMEOUT = 300
    WHATSAPP_ELEMENT_WAIT = 10
    WHATSAPP_PAGE_LOAD = 3
    WHATSAPP_CHAT_OPEN = 4
    WHATSAPP_TYPE_DELAY = 0.05
    WHATSAPP_ACTION_DELAY = 1
    
    # Web Search
    WEB_SEARCH_TIMEOUT = 10
    WEB_SEARCH_RETRY_DELAY = 2
    
    # Ollama
    OLLAMA_REQUEST_TIMEOUT = 30


# ============================================================================
# MESSAGGI E FORMATTAZIONE
# ============================================================================

class Messages:
    """Messaggi standard per l'interfaccia utente"""
    
    # Successo
    SUCCESS_WHATSAPP_CONNECTED = "WhatsApp connesso e autenticato"
    SUCCESS_MESSAGE_SENT = "Messaggio inviato con successo!"
    SUCCESS_RESEARCH_COMPLETE = "Ricerca completata"
    
    # Errori
    ERROR_NO_DATA = "Nessun dato da inviare. Esegui prima la ricerca!"
    ERROR_WHATSAPP_NOT_CONNECTED = "WhatsApp non connesso"
    ERROR_SELENIUM_NOT_AVAILABLE = "Selenium non disponibile. Installa con: pip install selenium webdriver-manager"
    ERROR_CONTACT_NOT_FOUND = "Impossibile trovare il contatto"
    
    # Info
    INFO_GENERATING_MESSAGE = "Generazione messaggio..."
    INFO_SEARCHING_CONTACT = "Cercando il contatto..."
    INFO_TYPING_MESSAGE = "Digitando il messaggio..."
    INFO_SENDING = "Invio in corso..."


# ============================================================================
# VERSIONE E INFO
# ============================================================================

class AppInfo:
    """Informazioni sull'applicazione"""
    
    NAME = "Social Engineering Research Tool"
    VERSION = "1.0"
    DESCRIPTION = "Integra Ollama + Ricerca Web + WhatsApp"
    
    @staticmethod
    def get_banner() -> str:
        """Restituisce il banner dell'applicazione"""
        return f"""
{AppInfo.NAME} v{AppInfo.VERSION}
{AppInfo.DESCRIPTION}
{"=" * 50}
"""


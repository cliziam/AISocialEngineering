"""
Gestione centralizzata della configurazione
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

class ConfigManager:
    """Gestore centralizzato della configurazione"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
        # Carica variabili d'ambiente
        load_dotenv()
        
        # Configurazioni di default
        self._defaults = {
            # Ollama - usa 127.0.0.1 invece di localhost per evitare problemi IPv6/IPv4 su Windows
            'ollama_host': 'http://127.0.0.1:11434',
            'ollama_model': 'gpt-oss-120b',  # Usa gpt-oss-120b
            'ollama_timeout': 120,  # Aumentato a 120s per permettere caricamento iniziale modello
            
            # WhatsApp
            'whatsapp_session_path': './data/whatsapp_session',
            'whatsapp_timeout': 60,
            
            # Ricerca web
            'search_engine': 'duckduckgo',
            'max_search_results': 10,
            'search_timeout': 15,
            'rate_limit_delay': 1,
            
            # Hardware
            'gpu_enabled': True,
            'max_memory_usage': 80,
            'cpu_threads': None,  # Auto-detect
            
            # File
            'output_dir': './data/output',
            'backup_dir': './data/backups',
            'log_dir': './logs',
            
            # Logging
            'log_level': 'INFO',
            'log_format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        }
        
        self._config = {}
        self._load_config()
        
    def _load_config(self):
        """Carica la configurazione da file e variabili d'ambiente"""
        # Carica configurazione da file se esiste
        config_file = self.config_dir / "config.json"
        if config_file.exists():
            try:
                import json
                with open(config_file, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    # Gestisci struttura annidata (es: {"ollama": {"model": "..."}})
                    if 'ollama' in file_config and isinstance(file_config['ollama'], dict):
                        # Estrai configurazione Ollama
                        ollama_config = file_config['ollama']
                        if 'model' in ollama_config:
                            model_value = ollama_config['model']
                            # Normalizza llama2 a llama3:8b
                            if model_value == 'llama2' or model_value == 'llama2:latest':
                                model_value = 'llama3:8b'
                                print(f"[WARN] Modello 'llama2' trovato in config, aggiornato a 'llama3:8b'")
                            self._config['ollama_model'] = model_value
                        if 'host' in ollama_config:
                            self._config['ollama_host'] = ollama_config['host']
                        if 'timeout' in ollama_config:
                            self._config['ollama_timeout'] = ollama_config['timeout']
                    
                    # Aggiorna anche altre configurazioni flat
                    for key, value in file_config.items():
                        if key != 'ollama':  # Già gestito sopra
                            if isinstance(value, dict):
                                # Se è un dict annidato, appiattisci
                                for sub_key, sub_value in value.items():
                                    self._config[f"{key}_{sub_key}"] = sub_value
                            else:
                                self._config[key] = value
            except Exception as e:
                print(f"[WARN] Errore nel caricamento config file: {e}")
        
        # Override con variabili d'ambiente
        # IMPORTANTE: Controlla prima OLLAMA_HOST che è critico
        ollama_host_env = os.getenv('OLLAMA_HOST')
        if ollama_host_env:
            self._config['ollama_host'] = ollama_host_env
            print(f"[ENV] OLLAMA_HOST da variabile d'ambiente: {ollama_host_env}")
        
        for key, default_value in self._defaults.items():
            env_key = key.upper()
            env_value = os.getenv(env_key)
            
            # Skip ollama_host se già impostato sopra
            if key == 'ollama_host' and ollama_host_env:
                continue
            
            if env_value is not None:
                # Converti il tipo appropriato
                if isinstance(default_value, bool):
                    self._config[key] = env_value.lower() in ('true', '1', 'yes', 'on')
                elif isinstance(default_value, int):
                    try:
                        self._config[key] = int(env_value)
                    except ValueError:
                        self._config[key] = default_value
                elif isinstance(default_value, float):
                    try:
                        self._config[key] = float(env_value)
                    except ValueError:
                        self._config[key] = default_value
                else:
                    self._config[key] = env_value
            elif key not in self._config:
                # Usa default solo se non è già stato impostato dal file config
                self._config[key] = default_value
            # Se key è già in _config (da file), mantienila
            # MA: forza llama3:8b se trova ancora llama2
            if key == 'ollama_model' and self._config.get(key) in ['llama2', 'llama2:latest']:
                print(f"[WARN] Rilevato modello 'llama2', forzato a 'llama3:8b'")
                self._config[key] = 'llama3:8b'
                
        # Assicurati che le directory esistano
        self._ensure_directories()
        
    def _ensure_directories(self):
        """Assicura che le directory necessarie esistano"""
        directories = [
            self._config['whatsapp_session_path'],
            self._config['output_dir'],
            self._config['backup_dir'],
            self._config['log_dir']
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            
    def get(self, key: str, default: Any = None) -> Any:
        """Ottiene un valore di configurazione"""
        value = self._config.get(key, default)
        # Forza llama3:8b se trova llama2
        if key == 'ollama_model' and value in ['llama2', 'llama2:latest']:
            return 'llama3:8b'
        return value
        
    def set(self, key: str, value: Any):
        """Imposta un valore di configurazione"""
        self._config[key] = value
        
    def get_all(self) -> Dict[str, Any]:
        """Ottiene tutta la configurazione"""
        return self._config.copy()
        
    def save_config(self, filename: Optional[str] = None):
        """Salva la configurazione in un file"""
        if filename is None:
            filename = self.config_dir / "config.json"
        else:
            filename = Path(filename)
            
        try:
            import json
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            print(f"[OK] Configurazione salvata in: {filename}")
        except Exception as e:
            print(f"[ERR] Errore nel salvataggio configurazione: {e}")
            
    def reset_to_defaults(self):
        """Ripristina la configurazione ai valori di default"""
        self._config = self._defaults.copy()
        self._ensure_directories()
        
    def validate_config(self) -> Dict[str, Any]:
        """Valida la configurazione e restituisce problemi trovati"""
        issues = []
        warnings = []
        
        # Controlla connessioni
        if not self._config.get('ollama_host'):
            issues.append("Ollama host non configurato")
            
        # Controlla directory
        for dir_key in ['output_dir', 'backup_dir', 'log_dir']:
            dir_path = Path(self._config.get(dir_key, ''))
            if not dir_path.exists():
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    issues.append(f"Impossibile creare directory {dir_key}: {e}")
                    
        # Controlla valori numerici
        if self._config.get('max_memory_usage', 0) > 100:
            warnings.append("Utilizzo memoria troppo alto (>100%)")
            
        if self._config.get('max_search_results', 0) > 50:
            warnings.append("Troppi risultati di ricerca richiesti (>50)")
            
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings
        }
        
    def print_config(self):
        """Stampa la configurazione corrente"""
        print("[CONFIG] CONFIGURAZIONE SISTEMA")
        print("=" * 40)
        
        sections = {
            'Ollama': ['ollama_host', 'ollama_model', 'ollama_timeout'],
            'WhatsApp': ['whatsapp_session_path', 'whatsapp_timeout'],
            'Ricerca Web': ['search_engine', 'max_search_results', 'search_timeout'],
            'Hardware': ['gpu_enabled', 'max_memory_usage', 'cpu_threads'],
            'File': ['output_dir', 'backup_dir', 'log_dir'],
            'Logging': ['log_level', 'log_format']
        }
        
        for section_name, keys in sections.items():
            print(f"\n[SECTION] {section_name}:")
            for key in keys:
                value = self._config.get(key, 'N/A')
                if key == 'whatsapp_session_path' and len(str(value)) > 30:
                    value = str(value)[:27] + "..."
                print(f"  {key}: {value}")
                
    def get_ollama_config(self) -> Dict[str, Any]:
        """Ottiene la configurazione specifica per Ollama"""
        return {
            'host': self.get('ollama_host'),
            'model': self.get('ollama_model'),
            'timeout': self.get('ollama_timeout'),
            'gpu_enabled': self.get('gpu_enabled'),
            'max_memory_usage': self.get('max_memory_usage')
        }
        
    def get_whatsapp_config(self) -> Dict[str, Any]:
        """Ottiene la configurazione specifica per WhatsApp"""
        return {
            'session_path': self.get('whatsapp_session_path'),
            'timeout': self.get('whatsapp_timeout')
        }
        
    def get_web_search_config(self) -> Dict[str, Any]:
        """Ottiene la configurazione specifica per la ricerca web"""
        return {
            'engine': self.get('search_engine'),
            'max_results': self.get('max_search_results'),
            'timeout': self.get('search_timeout'),
            'rate_limit_delay': self.get('rate_limit_delay')
        }

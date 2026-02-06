"""
Client Ollama ottimizzato per analisi target e generazione messaggi WhatsApp
Gestisce connessioni, modelli e ottimizzazioni hardware con focus su social engineering
"""

import ollama
import requests
import asyncio
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from src.core.config_manager import ConfigManager
from src.core.hardware_optimizer import HardwareOptimizer

# Import torch per GPU management (opzionale)
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

# Import AIPrompts - prova diversi modi per gestire problemi di import
try:
    from src.prompts import AIPrompts
except ImportError:
    try:
        from prompts import AIPrompts
    except ImportError:
        # Fallback: import diretto dal percorso
        import sys
        from pathlib import Path
        prompts_path = Path(__file__).parent.parent / "prompts.py"
        if prompts_path.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location("prompts", prompts_path)
            prompts_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(prompts_module)
            AIPrompts = prompts_module.AIPrompts
        else:
            AIPrompts = None


class OllamaClient:
    """Client per l'integrazione con Ollama - ottimizzato per analisi target e messaggistica"""
    
    def __init__(self, config_manager: ConfigManager = None):
        self.config_manager = config_manager or ConfigManager()
        self.hardware_optimizer = HardwareOptimizer(self.config_manager)
        
        # Configurazione Ollama
        ollama_config = self.config_manager.get_ollama_config()
        self.ollama_host = ollama_config.get('host', 'http://127.0.0.1:11434')
        base_timeout = ollama_config.get('timeout', 120)
        
        # Aumenta timeout per modelli grandi
        model_name = self.config_manager.get('ollama_model', 'llama3:8b')
        
        # Verifica se il modello è in CPU (controlla dopo che hardware_optimizer è inizializzato)
        # Per ora assumiamo che se il timeout è molto basso (30s), potrebbe essere un problema
        is_cpu_mode = base_timeout < 60  # Se timeout < 60s, probabilmente è un problema
        
        if self._is_120b_model(model_name):
            # Per modelli 120B, serve molto tempo
            if is_cpu_mode:
                self.ollama_timeout = max(base_timeout, 1800)  # 30 minuti in CPU
            else:
                self.ollama_timeout = max(base_timeout, 900)  # 15 minuti su GPU
        elif self._is_large_model(model_name):
            # Per modelli 30B/70B, aumenta il timeout significativamente
            if '30b' in str(model_name).lower():
                if is_cpu_mode:
                    self.ollama_timeout = max(base_timeout, 600)  # 10 minuti in CPU per 30B
                else:
                    self.ollama_timeout = max(base_timeout, 300)  # 5 minuti su GPU
            elif '70b' in str(model_name).lower():
                if is_cpu_mode:
                    self.ollama_timeout = max(base_timeout, 1200)  # 20 minuti in CPU per 70B
                else:
                    self.ollama_timeout = max(base_timeout, 600)  # 10 minuti su GPU
            else:
                self.ollama_timeout = max(base_timeout, 300)  # Default 5 minuti per altri modelli grandi
        else:
            self.ollama_timeout = base_timeout
        
        # Assicurati che l'host abbia lo schema HTTP
        if not self.ollama_host.startswith('http'):
            self.ollama_host = f'http://{self.ollama_host}'
        
        # Sostituisci 0.0.0.0 con 127.0.0.1 (0.0.0.0 non funziona come client)
        self.ollama_host = self.ollama_host.replace('0.0.0.0', '127.0.0.1')
        
        # Crea client con timeout appropriato (usato solo per list e altre operazioni)
        self.client = ollama.Client(host=self.ollama_host)
        
        self.available_models = []
        self.optimized_params = {}
        # Alias per modelli deprecati o rinominati
        # NON normalizzare llama3.2:1b - è un modello valido e diverso!
        self.model_aliases = {
            'llama2': 'llama3:8b',
            'llama2:latest': 'llama3:8b',
            'llama3.1:8b': 'llama3:8b',
            # llama3.2:1b è un modello VALIDO - NON normalizzare!
            # llama3:8b è un modello VALIDO - NON normalizzare!
        }
        
        # Conversazione persistente per mantenere contesto tra chiamate
        self.conversation_history: List[Dict[str, str]] = []
        self.use_persistent_conversation = True  # Abilita conversazione persistente
        
    async def initialize(self):
        """Inizializza il client Ollama e ottimizza per l'hardware"""
        print("Inizializzazione Ollama...")
        
        # Controlla salute sistema
        health = self.hardware_optimizer.check_system_health()
        if not health['healthy']:
            print(f"  Avvisi sistema: {', '.join(health.get('warnings', []))}")
        
        # Carica modelli disponibili
        await self._get_available_models()
        
        # Ottimizza parametri
        model_name = self._normalize_model_name(
            self.config_manager.get('ollama_model', 'llama3:8b')
        )
        self.optimized_params = self.hardware_optimizer.get_optimized_model_params(model_name)
        
        # Verifica se il modello è in CPU e aggiusta timeout se necessario
        is_cpu_mode = False
        if 'options' in self.optimized_params:
            num_gpu = self.optimized_params['options'].get('num_gpu', -1)
            is_cpu_mode = (num_gpu == 0)
        
        # Se il modello è grande e in CPU, aumenta ulteriormente il timeout
        if is_cpu_mode and self._is_large_model(model_name):
            if '30b' in str(model_name).lower():
                if self.ollama_timeout < 600:
                    old_timeout = self.ollama_timeout
                    self.ollama_timeout = 600  # 10 minuti minimo per 30B in CPU
                    print(f"  Timeout aumentato da {old_timeout}s a {self.ollama_timeout}s (modello 30B in CPU)")
            elif '70b' in str(model_name).lower():
                if self.ollama_timeout < 1200:
                    old_timeout = self.ollama_timeout
                    self.ollama_timeout = 1200  # 20 minuti minimo per 70B in CPU
                    print(f"  Timeout aumentato da {old_timeout}s a {self.ollama_timeout}s (modello 70B in CPU)")
            elif self._is_120b_model(model_name):
                if self.ollama_timeout < 1800:
                    old_timeout = self.ollama_timeout
                    self.ollama_timeout = 1800  # 30 minuti minimo per 120B in CPU
                    print(f"  Timeout aumentato da {old_timeout}s a {self.ollama_timeout}s (modello 120B in CPU)")
        
        # Verifica potenziali problemi GPU
        self._check_gpu_warnings()
        
        # WARMUP: Pre-carica il modello con una generazione veloce
        print("Warmup del modello (pre-caricamento)...")
        
        # Per modelli grandi (120B), verifica se è già pronto (ma non aspettare troppo)
        if self._is_120b_model(model_name):
            # Se il modello è già nella lista, è pronto, skip attesa
            if model_name in self.available_models:
                print("  Modello già disponibile, skip attesa")
            else:
                print("  Modello grande rilevato - verifica rapida caricamento...")
                # Attesa breve, max 2 minuti
                await self._wait_for_model_ready(model_name, max_wait=120)
        
        try:
            # Prova una generazione molto breve per verificare che il modello risponda
            warmup_response = await self.generate_response(
                "test", 
                model=model_name,
                options={'num_predict': 3, 'num_ctx': 64}  # Genera solo 3 token, contesto minimo
            )
            if warmup_response and len(warmup_response.strip()) > 0:
                pass  # Warmup completato
            else:
                # Per modelli grandi, potrebbe essere normale che il warmup sia lento
                if self._is_120b_model(model_name):
                    pass  # Normale per modelli grandi
                else:
                    pass  # Warmup incompleto
        except Exception as e:
            # Per modelli grandi, gli errori durante warmup sono meno critici
            if self._is_120b_model(model_name):
                print(f"  Warmup non completato (normale per modelli grandi): {str(e)[:50]}")
            else:
                print(f"  Errore durante warmup: {e}")
        
        print(f"Ollama pronto (modello: {model_name})")
    
    def _check_gpu_warnings(self):
        """Verifica e avvisa su potenziali problemi GPU"""
        if 'options' not in self.optimized_params:
            return
        
        num_gpu = self.optimized_params['options'].get('num_gpu', 0)
        
        if num_gpu > 0:
            sys_info = self.hardware_optimizer.system_info
            if sys_info.get('gpu_available') and len(sys_info.get('gpus', [])) > 0:
                gpu = sys_info['gpus'][0]
                vram_free_gb = gpu.get('memory_free', 0) / 1024
                
                if vram_free_gb < 1.5 and num_gpu > 5:
                    print(f"   Se riscontri errori CUDA, il sistema passerà automaticamente a CPU")
        elif num_gpu == 0:
            print(f"  Modalità CPU rilevata")
        
    def _normalize_model_name(self, model_name: str) -> str:
        """Normalizza il nome del modello usando gli alias"""
        normalized = self.model_aliases.get(model_name, model_name)
        if normalized != model_name:
            print(f"  INFO: Modello normalizzato: {model_name} → {normalized}")
            self.config_manager.set('ollama_model', normalized)
        return normalized
        
    async def _get_available_models(self):
        """Ottiene la lista dei modelli disponibili da Ollama"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get('http://localhost:11434/api/tags') as response:
                    if response.status == 200:
                        data = await response.json()
                        self.available_models = [
                            model.get('name', '') 
                            for model in data.get('models', []) 
                            if model.get('name')
                        ]
                    else:
                        self.available_models = []
            
            if not self.available_models:
                print("  Nessun modello disponibile")
                
        except Exception as e:
            print(f"ERRORE: Errore nel recupero modelli: {e}")
            self.available_models = []
            
    async def ensure_model_exists(self, model_name: str) -> bool:
        """Verifica esistenza modello e lo scarica se necessario"""
        normalized_model = self._normalize_model_name(model_name)
        
        # Aggiorna sempre la lista dei modelli disponibili prima di verificare
        await self._get_available_models()
        
        # Genera varianti del nome modello (gestisce : vs -)
        def generate_name_variants(name: str) -> list:
            """Genera varianti del nome modello"""
            variants = [name, normalized_model]
            # Se contiene :, prova anche con -
            if ':' in name:
                variants.append(name.replace(':', '-'))
            # Se contiene -, prova anche con :
            if '-' in name:
                variants.append(name.replace('-', ':'))
            return variants
        
        model_variants = generate_name_variants(model_name)
        # Aggiungi anche varianti comuni per compatibilità
        model_variants.extend([
            'llama3:8b',
            'llama3.1:8b',
            'llama3:latest'  # Fallback per llama3:8b
        ])
        
        # Verifica se già disponibile (match esatto)
        for variant in model_variants:
            if variant in self.available_models:
                if variant != model_name:
                    print(f"  Modello trovato: {variant}")
                else:
                    print(f"  Modello {normalized_model} già disponibile")
                return True
        
        # Match parziale per compatibilità (gestisce anche gpt-oss:120b vs gpt-oss-120b)
        # Normalizza entrambi i nomi per il confronto (rimuovi : e -)
        normalized_for_match = normalized_model.replace(':', '-').replace('_', '-').lower()
        for available in self.available_models:
            available_normalized = available.replace(':', '-').replace('_', '-').lower()
            
            # Match esatto dopo normalizzazione
            if normalized_for_match == available_normalized:
                print(f"  Modello trovato (match normalizzato): {available}")
                return True
            
            # Match parziale: se contengono le stesse parti chiave
            model_parts = set(normalized_for_match.split('-'))
            available_parts = set(available_normalized.split('-'))
            
            # Se hanno almeno 2 parti in comune (es: "gpt", "oss", "120b")
            common_parts = model_parts & available_parts
            if len(common_parts) >= 2:
                # Verifica che abbiano anche il numero (120b, 70b, ecc.)
                has_number_match = any(p.isdigit() or 'b' in p for p in common_parts)
                if has_number_match:
                    print(f"  Modello compatibile trovato: {available} (cercato: {normalized_model})")
                    return True
            
            # Match per llama3:8b - accetta anche llama3:latest
            if ('llama3' in normalized_model.lower() and 
                'llama3' in available.lower()):
                # Se cerchiamo llama3:8b, accetta anche llama3:latest
                if '8b' in normalized_model.lower() and 'latest' in available.lower():
                    print(f"  Modello compatibile: {available} (usato come fallback per {normalized_model})")
                    return True
                # Match esatto per 8b
                elif '8b' in normalized_model.lower() and '8b' in available.lower():
                    print(f"  Modello compatibile: {available}")
                    return True
        
        # Verifica connessione prima di scaricare
        if not await self._check_connection():
            print(f"ERRORE: Impossibile connettersi a Ollama per scaricare il modello")
            print(f"  SUGGERIMENTO: Verifica che Ollama sia in esecuzione: ollama list")
            return False
        
        # Prima di scaricare, verifica se il modello risponde (potrebbe essere già caricato)
        print(f"  Verifica se il modello {normalized_model} è già pronto...")
        try:
            url = f"{self.ollama_host}/api/generate"
            test_data = {
                "model": normalized_model,
                "prompt": "test",
                "stream": False,
                "options": {"num_predict": 1}
            }
            response = requests.post(url, json=test_data, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get('response'):
                    print(f"  Modello {normalized_model} già disponibile e funzionante!")
                    # Aggiorna la lista dei modelli disponibili
                    await self._get_available_models()
                    return True
        except Exception:
            # Se il test fallisce, procedi con il download
            pass
        
        # Download del modello
        print(f"📥 Download modello {normalized_model}...")
        try:
            # Esegui pull in un thread separato per non bloccare l'event loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.pull(normalized_model)
            )
            for chunk in response:
                if isinstance(chunk, dict) and 'status' in chunk:
                    print(f"📥 {chunk['status']}")
            
            await self._get_available_models()
            if normalized_model in self.available_models:
                return True
            else:
                print(f"Modello {normalized_model} scaricato ma non ancora disponibile")
                return False
            
        except Exception as e:
            error_msg = str(e)
            error_lower = error_msg.lower()
            
            # Controlla se è un errore di connessione
            if 'failed to connect' in error_lower or 'connection' in error_lower or 'refused' in error_lower:
                print(f"Errore di connessione durante il download: {error_msg}")
                print(f"Verifica che Ollama sia in esecuzione: ollama list")
                print(f"Se Ollama non è in esecuzione: ollama serve")
            else:
                print(f"Errore download modello: {error_msg}")
            
            # Suggerimenti utili
            if self.available_models:
                print(f"  SUGGERIMENTO: Modelli disponibili: {', '.join(self.available_models[:3])}")
                if 'llama3' in normalized_model.lower() and any('llama3' in m.lower() for m in self.available_models):
                    llama3_models = [m for m in self.available_models if 'llama3' in m.lower()]
                    print(f"  SUGGERIMENTO: Prova a usare uno di questi modelli llama3: {', '.join(llama3_models)}")
            print(f"  SUGGERIMENTO: Per scaricare manualmente: ollama pull {normalized_model}")
            
            return False
            
    async def _wait_for_model_ready(self, model_name: str, max_wait: int = 300) -> bool:
        """Attende che il modello sia completamente caricato e pronto"""
        import time
        start_time = time.time()
        max_attempts = 10  # Massimo 10 tentativi
        attempt = 0
        
        # Per modelli grandi (120B), aspetta più tempo ma con meno tentativi
        if self._is_120b_model(model_name):
            max_wait = min(max_wait, 300)  # Max 5 minuti per modelli 120B
            wait_between_attempts = 30  # Aspetta 30 secondi tra i tentativi
            print(f"  Modello grande (120B) - verifica caricamento GPU (max {max_attempts} tentativi)...")
        else:
            wait_between_attempts = 10
            print(f"  Attesa caricamento modello {model_name}...")
        
        # Aspetta un po' prima di iniziare i test (il modello potrebbe essere appena iniziato a caricare)
        await asyncio.sleep(15)
        
        while attempt < max_attempts and (time.time() - start_time) < max_wait:
            attempt += 1
            try:
                # Prova una richiesta semplice per verificare se il modello è pronto
                test_data = {
                    "model": model_name,
                    "prompt": "ok",
                    "stream": False,
                    "options": {"num_predict": 2}  # Richiesta minimale
                }
                
                # Timeout breve per il test (se risponde velocemente, è pronto)
                test_timeout = 5
                response, error = await self._make_ollama_request(test_data, timeout=test_timeout)
                
                if error:
                    if isinstance(error, requests.exceptions.Timeout):
                        # Timeout breve significa che il modello potrebbe essere ancora in caricamento
                        elapsed = int(time.time() - start_time)
                        if attempt % 3 == 0:  # Stampa ogni 3 tentativi
                            print(f"  Ancora in caricamento... (tentativo {attempt}/{max_attempts}, {elapsed}s)")
                        await asyncio.sleep(wait_between_attempts)
                        continue
                    elif isinstance(error, requests.exceptions.ConnectionError):
                        # Errore di connessione - Ollama potrebbe essere ancora in caricamento
                        elapsed = int(time.time() - start_time)
                        if attempt % 3 == 0:
                            print(f"  Ollama in caricamento... (tentativo {attempt}/{max_attempts}, {elapsed}s)")
                        await asyncio.sleep(wait_between_attempts)
                        continue
                    else:
                        # Altri errori, considera il modello pronto (potrebbe essere un errore minore)
                        print(f"  Errore durante test: {str(error)[:50]} - considero modello pronto")
                        return True
                
                # Se risponde 200, il modello è pronto (anche se response è vuota)
                if response and response.status_code == 200:
                    result = response.json()
                    # Se ha una risposta o anche solo se risponde 200, è pronto
                    if self._extract_response_from_result(result) or response.status_code == 200:
                        print(f"  Modello {model_name} pronto! (tentativo {attempt}/{max_attempts})")
                        return True
                        
            except Exception as e:
                # Altri errori - se è un errore HTTP diverso da timeout, potrebbe essere pronto
                if '404' in str(e) or 'model not found' in str(e).lower():
                    # Modello non trovato, aspetta
                    elapsed = int(time.time() - start_time)
                    if attempt % 3 == 0:
                        print(f"  Modello non trovato, attendo... (tentativo {attempt}/{max_attempts}, {elapsed}s)")
                    await asyncio.sleep(wait_between_attempts)
                    continue
                else:
                    # Altri errori, considera il modello pronto (potrebbe essere un errore minore)
                    print(f"  Errore durante test: {str(e)[:50]} - considero modello pronto")
                    return True
        
        # Se abbiamo fatto tutti i tentativi o superato il timeout
        if attempt >= max_attempts:
            print(f"  Raggiunto limite tentativi ({max_attempts}) - procedo comunque")
        else:
            print(f"  Timeout attesa modello ({max_wait}s) - procedo comunque")
        return False
    
    async def generate_response_json(self, prompt: str, model: str = None) -> str:
        """Genera risposta in formato JSON puro (senza markdown)"""
        normalized_model = self._get_model_name(model)
        
        # ==================== DEBUG: SALVA PROMPT JSON ====================
        try:
            from pathlib import Path
            logs_dir = Path("logs")
            logs_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prompt_file = logs_dir / f"prompt_json_debug_{timestamp}.txt"
            
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write(f"{'='*70}\n")
                f.write(f"PROMPT JSON DEBUG - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{'='*70}\n\n")
                f.write(f"Modello: {normalized_model}\n")
                f.write(f"Lunghezza prompt: {len(prompt)} caratteri\n")
                f.write(f"Formato: JSON\n")
                f.write(f"\n{'='*70}\n")
                f.write(f"PROMPT:\n")
                f.write(f"{'='*70}\n\n")
                f.write(prompt)
                f.write(f"\n\n{'='*70}\n")
            
            print(f"📝 DEBUG: Prompt JSON salvato in {prompt_file}")
        except Exception as e:
            print(f"⚠️  Errore nel salvare il prompt JSON debug: {e}")
        # ==================== FINE DEBUG ====================
        
        if not await self.ensure_model_exists(normalized_model):
            print(f"Modello {normalized_model} non disponibile")
            return "{}"
        
        # Per modelli grandi, verifica se sono già pronti (ma non aspettare troppo)
        if self._is_120b_model(normalized_model):
            # Solo se non è nella lista, aspetta brevemente
            if normalized_model not in self.available_models:
                await self._wait_for_model_ready(normalized_model, max_wait=60)  # Max 1 minuto
            # Se è nella lista, è già pronto, procedi direttamente
        
        try:
            # Per modelli grandi, aumenta num_predict per assicurarsi che generi abbastanza
            options = self.optimized_params.get('options', {}).copy()
            if self._is_120b_model(normalized_model):
                options['num_predict'] = max(options.get('num_predict', 100), 200)  # Minimo 200 token per JSON
            
            data = {
                "model": normalized_model,
                "prompt": prompt,
                "stream": False,
                "format": "json",  # FORZA OUTPUT JSON
                "options": options
            }
            
            # Retry logic per errori 500 e timeout
            max_retries = 2
            retry_count = 0
            last_exception = None
            
            while retry_count <= max_retries:
                try:
                    response, error = await self._make_ollama_request(data)
                    
                    if error:
                        last_exception = error
                        if isinstance(error, requests.exceptions.Timeout):
                            if retry_count < max_retries:
                                wait_time = (retry_count + 1) * 5
                                print(f"  Timeout (tentativo {retry_count + 1}/{max_retries + 1}) - attendo {wait_time}s...")
                                await asyncio.sleep(wait_time)
                                retry_count += 1
                                continue
                            else:
                                break
                        elif isinstance(error, requests.exceptions.ConnectionError):
                            if retry_count < max_retries:
                                wait_time = (retry_count + 1) * 3
                                print(f"  Errore connessione (tentativo {retry_count + 1}/{max_retries + 1}) - attendo {wait_time}s...")
                                await asyncio.sleep(wait_time)
                                retry_count += 1
                                continue
                            else:
                                break
                        else:
                            break
                    
                    # Gestisci errori HTTP
                    if response.status_code == 500:
                        error_text = response.text[:500] if response.text else "Nessun dettaglio"
                        print(f"  Errore 500 da Ollama (tentativo {retry_count + 1}/{max_retries + 1})")
                        print(f"  Dettagli errore: {error_text}")
                        
                        # Suggerimenti basati sul modello e hardware
                        model_name = data.get('model', normalized_model)
                        if self._is_large_model(model_name):
                            print(f"  Modello grande rilevato ({model_name})")
                            # Controlla se sta usando CPU
                            if 'options' in data and data['options'].get('num_gpu', -1) == 0:
                                print(f"  Modello in modalità CPU-only - potrebbe essere lento o causare errori")
                                print(f"  Suggerimenti:")
                                print(f"     - Verifica che ci sia abbastanza RAM disponibile (serve ~18GB+)")
                                print(f"     - Considera di ridurre num_ctx o num_predict")
                                print(f"     - Aumenta OLLAMA_TIMEOUT in config/default.env")
                            else:
                                print(f"  Il modello potrebbe essere ancora in caricamento su GPU")
                                print(f"  Attendi qualche minuto e riprova")
                        
                        # Per errori 500, aspetta di più prima di riprovare (il modello potrebbe essere occupato)
                        if retry_count < max_retries:
                            wait_time = (retry_count + 1) * 5  # Aumentato a 5s per tentativo
                            print(f"  Attendo {wait_time}s prima di riprovare (modello potrebbe essere occupato)...")
                            await asyncio.sleep(wait_time)
                            retry_count += 1
                            continue
                        else:
                            print(f"  ERRORE: Errore 500 persistente dopo {max_retries + 1} tentativi")
                            
                            # Prova con parametri ridotti
                            print(f"    SUGGERIMENTO: Tentativo con parametri ridotti...")
                            data_reduced = data.copy()
                            if 'options' in data_reduced:
                                data_reduced['options'] = data_reduced['options'].copy()
                                # Riduci drasticamente i parametri
                                data_reduced['options']['num_predict'] = min(
                                    data_reduced['options'].get('num_predict', 200), 100
                                )
                                data_reduced['options']['num_ctx'] = min(
                                    data_reduced['options'].get('num_ctx', 2048), 512
                                )
                            try:
                                response_reduced, _ = await self._make_ollama_request(data_reduced, timeout=60)
                                if response_reduced and response_reduced.status_code == 200:
                                    result_reduced = response_reduced.json()
                                    response_text = self._extract_response_from_result(result_reduced)
                                    if response_text and len(response_text.strip()) > 0:
                                        print(f"  Risposta ricevuta con parametri ridotti ({len(response_text)} char)")
                                        return response_text
                            except Exception as e:
                                print(f"  AVVISO: Anche parametri ridotti hanno fallito: {str(e)[:50]}")
                            
                            # Prova senza formato JSON forzato come ultimo tentativo
                            print(f"    SUGGERIMENTO: Tentativo finale senza formato JSON forzato...")
                            data_no_format = data.copy()
                            if 'format' in data_no_format:
                                del data_no_format['format']
                            # Riduci anche qui i parametri
                            if 'options' in data_no_format:
                                data_no_format['options'] = data_no_format['options'].copy()
                                data_no_format['options']['num_predict'] = min(
                                    data_no_format['options'].get('num_predict', 200), 150
                                )
                            try:
                                response_final, _ = await self._make_ollama_request(data_no_format, timeout=60)
                                if response_final and response_final.status_code == 200:
                                    result_final = response_final.json()
                                    response_text = self._extract_response_from_result(result_final)
                                    if response_text and len(response_text.strip()) > 0:
                                        print(f"  Risposta ricevuta senza formato JSON ({len(response_text)} char)")
                                        return response_text
                            except Exception as e:
                                print(f"  AVVISO: Anche il tentativo finale ha fallito: {str(e)[:50]}")
                            
                            print(f"  ERRORE: Tutti i tentativi falliti - verifica i log di Ollama per dettagli")
                            return "{}"
                    
                    if response.status_code != 200:
                        raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")
                    
                    # Se arriviamo qui, status_code è 200
                    result = response.json()
                    response_text = self._extract_response_from_result(result)
                    
                    # Debug dettagliato se response è ancora vuoto
                    if not response_text or len(response_text.strip()) == 0:
                        print(f"  AVVISO: Risposta JSON vuota da Ollama")
                        print(f"  Debug: status={response.status_code}, keys={list(result.keys())}")
                        
                        # Gestisci risposta vuota con fallback
                        empty_response = await self._handle_empty_response(result, data, normalized_model, prompt)
                        if empty_response:
                            return empty_response
                        
                        # Se ancora vuoto, prova fallback senza formato JSON forzato
                        fallback_response = await self._fallback_without_json_format(data, normalized_model, prompt)
                        if fallback_response:
                            return fallback_response
                        
                        return '{}'
                    
                    # Se abbiamo una risposta valida, restituiscila
                    if response_text and len(response_text.strip()) > 0:
                        return response_text
                    else:
                        return '{}'
                    
                except Exception as e:
                    # Per altri errori, non fare retry (probabilmente errore nel prompt o dati)
                    last_exception = e
                    break
            
            # Gestisci errori finali dopo tutti i retry
            if isinstance(last_exception, requests.exceptions.Timeout):
                print(f"  AVVISO: Timeout generazione JSON dopo {max_retries + 1} tentativi ({self.ollama_timeout}s)")
                if self._is_120b_model(normalized_model):
                    print(f"    SUGGERIMENTO: Per modelli grandi (120B), il timeout potrebbe essere insufficiente")
                print(f"    SUGGERIMENTO: Considera di aumentare OLLAMA_TIMEOUT in config/default.env")
                return "{}"
            elif isinstance(last_exception, requests.exceptions.ConnectionError):
                print(f"  AVVISO: Errore connessione dopo {max_retries + 1} tentativi: {str(last_exception)[:100]}")
                print(f"    SUGGERIMENTO: Il modello potrebbe essere ancora in caricamento")
                print(f"    SUGGERIMENTO: Verifica che Ollama sia in esecuzione: ollama serve")
                return "{}"
            elif last_exception:
                print(f"  AVVISO: Errore generazione JSON: {str(last_exception)[:100]}")
                return "{}"
            else:
                # Nessuna eccezione ma nessuna risposta valida
                return "{}"
                
        except Exception as e:
            print(f"  AVVISO: Errore generazione JSON: {str(e)[:100]}")
            return "{}"
    
    async def generate_response(self, prompt: str, model: str = None, 
                              options: Dict[str, Any] = None, 
                              retry_count: int = 0) -> str:
        """Genera una risposta usando Ollama con fallback automatico a CPU"""
        normalized_model = self._get_model_name(model)
        
        # SALVA PROMPT IN LOG
        if retry_count == 0:  # Solo primo tentativo
            try:
                from pathlib import Path
                from datetime import datetime
                
                logs_dir = Path("logs")
                logs_dir.mkdir(exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                prompt_file = logs_dir / f"prompt_{timestamp}.txt"
                
                with open(prompt_file, 'w', encoding='utf-8') as f:
                    f.write(f"{'='*80}\n")
                    f.write(f"PROMPT LOG - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"{'='*80}\n\n")
                    f.write(f"Modello: {normalized_model}\n")
                    f.write(f"Lunghezza: {len(prompt)} caratteri\n")
                    f.write(f"\n{'='*80}\n")
                    f.write(f"PROMPT:\n")
                    f.write(f"{'='*80}\n\n")
                    f.write(prompt)
                    f.write(f"\n\n{'='*80}\n")
                
                print(f"  💾 Prompt salvato in logs/{prompt_file.name}")
            except Exception as e:
                # Silenzioso - non bloccare l'esecuzione
                pass
        
        # CONTROLLO PREVENTIVO RAM per evitare crash
        import psutil
        available_memory_gb = psutil.virtual_memory().available / (1024**3)
        memory_percent = psutil.virtual_memory().percent
        
        if available_memory_gb < 1.5:
            print(f"AVVISO: RAM MOLTO BASSA: {available_memory_gb:.1f}GB disponibili ({100-memory_percent:.0f}% libera)")
            print(f"  SUGGERIMENTO: RISCHIO CRASH - Chiudi altre applicazioni prima di continuare")
            # Riduci drasticamente i parametri
            if options is None:
                options = {}
            options['num_ctx'] = 256
            options['num_predict'] = 50
            options['num_thread'] = 1
        elif available_memory_gb < 3:
            print(f"AVVISO: RAM limitata: {available_memory_gb:.1f}GB disponibili - usando parametri conservativi")
            if options is None:
                options = {}
            options['num_ctx'] = min(options.get('num_ctx', 512), 512)
            options['num_predict'] = min(options.get('num_predict', 100), 100)
        
   
        if not await self.ensure_model_exists(normalized_model):
            print(f"ERRORE: Modello {normalized_model} non disponibile")
            return ""
        
        # Per modelli grandi, verifica se sono già pronti (ma non aspettare troppo)
        if self._is_120b_model(normalized_model):
            # Solo se non è nella lista, aspetta brevemente
            if normalized_model not in self.available_models:
                await self._wait_for_model_ready(normalized_model, max_wait=60)  # Max 1 minuto
            # Se è nella lista, è già pronto, procedi direttamente
        
        if options is None:
            options = self.optimized_params.get('options', {}).copy()
        else:
            options = options.copy()
        
        # Per modelli grandi, aggiusta i parametri
        options = self._adjust_options_for_large_model(options, normalized_model)
        
        try:
            data = {
                "model": normalized_model,
                "prompt": prompt,
                "stream": False,
                "options": options or {}
            }
            
            response, error = await self._make_ollama_request(data)
            
            if error:
                if isinstance(error, requests.exceptions.Timeout):
                    print(f"AVVISO: Timeout generazione ({self.ollama_timeout}s)")
                    if self._is_120b_model(normalized_model):
                        print(f"  SUGGERIMENTO: Modello 120B molto grande - considera di aumentare OLLAMA_TIMEOUT")
                        print(f"  SUGGERIMENTO: Attualmente: {self.ollama_timeout}s (consigliato: 600s+ per 120B)")
                    if retry_count < 2:
                        print(f"  Tentativo di riconnessione ({retry_count + 1}/2)...")
                        await asyncio.sleep(5)
                        return await self.generate_response(prompt, model, options, retry_count + 1)
                    return ""
                elif isinstance(error, requests.exceptions.ConnectionError):
                    error_str = str(error).lower()
                    if retry_count < 2:
                        print(f"AVVISO: Errore di connessione rilevato: {error}")
                        print(f"  Tentativo di riconnessione ({retry_count + 1}/2)...")
                        await asyncio.sleep(2)
                        return await self.generate_response(prompt, model, options, retry_count + 1)
                    return ""
                else:
                    raise error
            
            if response.status_code == 200:
                result = response.json()
                response_text = self._extract_response_from_result(result)
                
                # Debug per modelli grandi
                if self._is_120b_model(normalized_model):
                    if not response_text or len(response_text.strip()) == 0:
                        print(f"  AVVISO: Risposta vuota da {normalized_model}")
                        print(f"  Debug: done={result.get('done')}, keys={list(result.keys())}")
                        if 'error' in result:
                            print(f"  ERRORE: Errore: {result.get('error')}")
                        # Prova con opzioni diverse
                        print(f"    SUGGERIMENTO: Tentativo con opzioni modificate...")
                        data_retry = data.copy()
                        data_retry['options'] = {
                            'num_predict': 200,  # Aumenta predizioni
                            'temperature': 0.7,  # Aumenta temperatura per più creatività
                            'num_ctx': 2048
                        }
                        try:
                            response_retry, _ = await self._make_ollama_request(data_retry)
                            if response_retry and response_retry.status_code == 200:
                                result_retry = response_retry.json()
                                response_text = self._extract_response_from_result(result_retry)
                                if response_text:
                                    print(f"  Risposta ricevuta con opzioni modificate")
                        except Exception as retry_e:
                            print(f"  AVVISO: Retry fallito: {str(retry_e)[:50]}")
                
                # Se ancora vuoto dopo retry, logga per debug
                if not response_text or len(response_text.strip()) == 0:
                    print(f"  AVVISO: Risposta ancora vuota dopo retry")
                    print(f"    SUGGERIMENTO: Potrebbe essere un problema con il prompt o il modello")
                
                return response_text if response_text else ''
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
        except Exception as e:
            error_str = str(e).lower()
            
            # Controlla se è un errore di connessione
            if ('failed to connect' in error_str or 'connection' in error_str or 
                'refused' in error_str or 'timeout' in error_str or 'cannot connect' in error_str) and retry_count < 2:
                print(f"AVVISO: Errore di connessione rilevato: {e}")
                print(f"  Tentativo di riconnessione ({retry_count + 1}/2)...")
                await asyncio.sleep(2)  # Attendi prima di riprovare
                # Ricrea il client per assicurarsi che sia configurato correttamente
                ollama_config = self.config_manager.get_ollama_config()
                timeout = ollama_config.get('timeout', 30)
                try:
                    self.client = ollama.Client(host=ollama_config['host'], timeout=timeout)
                except TypeError:
                    self.client = ollama.Client(host=ollama_config['host'])
                return await self.generate_response(prompt, model, options, retry_count + 1)
            
            # Controlla se è un errore CUDA di memoria
            if ('cuda' in error_str or 'out of memory' in error_str or 'cudamalloc' in error_str) and retry_count == 0:
                print(f"AVVISO: Errore memoria GPU rilevato: {e}")
                print(f"  Tentativo di recupero: passaggio a modalità solo CPU...")
                
                # Forza CPU-only mode
                options['num_gpu'] = 0
                
                # Riduci anche il contesto per essere conservativi
                if 'num_ctx' in options:
                    options['num_ctx'] = min(options['num_ctx'], 1024)
                
                # Aggiorna le ottimizzazioni persistenti per i prossimi tentativi
                if 'options' in self.optimized_params:
                    self.optimized_params['options']['num_gpu'] = 0
                    self.optimized_params['options']['num_ctx'] = min(
                        self.optimized_params['options'].get('num_ctx', 1024), 
                        1024
                    )
                
                # Retry con CPU
                return await self.generate_response(
                    prompt=prompt, 
                    model=model, 
                    options=options,
                    retry_count=1
                )
            
            # Se è ancora un errore dopo retry, o è un altro tipo di errore
            if retry_count > 0:
                print(f"ERRORE: Errore persistente dopo retry con CPU: {e}")
                print("[INFO] WhatsApp caricato, ma Ollama non disponibile.")
                print("[INFO] Soluzioni:")
                print("   1. Assicurati che Ollama sia in esecuzione (ollama serve)")
                print("   2. Verifica che Ollama sia raggiungibile su http://127.0.0.1:11434")
                print("   3. Controlla i log di Ollama per eventuali errori")
            else:
                print(f"ERRORE: Errore generazione: {e}")
            
            # Controlla se è un messaggio vuoto
            if 'response' in error_str or 'empty' in error_str:
                print(f"AVVISO: Messaggio vuoto generato - possibile problema con il prompt")
            
            return ""

    # ============================================================================
    # ANALISI TARGET - Funzioni ottimizzate per profilazione persona
    # ============================================================================
    
    async def generate_additional_search_queries(self, initial_results: List[Dict[str, Any]], 
                                                  subject: str) -> List[str]:
        """
        Usa l'LLM per generare query di ricerca aggiuntive basate sui risultati iniziali
        
        Args:
            initial_results: Risultati della ricerca iniziale
            subject: Nome del soggetto da ricercare
            
        Returns:
            Lista di query di ricerca aggiuntive
        """
        # Combina i risultati iniziali per il contesto
        combined_text = "\n".join([
            f"- {r.get('title', '')}: {r.get('snippet', '')[:200]}"
            for r in initial_results[:5]
        ])
        
        # USA PROMPT DA prompts.py
        prompt_text = AIPrompts.generate_search_queries(
            subject=subject,
            context=combined_text[:1000]
        )
        
        # Wrapper per ottenere JSON
        prompt = f"""{prompt_text}

Rispondi in formato JSON:
{{
  "queries": ["query1", "query2", "query3"]
}}
"""
        
        print(f"  Generazione query di ricerca aggiuntive con LLM...")
        response = await self.generate_response_json(prompt)
        
        if response and response != '{}':
            try:
                queries_data = self._parse_json_response(response)
                queries = queries_data.get('queries', [])
                if queries:
                    print(f"  Generate {len(queries)} query aggiuntive")
                    return queries[:5]  # Max 5 query
            except:
                pass
        
        # Fallback: query generiche basate sul nome
        print(f"  AVVISO: Fallback a query generiche")
        return [
            f'"{subject}" LinkedIn',
            f'"{subject}" pubblicazioni',
            f'"{subject}" progetti',
            f'"{subject}" interviste'
        ]
    
    async def analyze_target_profile(self, search_results: List[Dict[str, Any]], 
                                     web_searcher=None) -> Dict[str, Any]:
        """
        Analisi completa del target da risultati di ricerca con ricerche aggiuntive guidate da LLM
        USA UNA CONVERSAZIONE PERSISTENTE invece di chiamate indipendenti
        
        Args:
            search_results: Risultati della ricerca iniziale
            web_searcher: Istanza di WebSearcher per ricerche aggiuntive (opzionale)
        
        Returns:
            Dict con: name, work, location, skills, interests, summary, explanation, social_profiles
        """
        # Resetta la conversazione all'inizio di una nuova analisi
        if self.use_persistent_conversation:
            self.clear_conversation()
            print(f"  Avvio conversazione persistente per analisi target...")
        
        combined_text = "\n".join([
            r.get('snippet', '') for r in search_results[:10]
        ])
        
        # DEBUG: mostra cosa abbiamo estratto
        print(f"  Testo combinato ({len(combined_text)} char): {combined_text[:200]}...")
        
        if not combined_text or len(combined_text) < 50:
            print(f"  AVVISO: Testo insufficiente per analisi")
            return self._empty_profile()
        
        # STEP 1: Analisi iniziale per estrarre nome base (usando conversazione)
        print(f"  Analisi iniziale per identificare il soggetto...")
        # USA PROMPT DA prompts.py
        prompt_text = AIPrompts.extract_name(combined_text[:500])
        initial_prompt = f"""{prompt_text}

Rispondi in formato JSON:
{{
  "name": "Nome Cognome o Sconosciuto"
}}
"""
        
        if self.use_persistent_conversation:
            initial_response = await self.chat_completion(
                messages=[{"role": "user", "content": initial_prompt}],
                use_history=True
            )
        else:
            initial_response = await self.generate_response_json(initial_prompt)
        
        initial_profile = self._parse_json_response(initial_response) if initial_response else {}
        subject_name = initial_profile.get('name', 'Sconosciuto')
        
        # STEP 2: Se abbiamo un web_searcher, genera e esegui ricerche aggiuntive guidate da LLM
        additional_results = []
        if web_searcher and subject_name != 'Sconosciuto':
            print(f"\n  Ricerche aggiuntive guidate da LLM per '{subject_name}'...")
            try:
                # Genera query aggiuntive usando la conversazione (sa già il nome!)
                # USA PROMPT DA prompts.py
                prompt_text = AIPrompts.generate_search_queries(
                    subject=subject_name,
                    context="Basandoti sulla conversazione precedente"
                )
                query_prompt = f"""{prompt_text}

Rispondi in formato JSON:
{{
  "queries": ["query1", "query2", "query3"]
}}
"""
                
                if self.use_persistent_conversation:
                    query_response = await self.chat_completion(
                        messages=[{"role": "user", "content": query_prompt}],
                        use_history=True
                    )
                else:
                    query_response = await self.generate_response_json(query_prompt)
                
                queries_data = self._parse_json_response(query_response) if query_response else {}
                additional_queries = queries_data.get('queries', [])
                
                if not additional_queries:
                    # Fallback a query generiche
                    additional_queries = [
                        f'"{subject_name}" LinkedIn',
                        f'"{subject_name}" pubblicazioni',
                        f'"{subject_name}" progetti'
                    ]
                
                # Esegui le ricerche aggiuntive
                for i, query in enumerate(additional_queries[:5], 1):
                    print(f"    📡 ({i}/{len(additional_queries[:5])}): {query}")
                    try:
                        results = await web_searcher._search_term(query)
                        additional_results.extend(results[:3])  # Max 3 risultati per query
                        await asyncio.sleep(0.5)  # Delay tra ricerche
                    except Exception as e:
                        print(f"    AVVISO: Errore ricerca '{query}': {str(e)[:50]}")
                
                if additional_results:
                    print(f"  Trovati {len(additional_results)} risultati aggiuntivi")
                    # Combina con i risultati iniziali
                    all_results = search_results + additional_results
                    # Aggiorna il testo combinato
                    additional_text = "\n".join([
                        r.get('snippet', '') for r in additional_results[:10]
                    ])
                    combined_text = combined_text + "\n\n--- RICERCHE AGGIUNTIVE ---\n" + additional_text
            except Exception as e:
                print(f"  AVVISO: Errore nelle ricerche aggiuntive: {str(e)[:50]}")
        
        # STEP 3: Analisi completa con tutti i dati (usando conversazione - sa già tutto!)
        model_name = self.config_manager.get('ollama_model', 'llama3:8b')
        is_large_model = self._is_large_model(model_name)
        
        # Limita il testo in base al modello
        max_text_length = 2000 if is_large_model else 3000
        truncated_text = combined_text[:max_text_length]
        
        # USA PROMPT DA prompts.py
        prompt_text = AIPrompts.create_comprehensive_profile(
            context="Basandoti sulla conversazione precedente",
            new_info=truncated_text
        )
        
        final_prompt = f"""{prompt_text}

REGOLE CRITICHE:
1. "name": SOLO nome e cognome (max 50 caratteri, NO descrizioni lavorative)
2. "explanation": Spiegazione dettagliata del profilo (3-5 frasi)

Rispondi in formato JSON:
{{
  "name": "Nome Cognome o Sconosciuto",
  "work": "Ruolo professionale",
  "location": "Città, Regione",
  "skills": ["competenza1", "competenza2"],
  "interests": ["interesse1", "interesse2"],
  "summary": "Riassunto professionale (2-3 frasi)",
  "explanation": "Spiegazione dettagliata (3-5 frasi)",
  "social_profiles": ["piattaforma1"],
  "recent_activities": ["attività1"],
  "key_achievements": ["realizzazione1"],
  "education": "Titolo di studio"
}}
"""
        
        # Usa conversazione persistente invece di chiamata stateless
        if self.use_persistent_conversation:
            print(f"  Analisi completa con conversazione persistente...")
            response = await self.chat_completion(
                messages=[{"role": "user", "content": final_prompt}],
                use_history=True
            )
        else:
            print(f"  Analisi completa con formato JSON...")
            response = await self.generate_response_json(final_prompt)
        
        # DEBUG: mostra risposta AI
        if response and response.strip() and response != '{}':
            print(f"  Risposta AI ricevuta ({len(response)} char): {response[:200]}...")
        else:
            print(f"  AVVISO: Risposta vuota - tentativo con metodo alternativo...")
            if not self.use_persistent_conversation:
                response = await self.generate_response(final_prompt)
            if not response or not response.strip():
                print(f"  AVVISO: Anche il metodo alternativo ha fallito")
        
        profile = self._parse_json_response(response) if response else {}
        
        # DEBUG: mostra profilo parsato
        if profile:
            print(f"  Profilo parsato: name={profile.get('name', 'N/A')}, work={profile.get('work', 'N/A')[:50]}")
            if self.use_persistent_conversation:
                print(f"  Conversazione completata ({len(self.conversation_history)} messaggi)")
        else:
            print(f"  AVVISO: Profilo vuoto dopo parsing")
            print(f"  Risposta originale (primi 500 char): {response[:500] if response else 'Nessuna risposta'}")
        
        # Validazione e pulizia del profilo
        return self._validate_and_clean_profile(profile)
    
    async def _analyze_initial_profile(self, text: str) -> Dict[str, Any]:
        """Analisi rapida iniziale per estrarre solo il nome"""
        # USA PROMPT DA prompts.py
        prompt_text = AIPrompts.extract_name(text[:500])
        prompt = f"""{prompt_text}

Rispondi in formato JSON:
{{
  "name": "Nome Cognome o Sconosciuto"
}}
"""
        response = await self.generate_response_json(prompt)
        profile = self._parse_json_response(response) if response else {}
        return profile if profile else {'name': 'Sconosciuto'}
    
    async def extract_personality_traits(self, profile: Dict[str, Any], 
                                        additional_text: str = "") -> Dict[str, Any]:
        """
        Estrae tratti di personalità utili per social engineering
        
        Returns:
            Dict con: communication_style, likely_triggers, vulnerabilities, approach_strategy
        """
        context = f"""
Profilo: {json.dumps(profile, ensure_ascii=False)}
Testo aggiuntivo: {additional_text[:1000]}
"""
        
        # USA PROMPT DA prompts.py
        prompt = AIPrompts.analyze_profile_for_contact(context)
        
        response = await self.generate_response(prompt)
        return self._parse_json_response(response)
    
    async def analyze_social_media_presence(self, profile: Dict[str, Any],
                                           social_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analizza la presenza sui social media del target
        
        Returns:
            Dict con: activity_level, posting_patterns, topics, sentiment, engagement_style
        """
        social_text = "\n".join([
            f"{item.get('platform', 'unknown')}: {item.get('content', '')[:200]}"
            for item in social_data[:5]
        ])
        
        # USA PROMPT DA prompts.py
        prompt = AIPrompts.analyze_social_media_presence(
            profile_name=profile.get('name', 'Sconosciuto'),
            work=profile.get('work', ''),
            social_data=social_text
        )
        
        response = await self.generate_response(prompt)
        return self._parse_json_response(response)

    # ============================================================================
    # GENERAZIONE MESSAGGI - Funzioni ottimizzate per WhatsApp
    # ============================================================================
    
    async def generate_initial_contact_message(self,
                                              target_info: Dict[str, Any],
                                              context: str = "auto",
                                              scenario: str = "richiesta_consulenza",
                                              urgency: str = "media",
                                              ai_summary: str = "") -> str:
        """
        Genera messaggio di primo contatto ottimizzato e naturale
        
        Args:
            target_info: Informazioni sul target
            context: "auto" (LLM sceglie) o manuale (professionale/colleghi/networking)
            scenario: richiesta_consulenza/collaborazione/informazione/urgenza
            urgency: bassa/media/alta
            ai_summary: Riassunto AI in linguaggio naturale per creare contesto migliore
            
        Returns:
            Messaggio WhatsApp naturale e credibile
        """
        name = self._extract_clean_name(target_info.get('name', ''))
        work = target_info.get('work', 'professionista')
        
        # Mappa scenario alla descrizione per il prompt
        scenario_descriptions = {
            "richiesta_consulenza": "ha bisogno di consulenza/aiuto",
            "collaborazione": "propone collaborazione/progetto",
            "informazione": "cerca informazioni",
            "urgenza": "ha urgenza/problema da risolvere"
        }
        scenario_desc = scenario_descriptions.get(scenario, "ha bisogno di aiuto")
        
        # Prepara le informazioni contestuali
        context_info = f"Nome: {name}\nLavoro: {work}"
        if target_info.get('location'):
            context_info += f"\nLocalità: {target_info['location']}"
        
        # USA IL PROMPT MIGLIORATO da prompts.py
        if AIPrompts is None:
            print("⚠️  AVVISO: AIPrompts non disponibile, uso prompt semplificato")
            # Fallback se AIPrompts non è disponibile
            first_name = name.split()[0] if name else "una persona"
            prompt = f"""Scrivi un messaggio WhatsApp naturale e completo per contattare {first_name}.
Usa un nome italiano reale (Marco, Luca, Andrea, Giulia).
Presentati brevemente e chiedi disponibilità con un motivo credibile.
Max 1000 caratteri. Tono colloquiale.
NON usare emoji.

Messaggio:"""
        else:
            prompt = AIPrompts.generate_social_engineering_message(
                name=name,
                context_info=context_info,
                impersonation_context=context,
                scenario_desc=scenario_desc,
                work=work,
                ai_summary=ai_summary,
                max_length=1000
            )
        
        # Genera il messaggio
        message = await self.generate_response(prompt)
        
        # Pulizia base: strip e rimuovi virgolette
        message = message.strip()
        if (message.startswith('"') and message.endswith('"')) or \
           (message.startswith("'") and message.endswith("'")):
            message = message[1:-1].strip()
        
        # Debug: verifica se la risposta è vuota
        if not message or len(message.strip()) == 0:
            print(f"  AVVISO: Risposta vuota da generate_response, tentativo con prompt semplificato...")
            # Fallback: prompt più semplice e diretto
            simple_prompt = f"""Scrivi un messaggio WhatsApp completo e naturale (max 1000 caratteri) per contattare {name if name and name != 'Sconosciuto' else 'una persona'}.

Messaggio:"""
            message = await self.generate_response(simple_prompt)
            
            # Se ancora vuoto, usa un messaggio template migliorato
            if not message or len(message.strip()) == 0:
                print(f"  AVVISO: Anche il prompt semplificato ha fallito, uso template...")
                # Template di fallback (SENZA frasi spam e emoji)
                import random
                nomi_italiani = ['Luca', 'Marco', 'Andrea', 'Francesco', 'Giulia', 'Matteo']
                nome_random = random.choice(nomi_italiani)
                first_name = name.split()[0] if name else "ciao"
                # Usa frasi più naturali e credibili
                message = f"Ciao {first_name}, sono {nome_random}. Ti posso disturbare un attimo per una cosa veloce?"
        
        # Rimuovi solo emoji (niente altra pulizia aggressiva)
        import re
        message = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251]+', '', message)
        message = message.strip()
        
        # Mostra messaggio iniziale generato
        print("\n" + "="*80)
        print("📝 MESSAGGIO INIZIALE GENERATO:")
        print("="*80)
        print(f"{message}")
        print("="*80 + "\n")
        
        # VALIDAZIONE POST-GENERAZIONE: controlla placeholder non sostituiti
        placeholder_patterns = ['[nome]', '[nome proprio]', '[professione generica]', '[NOME', '[professione]']
        has_placeholder = any(pattern.lower() in message.lower() for pattern in placeholder_patterns)
        
        if has_placeholder:
            print(f"  [FIX] Messaggio contiene placeholder, lo correggo...")
            # Prova a fixare sostituendo i placeholder con valori casuali
            import random
            nomi_italiani = ['Luca', 'Marco', 'Andrea', 'Francesco', 'Giulia', 'Matteo', 'Alessandro', 'Davide']
            professioni = ['consulente', 'freelance', 'lavoro in uno studio', 'professionista']
            
            nome_random = random.choice(nomi_italiani)
            prof_random = random.choice(professioni)
            
            message = message.replace('[nome proprio]', nome_random)
            message = message.replace('[nome]', nome_random)
            message = message.replace('[NOME REALE]', nome_random)
            message = message.replace('[professione generica]', prof_random)
            message = message.replace('[professione]', prof_random)
            
            print(f"  [OK] Placeholder sostituiti automaticamente")
        
        # VALIDAZIONE: verifica che inizi con saluto
        first_name = name.split()[0] if name else "ciao"
        if not (message.lower().startswith('ciao') or message.lower().startswith('salve') or message.lower().startswith('buongiorno')):
            print(f"  [FIX] Messaggio senza saluto, lo aggiungo...")
            # Genera un nome italiano casuale
            import random
            nomi_italiani = ['Marco', 'Luca', 'Andrea', 'Francesco', 'Giulia', 'Matteo', 'Alessandro', 'Davide', 'Stefano', 'Paolo']
            nome_mittente = random.choice(nomi_italiani)
            message = f"Ciao {first_name}, sono {nome_mittente}, {message}"
            print(f"  [OK] Saluto aggiunto: 'Ciao {first_name}, sono {nome_mittente}'")
        
        # CORREZIONE SINTASSI: usa LLM per migliorare punteggiatura e leggibilità
        # Prepara informazioni target per double-check contenuto
        target_info_text = f"Nome: {name}\nLavoro: {work}"
        if ai_summary:
            target_info_text += f"\n{ai_summary[:300]}"
        
        print("  [SYNTAX] Correzione sintassi + verifica contenuto con LLM...")
        message = await self._fix_message_syntax(message, target_info_text)
        print("  [OK] Sintassi corretta e contenuto verificato!")
        
        # Mostra messaggio finale dopo fine tuning
        print("\n" + "="*80)
        print("✅ MESSAGGIO FINALE (DOPO FINE TUNING):")
        print("="*80)
        print(f"{message}")
        print("="*80 + "\n")
        
        return message
    
    async def generate_followup_message(self,
                                       conversation_history: List[Dict[str, str]],
                                       target_info: Dict[str, Any],
                                       goal: str = "maintain_engagement") -> str:
        """
        Genera messaggio di follow-up contestuale
        
        Args:
            conversation_history: [{"role": "user/assistant", "content": "..."}]
            target_info: Info sul target
            goal: maintain_engagement/request_action/provide_info/build_trust
            
        Returns:
            Messaggio di risposta naturale
        """
        # Estrai ultimi 3 messaggi per contesto
        recent_messages = conversation_history[-3:] if len(conversation_history) > 3 else conversation_history
        
        conversation_context = "\n".join([
            f"{'Tu' if msg['role'] == 'assistant' else 'Target'}: {msg['content']}"
            for msg in recent_messages
        ])
        
        name = self._extract_clean_name(target_info.get('name', ''))
        
        # USA PROMPT DA prompts.py
        prompt = AIPrompts.generate_followup_message(
            conversation_history=conversation_context,
            target_name=name if name and name != 'Sconosciuto' else 'Persona',
            goal=goal
        )
        
        response = await self.generate_response(prompt)
        return self._clean_message(response, max_length=500)
    
    async def adapt_message_to_response(self,
                                       original_message: str,
                                       target_response: str,
                                       target_info: Dict[str, Any]) -> str:
        """
        Adatta il tuo messaggio basandoti sulla risposta del target
        
        Returns:
            Messaggio adattato al tono e contenuto della risposta
        """
        # USA PROMPT DA prompts.py
        target_name = target_info.get('name', 'Persona')
        context = f"TARGET: {target_name} - {target_info.get('work', '')}"
        
        prompt = AIPrompts.generate_reply_to_response(
            original_message=original_message,
            target_response=target_response,
            target_name=target_name,
            context=context
        )
        
        response = await self.generate_response(prompt)
        return self._clean_message(response, max_length=500)
    
    async def generate_social_engineering_message(self, 
                                                  target_info: Dict[str, Any],
                                                  impersonation_context: str = "auto",
                                                  scenario: str = "richiesta_aiuto",
                                                  max_length: int = 1000,
                                                  ai_summary: str = "") -> str:
        """
        Genera un messaggio di social engineering rivolto alla persona target
        (Metodo legacy per compatibilità - usa generate_initial_contact_message)
        
        Args:
            target_info: Informazioni sul target
            impersonation_context: Chi fingere di essere
            scenario: Tipo di scenario
            max_length: Lunghezza massima messaggio
            ai_summary: Riassunto AI in linguaggio naturale per creare contesto migliore
        """
        # Mappa scenari legacy a nuovi
        scenario_map = {
            "richiesta_aiuto": "richiesta_consulenza",
            "urgenza": "urgenza",
            "opportunità": "collaborazione",
            "problema_tecnico": "richiesta_consulenza"
        }
        
        new_scenario = scenario_map.get(scenario, "richiesta_consulenza")
        urgency = "alta" if scenario == "urgenza" else "media"
        
        return await self.generate_initial_contact_message(
            target_info=target_info,
            context=impersonation_context,
            scenario=new_scenario,
            urgency=urgency,
            ai_summary=ai_summary
        )
    
    async def generate_conversational_response(self,
                                             conversation_history: List[Dict[str, str]],
                                             target_info: Dict[str, Any],
                                             impersonation_context: str = "auto",
                                             scenario: str = "richiesta_aiuto",
                                             max_length: int = 200) -> str:
        """Genera una risposta contestuale basata sulla conversazione con strategia social engineering"""
        from src.prompts import AIPrompts
        
        # Usa il prompt dettagliato con strategia progressiva di social engineering
        prompt = AIPrompts.generate_conversational_response(
            conversation_history=conversation_history,
            target_info=target_info,
            impersonation_context=impersonation_context,
            scenario=scenario,
            max_length=max_length
        )
        
        response = await self.generate_response(prompt)
        
        # Pulizia minima: solo strip e virgolette
        response = response.strip()
        if (response.startswith('"') and response.endswith('"')) or \
           (response.startswith("'") and response.endswith("'")):
            response = response[1:-1].strip()
        
        # Rimuovi punto finale se presente
        if response.endswith('.'):
            response = response[:-1]
        
        # Rimuovi emoji
        import re
        response = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251]+', '', response)
        response = response.strip()
        
        # Mostra messaggio iniziale generato
        print("\n" + "="*80)
        print("📝 RISPOSTA INIZIALE GENERATA:")
        print("="*80)
        print(f"{response}")
        print("="*80 + "\n")
        
        # FINE TUNING: Correzione sintassi CONSERVATIVA per conversazioni
        name = target_info.get('name', '')
        work = target_info.get('work', '')
        
        # Prepara informazioni target per double-check contenuto
        target_info_text = f"Nome: {name}\nLavoro: {work}"
        full_context = target_info.get('full_context', '')
        if full_context:
            target_info_text += f"\n{full_context[:300]}"
        
        # Costruisci storico conversazione per contesto
        conversation_text = ""
        for msg in conversation_history[-4:]:  # Ultimi 4 messaggi
            role = "Tu" if msg.get('role') == 'assistant' else name
            content = msg.get('content', '')[:100]  # Max 100 char per messaggio
            conversation_text += f"{role}: {content}\n"
        
        print("  [SYNTAX] Correzione sintassi CONSERVATIVA (no espansioni)...")
        response = await self._fix_conversation_message_syntax(
            response, 
            conversation_history=conversation_text,
            target_info=target_info_text
        )
        print("  [OK] Sintassi corretta senza espansioni!")
        
        # Mostra messaggio finale dopo fine tuning
        print("\n" + "="*80)
        print("✅ RISPOSTA FINALE (DOPO FINE TUNING):")
        print("="*80)
        print(f"{response}")
        print("="*80 + "\n")
        
        return response
    
    async def summarize_information(self, information: List[str], 
                                  max_sentences: int = 3) -> str:
        """Riassume una lista di informazioni"""
        # USA PROMPT DA prompts.py
        prompt = AIPrompts.summarize_information(
            information_list=information,
            max_sentences=max_sentences
        )
        return await self.generate_response(prompt)
    
    async def generate_whatsapp_message(self, content: str, 
                                      tone: str = "professionale",
                                      max_length: int = 280) -> str:
        """Genera un messaggio WhatsApp ottimizzato"""
        # USA PROMPT DA prompts.py
        prompt = AIPrompts.generate_whatsapp_message(
            content=content,
            tone=tone,
            max_length=max_length
        )
        message = await self.generate_response(prompt)
        message = self._clean_message(message, max_length)
        return message
    
    async def analyze_text(self, text: str, analysis_type: str = "general") -> Dict[str, Any]:
        """Analizza un testo e restituisce informazioni strutturate"""
        # USA PROMPT DA prompts.py
        if analysis_type == "general":
            prompt = AIPrompts.analyze_text(text)
        elif analysis_type == "sentiment":
            prompt = AIPrompts.analyze_sentiment(text)
        elif analysis_type == "summary":
            prompt = AIPrompts.summarize_text(text)
        else:
            prompt = AIPrompts.analyze_text(text)
        
        response = await self.generate_response(prompt)
        
        if analysis_type == "sentiment":
            return {"sentiment": response.strip().lower()}
        elif analysis_type == "summary":
            return {"summary": response.strip()}
        else:
            return self._parse_json_response(response)
    
    async def chat_completion(self, messages: List[Dict[str, str]] = None, 
                            model: str = None,
                            temperature: float = 0.3,
                            use_history: bool = True) -> str:
        """
        Completamento chat conversazionale con supporto per conversazione persistente
        
        Args:
            messages: Lista di messaggi (se None, usa conversation_history)
            model: Nome modello
            temperature: Temperatura per generazione
            use_history: Se True, mantiene la conversazione persistente
        """
        normalized_model = self._get_model_name(model)
        
        # Se use_history è True e abbiamo conversation_history, aggiungi i nuovi messaggi
        if use_history and self.use_persistent_conversation:
            if messages is None:
                messages = self.conversation_history.copy()
            else:
                # Combina history esistente con nuovi messaggi
                messages = self.conversation_history + messages
        
        if messages is None:
            messages = []
        
        try:
            # Usa l'API chat di Ollama che supporta conversazioni
            response = self.client.chat(
                model=normalized_model,
                messages=messages,
                options={
                    'temperature': temperature,
                    'num_ctx': self.optimized_params.get('options', {}).get('num_ctx', 2048)
                }
            )
            
            response_content = response['message']['content']
            
            # Aggiorna la conversazione persistente
            if use_history and self.use_persistent_conversation:
                # Aggiungi i nuovi messaggi alla history
                if messages != self.conversation_history:
                    # Aggiungi solo i nuovi messaggi
                    new_messages = messages[len(self.conversation_history):]
                    self.conversation_history.extend(new_messages)
                # Aggiungi la risposta
                self.conversation_history.append({
                    'role': 'assistant',
                    'content': response_content
                })
            
            return response_content
        except Exception as e:
            print(f"ERRORE: Errore nel completamento chat: {e}")
            return ""
    
    def clear_conversation(self):
        """Pulisce la conversazione persistente"""
        self.conversation_history = []
        print("  Conversazione resettata")
    
    def get_conversation_history(self) -> List[Dict[str, str]]:
        """Restituisce la conversazione corrente"""
        return self.conversation_history.copy()
    
    async def generate_embeddings(self, text: str, model: str = None) -> List[float]:
        """Genera embeddings per il testo"""
        normalized_model = self._get_model_name(model)
        
        try:
            response = self.client.embeddings(
                model=normalized_model,
                prompt=text
            )
            return response.get('embedding', [])
        except Exception as e:
            print(f"ERRORE: Errore nella generazione embeddings: {e}")
            return []
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Ottiene statistiche di utilizzo"""
        try:
            stats = self.client.list()
            return {
                'models_count': len(self.available_models),
                'total_models': len(stats.get('models', [])),
                'system_info': stats.get('system', {})
            }
        except Exception as e:
            return {
                'models_count': len(self.available_models),
                'error': str(e)
            }

    # ============================================================================
    # FUNZIONI DI SUPPORTO
    # ============================================================================
    
    def _is_large_model(self, model_name: str) -> bool:
        """Verifica se il modello è grande (70B, 120B, ecc.)"""
        if not model_name:
            return False
        model_lower = str(model_name).lower()
        return '120b' in model_lower or '70b' in model_lower or '30b' in model_lower
    
    def _is_120b_model(self, model_name: str) -> bool:
        """Verifica se il modello è 120B"""
        if not model_name:
            return False
        return '120b' in str(model_name).lower()
    
    def _get_model_name(self, model: str = None) -> str:
        """Ottiene e normalizza il nome del modello"""
        if model is None:
            model = self.config_manager.get('ollama_model', 'llama3:8b')
        return self._normalize_model_name(model)
    
    def _extract_response_from_result(self, result: Dict[str, Any]) -> str:
        """Estrae la risposta da un result Ollama (controlla sia 'response' che 'thinking')"""
        # PRIMA: Controlla se c'è un campo "thinking" (alcuni modelli come qwen lo usano)
        if 'thinking' in result and result.get('thinking'):
            thinking_text = result.get('thinking', '').strip()
            if thinking_text and len(thinking_text) > 0:
                return thinking_text
        
        # Poi controlla 'response'
        response_text = result.get('response', '')
        return response_text if response_text else ''
    
    async def _make_ollama_request(self, data: Dict[str, Any], timeout: int = None) -> Tuple[Optional[requests.Response], Optional[Exception]]:
        """Esegue una richiesta HTTP a Ollama con gestione errori comune"""
        if timeout is None:
            timeout = self.ollama_timeout
        
        url = f"{self.ollama_host}/api/generate"
        
        try:
            response = requests.post(url, json=data, timeout=timeout)
            
            # Se è un errore 500, prova a estrarre più informazioni per debug
            if response.status_code == 500:
                try:
                    error_json = response.json()
                    if 'error' in error_json:
                        # Il testo dell'errore è già in response.text, ma lo miglioriamo
                        pass
                except:
                    # Se non è JSON, usa il testo così com'è
                    pass
            
            return response, None
        except requests.exceptions.Timeout as e:
            return None, e
        except requests.exceptions.ConnectionError as e:
            return None, e
        except Exception as e:
            return None, e
    
    async def _handle_empty_response(self, result: Dict[str, Any], data: Dict[str, Any], 
                                     normalized_model: str, prompt: str) -> Optional[str]:
        """Gestisce risposte vuote con fallback logic"""
        response_text = self._extract_response_from_result(result)
        
        if response_text and len(response_text.strip()) > 0:
            return response_text
        
        # Controlla se c'è un errore nella risposta
        if 'error' in result:
            print(f"  ERRORE: Errore da Ollama: {result.get('error')}")
            return None
        
        # Controlla se done è False (modello ancora in elaborazione)
        if result.get('done') == False:
            print(f"  Modello ancora in elaborazione (done=False)...")
            print(f"    SUGGERIMENTO: Attendo completamento...")
            await asyncio.sleep(2)
            
            # Riprova con gli stessi parametri
            try:
                retry_response, error = await self._make_ollama_request(data)
                if retry_response and retry_response.status_code == 200:
                    retry_result = retry_response.json()
                    retry_text = self._extract_response_from_result(retry_result)
                    if retry_text and len(retry_text.strip()) > 0:
                        print(f"  Risposta ricevuta dopo attesa ({len(retry_text)} char)")
                        return retry_text
            except Exception as e:
                print(f"  AVVISO: Retry fallito: {str(e)[:50]}")
        
        return None
    
    async def _fallback_without_json_format(self, data: Dict[str, Any], normalized_model: str, 
                                            prompt: str) -> Optional[str]:
        """Tenta fallback senza formato JSON forzato"""
        print(f"    SUGGERIMENTO: Tentativo senza formato JSON forzato...")
        data_no_format = data.copy()
        if 'format' in data_no_format:
            del data_no_format['format']
        
        # Aumenta num_predict per il fallback (soprattutto per modelli grandi)
        base_num_predict = data_no_format['options'].get('num_predict', 200)
        if self._is_large_model(normalized_model):
            data_no_format['options']['num_predict'] = max(base_num_predict, 500)
        else:
            data_no_format['options']['num_predict'] = max(base_num_predict, 400)
        
        data_no_format['options']['temperature'] = 0.7  # Più creatività
        data_no_format['options']['top_p'] = 0.9  # Migliora la qualità
        
        try:
            response, error = await self._make_ollama_request(data_no_format)
            if response and response.status_code == 200:
                result = response.json()
                response_text = self._extract_response_from_result(result)
                
                if response_text and len(response_text.strip()) > 0:
                    print(f"  Risposta ricevuta senza formato JSON forzato ({len(response_text)} char)")
                    return response_text
                else:
                    print(f"  AVVISO: Anche il fallback ha restituito risposta vuota")
                    print(f"  Fallback debug: done={result.get('done')}, eval_count={result.get('eval_count')}")
                    # Ultimo tentativo: usa generate_response normale
                    print(f"    SUGGERIMENTO: Ultimo tentativo con generate_response normale...")
                    try:
                        normal_response = await self.generate_response(
                            prompt, model=normalized_model, options=data_no_format['options']
                        )
                        if normal_response and len(normal_response.strip()) > 0:
                            print(f"  Risposta ricevuta con generate_response ({len(normal_response)} char)")
                            return normal_response
                    except Exception as normal_e:
                        print(f"  AVVISO: Anche generate_response normale ha fallito: {str(normal_e)[:50]}")
            else:
                print(f"  ERRORE: Fallback fallito: HTTP {response.status_code if response else 'N/A'}")
        except Exception as e:
            print(f"  ERRORE: Errore nel fallback: {str(e)[:100]}")
        
        return None
    
    def _adjust_options_for_large_model(self, options: Dict[str, Any], normalized_model: str) -> Dict[str, Any]:
        """Aggiusta le opzioni per modelli grandi"""
        if self._is_120b_model(normalized_model):
            options['num_predict'] = max(options.get('num_predict', 100), 300)  # Minimo 300 token
            options['temperature'] = max(options.get('temperature', 0.3), 0.7)  # Più creatività
            options['top_p'] = 0.95
            options['num_ctx'] = min(options.get('num_ctx', 2048), 4096)  # Contesto maggiore
        elif self._is_large_model(normalized_model):
            options['num_predict'] = max(options.get('num_predict', 100), 200)
        
        return options
    
    def _extract_clean_name(self, name: str) -> str:
        """Estrae e pulisce il nome da descrizioni lavorative"""
        if not name or name.lower() == 'sconosciuto':
            return 'Sconosciuto'
        
        # Keyword che indicano descrizioni lavorative
        work_keywords = [
            'CTP', 'CTU', 'Perizie', 'Forensi', 'Informatiche',
            'Civile', 'Penale', 'Consulente', 'Esperto', 'Specializzato',
            'ambito', 'settore', 'campo'
        ]
        
        # Controlla se contiene troppe keyword lavorative
        keyword_count = sum(1 for kw in work_keywords if kw.lower() in name.lower())
        
        if keyword_count >= 2 or len(name) > 50:
            # Prova a estrarre solo le prime 2-3 parole
            words = name.split()[:3]
            if words and len(words[0]) < 20:
                return ' '.join(words)
            return 'Sconosciuto'
        
        return name
    
    def _extract_work_area(self, work: str) -> str:
        """Estrae l'area di competenza principale dal lavoro"""
        if not work:
            return 'consulenza'
        
        work_lower = work.lower()
        
        # Cerca keyword di aree di competenza comuni
        area_keywords = {
            'forensic': 'forensics',
            'forensi': 'forensics',
            'perizia': 'perizie',
            'consulente': 'consulenza',
            'consulenza': 'consulenza',
            'ctp': 'consulenza tecnica',
            'ctu': 'consulenza tecnica',
            'informatic': 'informatica',
            'it': 'IT',
            'legal': 'legale',
            'legale': 'legale',
            'manager': 'gestione',
            'director': 'gestione',
            'engineer': 'ingegneria',
            'ingegner': 'ingegneria',
            'avvocato': 'legale',
            'avvocat': 'legale',
            'expert': 'consulenza',
            'esperto': 'consulenza',
            'specialist': 'specializzazione',
            'specialista': 'specializzazione'
        }
        
        # Cerca keyword nel lavoro
        for keyword, area in area_keywords.items():
            if keyword in work_lower:
                return area
        
        # Se contiene "at" o "in", prendi solo la parte prima (es: "Manager at Accuracy" -> "Manager")
        if ' at ' in work_lower or ' in ' in work_lower:
            parts = re.split(r'\s+(at|in)\s+', work_lower, flags=re.IGNORECASE)
            if parts:
                work_area = parts[0].strip()
                # Rimuovi titoli generici
                work_area = re.sub(r'^(senior|junior|lead|head|chief)\s+', '', work_area)
                # Prendi solo le prime 2-3 parole
                words = work_area.split()[:3]
                if len(words) > 0:
                    return ' '.join(words).title()
        
        # Prendi la prima parte (prima della virgola o punto)
        work_area = work.split(',')[0].split('.')[0].strip()
        
        # Rimuovi titoli generici
        work_area = re.sub(r'^(Senior|Junior|Lead|Head|Chief)\s+', '', work_area, flags=re.IGNORECASE)
        
        # Se contiene "at" o "in", rimuovi quella parte
        work_area = re.sub(r'\s+(at|in)\s+.*$', '', work_area, flags=re.IGNORECASE)
        
        # Se troppo lungo, accorcia a 2-3 parole significative
        words = work_area.split()
        if len(words) > 3:
            # Prendi le parole più significative (non articoli/preposizioni)
            important_words = [w for w in words[:4] if w.lower() not in ['di', 'del', 'della', 'dei', 'delle', 'a', 'al', 'alla', 'ai', 'alle', 'in', 'il', 'la', 'lo', 'gli', 'le']]
            if important_words:
                work_area = ' '.join(important_words[:3])
            else:
                work_area = ' '.join(words[:3])
        
        # Se ancora troppo lungo o non ha senso, usa un termine generico
        if len(work_area) > 30 or len(work_area.split()) > 4:
            return 'consulenza'
        
        return work_area.strip() if work_area.strip() else 'consulenza'
    
    async def _fix_conversation_message_syntax(self, message: str, conversation_history: str = "", target_info: str = "") -> str:
        """
        Corregge la sintassi del messaggio in una CONVERSAZIONE ATTIVA
        Più conservativo: NON aggiunge contenuto, SOLO virgole
        
        Args:
            message: Messaggio da correggere
            conversation_history: Storico conversazione per contesto
            target_info: Informazioni sul target per double-check coerenza (opzionale)
        """
        if not message or len(message.strip()) == 0:
            return message
        
        # Usa il prompt CONVERSAZIONALE (conservativo)
        from src.prompts import AIPrompts
        prompt = AIPrompts.fix_conversation_message_syntax(message, conversation_history, target_info)

        try:
            corrected = await self.generate_response(prompt)
            corrected = corrected.strip()
            
            # Rimuovi eventuali punti finali aggiunti dall'LLM
            if corrected.endswith('.'):
                corrected = corrected[:-1]
            
            # Rimuovi virgolette se presenti
            if (corrected.startswith('"') and corrected.endswith('"')) or \
               (corrected.startswith("'") and corrected.endswith("'")):
                corrected = corrected[1:-1].strip()
            
            return corrected if corrected else message
        except Exception as e:
            print(f"  [WARN] Impossibile correggere sintassi: {e}, uso messaggio originale")
            return message
    
    async def _fix_message_syntax(self, message: str, target_info: str = "") -> str:
        """
        Corregge la sintassi del messaggio usando l'LLM per renderlo più naturale
        Aggiunge virgole, separa le frasi, migliora la leggibilità
        Verifica anche la coerenza del contenuto con le informazioni disponibili
        
        Args:
            message: Messaggio da correggere
            target_info: Informazioni sul target per double-check coerenza (opzionale)
        """
        if not message or len(message.strip()) == 0:
            return message
        
        # Usa il prompt centralizzato da AIPrompts con verifica contenuto
        from src.prompts import AIPrompts
        prompt = AIPrompts.fix_message_syntax(message, target_info)

        try:
            corrected = await self.generate_response(prompt)
            corrected = corrected.strip()
            
            # Rimuovi eventuali punti finali aggiunti dall'LLM
            if corrected.endswith('.'):
                corrected = corrected[:-1]
            
            # Rimuovi virgolette se presenti
            if (corrected.startswith('"') and corrected.endswith('"')) or \
               (corrected.startswith("'") and corrected.endswith("'")):
                corrected = corrected[1:-1].strip()
            
            return corrected if corrected else message
        except Exception as e:
            print(f"  [WARN] Impossibile correggere sintassi: {e}, uso messaggio originale")
            return message
    
    def _clean_message(self, message: str, max_length: int = 1000) -> str:
        """Pulisce e formatta il messaggio generato"""
        original_message = message.strip()
        message = message.strip()
        
        # Rileva e rimuovi duplicazioni (messaggio ripetuto due volte)
        message_len = len(message)
        if message_len > 20:  # Solo per messaggi significativi
            # Normalizza il messaggio per il confronto
            normalized = re.sub(r'\s+', ' ', message.lower().strip())
            
            # Cerca pattern di duplicazione: prova diverse posizioni di divisione
            # (non sempre è esattamente a metà)
            for split_ratio in [0.45, 0.50, 0.55]:  # Prova diverse posizioni
                split_point = int(message_len * split_ratio)
                if split_point < 10 or split_point > message_len - 10:
                    continue
                    
                first_part = message[:split_point].strip()
                second_part = message[split_point:].strip()
                
                # Normalizza per confronto
                first_norm = re.sub(r'\s+', ' ', first_part.lower())
                second_norm = re.sub(r'\s+', ' ', second_part.lower())
                
                if len(first_norm) < 10 or len(second_norm) < 10:
                    continue
                
                # Calcola similarità usando sequenza comune più lunga
                # Se la seconda parte inizia con la prima parte (o viceversa), è una duplicazione
                if first_norm in second_norm or second_norm in first_norm:
                    # Usa la parte più corta (di solito la prima)
                    selected_part = first_part if len(first_part) <= len(second_part) else second_part
                    message = selected_part
                    break
                
                # Altrimenti calcola similarità carattere per carattere
                min_len = min(len(first_norm), len(second_norm))
                if min_len > 10:
                    matches = sum(1 for i in range(min_len) if first_norm[i] == second_norm[i])
                    similarity = matches / max(len(first_norm), len(second_norm)) if max(len(first_norm), len(second_norm)) > 0 else 0
                    
                    # Se la similarità è molto alta (>85%), è una duplicazione
                    if similarity > 0.85:
                        selected_part = first_part if len(first_part) <= len(second_part) else second_part
                        message = selected_part
                        break
        
        # Rimuovi prefissi meta-testuali
        meta_prefixes = [
            "Messaggio:", "WhatsApp:", "Ecco il messaggio:", "Ecco:",
            "Here is", "Message:", "Possible message:", "Risposta:"
        ]
        
        for prefix in meta_prefixes:
            if message.lower().startswith(prefix.lower()):
                message = message[len(prefix):].strip()
                if message.startswith((':','-')):
                    message = message[1:].strip()
        
        # Rimuovi virgolette
        if (message.startswith('"') and message.endswith('"')) or \
           (message.startswith("'") and message.endswith("'")):
            message = message[1:-1].strip()
        
        # Rimuovi pattern meta
        message = re.sub(r'^Here is (a possible |the )?.*?:?\s*', '', message, flags=re.IGNORECASE)
        message = re.sub(r'^\[.*?\]\s*', '', message)
        message = re.sub(r'^\{.*?\}\s*', '', message)
        
        # Normalizza spazi
        message = re.sub(r'\s+', ' ', message).strip()
        
        # Rimuovi riferimenti troppo specifici al lavoro del target
        # Pattern da evitare: "esperto di [lavoro specifico]", "cercavo un esperto di [lavoro]"
        
        # Rimuovi "esperto di [qualsiasi cosa lunga più di 15 caratteri]"
        message = re.sub(r'esperto di [^.!?]{15,}', 'consulente', message, flags=re.IGNORECASE)
        message = re.sub(r'cercavo un esperto di [^.!?]{15,}', 'ho bisogno di un consiglio', message, flags=re.IGNORECASE)
        message = re.sub(r'esperto in [^.!?]{15,}', 'consulente', message, flags=re.IGNORECASE)
        message = re.sub(r'specialista di [^.!?]{15,}', 'consulente', message, flags=re.IGNORECASE)
        
        # Rimuovi frasi che contengono "at [Azienda]" o "in [Azienda]" (troppo specifico)
        # Es: "Manager at Accuracy" -> rimuovi "at Accuracy"
        message = re.sub(r'\s+at\s+[A-Z][a-zA-Z]{3,}\b', '', message, flags=re.IGNORECASE)
        message = re.sub(r'\s+in\s+[A-Z][a-zA-Z]{3,}\b', '', message, flags=re.IGNORECASE)
        
        # Rimuovi titoli lavorativi troppo lunghi (es: "Senior Manager at Accuracy")
        # Se una frase contiene più di 3 parole maiuscole, potrebbe essere un titolo
        words = message.split()
        cleaned_words = []
        skip_next = False
        for i, word in enumerate(words):
            if skip_next:
                skip_next = False
                continue
            # Se la parola inizia con maiuscola e la prossima è "at" o "in", salta entrambe
            if word[0].isupper() and i + 1 < len(words) and words[i+1].lower() in ['at', 'in']:
                if i + 2 < len(words) and words[i+2][0].isupper():
                    skip_next = True
                    continue
            cleaned_words.append(word)
        message = ' '.join(cleaned_words)
        
        # Rimuovi frasi che contengono pattern tipo "cercavo un esperto di [qualcosa]"
        if 'cercavo' in message.lower() and 'esperto' in message.lower():
            # Sostituisci con qualcosa di più generico
            message = re.sub(r'cercavo un esperto di [^.!?]+', 'ho bisogno di un consiglio', message, flags=re.IGNORECASE)
        
        # Normalizza spazi di nuovo dopo le rimozioni
        message = re.sub(r'\s+', ' ', message).strip()
        
        # Limita lunghezza intelligentemente
        if len(message) > max_length:
            truncated = message[:max_length-3]
            
            # Cerca ultimo punto di punteggiatura
            last_punct = max(
                truncated.rfind('.'),
                truncated.rfind('!'),
                truncated.rfind('?')
            )
            
            if last_punct > max_length * 0.6:
                message = truncated[:last_punct+1].strip()
            else:
                # Taglia all'ultima parola completa
                last_space = truncated.rfind(' ')
                if last_space > max_length * 0.7:
                    message = truncated[:last_space].strip() + "..."
                else:
                    message = truncated + "..."
        
        return message
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parsa risposta JSON dal modello - con pulizia markdown e gestione JSON troncati"""
        if not response or not response.strip():
            return {}
        
        try:
            # Rimuovi markdown code blocks (```json ... ```)
            cleaned = response.strip()
            if '```' in cleaned:
                # Rimuovi tutti i backtick
                cleaned = cleaned.replace('```json', '').replace('```', '').strip()
            
            # Rimuovi eventuali prefissi/suffissi testuali
            # Cerca il primo { e l'ultimo }
            first_brace = cleaned.find('{')
            last_brace = cleaned.rfind('}')
            
            if first_brace != -1:
                if last_brace != -1 and last_brace > first_brace:
                    # Estrai solo la parte JSON
                    cleaned = cleaned[first_brace:last_brace + 1]
                else:
                    # JSON troncato - prova a chiudere le parentesi mancanti
                    cleaned = cleaned[first_brace:]
                    # Conta parentesi graffe aperte/chiuse
                    open_braces = cleaned.count('{')
                    close_braces = cleaned.count('}')
                    missing_braces = open_braces - close_braces
                    if missing_braces > 0:
                        # Chiudi le parentesi mancanti
                        cleaned += '}' * missing_braces
                        # Chiudi anche eventuali array aperti
                        open_brackets = cleaned.count('[')
                        close_brackets = cleaned.count(']')
                        missing_brackets = open_brackets - close_brackets
                        if missing_brackets > 0:
                            cleaned += ']' * missing_brackets
                        # Chiudi eventuali stringhe non chiuse
                        if cleaned.count('"') % 2 != 0:
                            # Stringa non chiusa - trova l'ultima virgoletta e chiudi
                            last_quote = cleaned.rfind('"')
                            if last_quote != -1:
                                # Inserisci virgoletta di chiusura prima dell'ultima parentesi
                                cleaned = cleaned[:last_quote + 1] + '"' + cleaned[last_quote + 1:]
            
            # Prova a parsare direttamente (caso più comune)
            try:
                parsed = json.loads(cleaned)
                print(f"  JSON parsato direttamente: {len(parsed)} campi")
                return parsed
            except json.JSONDecodeError as e:
                # Se il JSON è ancora malformato, prova a sistemarlo
                pass
            
            # Fallback 1: Cerca JSON con regex più robusta (gestisce anche JSON annidati)
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned, re.DOTALL)
            if not json_match:
                # Fallback 2: Regex più semplice - trova tutto tra { e }
                json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            
            if json_match:
                json_str = json_match.group()
                try:
                    parsed = json.loads(json_str)
                    print(f"  JSON parsato con regex: {len(parsed)} campi")
                    return parsed
                except json.JSONDecodeError:
                    # Prova a sistemare il JSON trovato
                    # Rimuovi virgole finali prima di } o ]
                    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
                    try:
                        parsed = json.loads(json_str)
                        print(f"  JSON parsato dopo pulizia: {len(parsed)} campi")
                        return parsed
                    except json.JSONDecodeError:
                        pass
            
            # Fallback 3: Prova a estrarre campi individuali con regex
            # Questo è un ultimo tentativo per JSON molto malformati
            result = {}
            name_match = re.search(r'"name"\s*:\s*"([^"]+)"', cleaned)
            if name_match:
                result['name'] = name_match.group(1)
            
            work_match = re.search(r'"work"\s*:\s*"([^"]+)"', cleaned)
            if work_match:
                result['work'] = work_match.group(1)
            
            location_match = re.search(r'"location"\s*:\s*"([^"]+)"', cleaned)
            if location_match:
                result['location'] = location_match.group(1)
            
            # Estrai skills (array)
            skills_match = re.search(r'"skills"\s*:\s*\[(.*?)\]', cleaned, re.DOTALL)
            if skills_match:
                skills_str = skills_match.group(1)
                skills = [s.strip().strip('"') for s in re.findall(r'"([^"]+)"', skills_str)]
                result['skills'] = skills
            
            # Estrai interests (array)
            interests_match = re.search(r'"interests"\s*:\s*\[(.*?)\]', cleaned, re.DOTALL)
            if interests_match:
                interests_str = interests_match.group(1)
                interests = [s.strip().strip('"') for s in re.findall(r'"([^"]+)"', interests_str)]
                result['interests'] = interests
            
            if result:
                print(f"  JSON parsato con estrazione regex: {len(result)} campi")
                return result
            
            print(f"  AVVISO: Nessun JSON trovato nella risposta (len={len(cleaned)})")
            print(f"  Risposta (primi 500 char): {cleaned[:500]}")
            return {}
            
        except Exception as e:
            print(f"  AVVISO: Errore parsing JSON: {str(e)[:50]}")
            print(f"  Risposta (primi 300 char): {response[:300]}")
            return {}
    
    def _validate_and_clean_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Valida e pulisce il profilo estratto"""
        # Proteggi contro valori None
        cleaned = {
            'name': self._extract_clean_name(profile.get('name', 'Sconosciuto') or 'Sconosciuto'),
            'work': profile.get('work', '') or '',
            'location': profile.get('location', '') or '',
            'skills': (profile.get('skills') or [])[:5],  # Max 5 skills
            'interests': (profile.get('interests') or [])[:5],
            'summary': (profile.get('summary') or '')[:300],  # Max 300 char
            'explanation': (profile.get('explanation') or '')[:500],  # Max 500 char per spiegazione dettagliata
            'social_profiles': profile.get('social_profiles') or [],
            'recent_activities': (profile.get('recent_activities') or [])[:3],
            'key_achievements': (profile.get('key_achievements') or [])[:5],  # Max 5 achievements
            'education': (profile.get('education') or '')[:200]  # Max 200 char
        }
        
        return cleaned
    
    def _empty_profile(self) -> Dict[str, Any]:
        """Restituisce un profilo vuoto"""
        return {
            'name': 'Sconosciuto',
            'work': '',
            'location': '',
            'skills': [],
            'interests': [],
            'summary': '',
            'explanation': '',
            'social_profiles': [],
            'recent_activities': [],
            'key_achievements': [],
            'education': ''
        }

    # ============================================================================
    # FUNZIONI UTILITY E AMMINISTRAZIONE
    # ============================================================================
    
    async def _check_connection(self) -> bool:
        """Verifica rapidamente se Ollama è raggiungibile"""
        try:
            # Prova una richiesta semplice e veloce (eseguita in thread separato per non bloccare)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self.client.list)
            # Verifica che il risultato sia valido
            if result is not None:
                return True
            return False
        except Exception as e:
            error_str = str(e).lower()
            # Log dell'errore per debug
            if 'failed to connect' in error_str or 'connection' in error_str or 'refused' in error_str or 'timeout' in error_str:
                print(f"  AVVISO: Errore connessione: {e}")
                return False
            # Se è un altro tipo di errore, considera la connessione OK (potrebbe essere un problema di modello)
            print(f"  AVVISO: Errore non critico: {e}")
            return True
    
    async def test_connection(self) -> bool:
        """Testa la connessione con Ollama"""
        return await self._check_connection()
    
    def get_model_info(self) -> Dict[str, Any]:
        """Restituisce informazioni sui modelli"""
        return {
            'available_models': self.available_models,
            'current_model': self.config_manager.get('ollama_model', 'llama3:8b'),
            'optimized_params': self.optimized_params,
            'hardware_info': self.hardware_optimizer.system_info
        }
    
    def update_model(self, new_model: str) -> bool:
        """Aggiorna il modello corrente"""
        try:
            normalized = self._normalize_model_name(new_model)
            self.config_manager.set('ollama_model', normalized)
            self.optimized_params = self.hardware_optimizer.get_optimized_model_params(normalized)
            print(f"  Modello aggiornato: {normalized}")
            return True
        except Exception as e:
            print(f"ERRORE: Errore aggiornamento modello: {e}")
            return False
    
    def force_cpu_mode(self):
        """Forza la modalità CPU-only per tutti i futuri generate"""
        print("  Forzatura modalità CPU-only...")
        
        # Aggiorna parametri ottimizzati
        if 'options' in self.optimized_params:
            self.optimized_params['options']['num_gpu'] = 0
            self.optimized_params['options']['num_ctx'] = min(
                self.optimized_params['options'].get('num_ctx', 2048), 
                1024
            )
        
        # Aggiorna configurazione permanente
        if self.config_manager:
            self.config_manager.set('gpu_enabled', False)
        
        print("[OK] Modalità CPU-only attivata")
    
    def clear_gpu_memory(self):
        """Tenta di liberare memoria GPU (se possibile)"""
        try:
            if TORCH_AVAILABLE and torch.cuda.is_available():
                torch.cuda.empty_cache()
                print("Cache GPU pulita")
        except Exception as e:
            print(f"AVVISO: Impossibile pulire cache GPU: {e}")
    
    def close(self):
        """Chiude la connessione"""
        self.clear_gpu_memory()
        print("Ollama client chiuso")
"""
Ottimizzatore hardware per Ollama
Analizza il sistema e ottimizza i parametri per le performance
"""

import psutil
import os
from typing import Dict, Any, Optional, List
from pathlib import Path

try:
    import GPUtil
    GPUTIL_AVAILABLE = True
except ImportError:
    GPUTIL_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

class HardwareOptimizer:
    """Ottimizzatore hardware per performance Ollama"""
    
    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        self.system_info = self._get_system_info()
        
    def _get_system_info(self) -> Dict[str, Any]:
        """Ottiene informazioni dettagliate sull'hardware del sistema"""
        info = {
            'cpu_count': psutil.cpu_count(),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_total': psutil.virtual_memory().total,
            'memory_available': psutil.virtual_memory().available,
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage': self._get_disk_usage(),
            'platform': os.name,
            'python_version': f"{psutil.sys.version_info.major}.{psutil.sys.version_info.minor}"
        }
        
        # Informazioni GPU
        info.update(self._get_gpu_info())
        
        return info
    
    def _get_disk_usage(self) -> float:
        """Ottiene l'utilizzo del disco"""
        try:
            if os.name == 'nt':  # Windows
                disk_usage = psutil.disk_usage('C:\\')
            else:  # Unix-like
                disk_usage = psutil.disk_usage('/')
            return disk_usage.percent
        except Exception:
            return 0.0
            
    def _get_gpu_info(self) -> Dict[str, Any]:
        """Ottiene informazioni GPU con diagnostica migliorata"""
        gpu_info = {
            'gpu_count': 0,
            'gpus': [],
            'gpu_available': False,
            'cuda_available': False,
            'rocm_available': False
        }
        
        # Controlla CUDA (NVIDIA)
        if TORCH_AVAILABLE:
            try:
                gpu_info['cuda_available'] = torch.cuda.is_available()
                if gpu_info['cuda_available']:
                    gpu_info['gpu_count'] = torch.cuda.device_count()
                    gpu_info['gpu_available'] = True
            except Exception as e:
                print(f"  [INFO] CUDA non disponibile: {e}")
                pass
        
        # Prova GPUtil per dettagli GPU
        if GPUTIL_AVAILABLE:
            try:
                gpus = GPUtil.getGPUs()
                if len(gpus) > 0:
                    gpu_info['gpu_count'] = len(gpus)
                    gpu_info['gpu_available'] = True
                    
                    for gpu in gpus:
                        gpu_info['gpus'].append({
                            'id': gpu.id,
                            'name': gpu.name,
                            'memory_total': gpu.memoryTotal,
                            'memory_used': gpu.memoryUsed,
                            'memory_free': gpu.memoryFree,
                            'temperature': gpu.temperature,
                            'load': gpu.load * 100,
                            'uuid': gpu.uuid
                        })
            except Exception as e:
                # GPUtil può fallire anche se la GPU c'è
                if gpu_info['cuda_available']:
                    # Se CUDA funziona ma GPUtil no, usa info di base da torch
                    print(f"  [INFO] GPUtil non disponibile, uso PyTorch per GPU info")
                    for i in range(gpu_info['gpu_count']):
                        try:
                            props = torch.cuda.get_device_properties(i)
                            # Ottieni memoria disponibile in real-time
                            mem_free, mem_total = torch.cuda.mem_get_info(i)
                            gpu_info['gpus'].append({
                                'id': i,
                                'name': torch.cuda.get_device_name(i),
                                'memory_total': mem_total / (1024**2),  # MB
                                'memory_used': (mem_total - mem_free) / (1024**2),  # MB
                                'memory_free': mem_free / (1024**2),  # MB
                                'temperature': 0,
                                'load': 0,
                                'uuid': ''
                            })
                        except Exception as torch_error:
                            print(f"  [WARN] Errore lettura GPU {i}: {torch_error}")
                            # Aggiungi GPU con info minimali se fallisce
                            gpu_info['gpus'].append({
                                'id': i,
                                'name': 'Unknown GPU',
                                'memory_total': 0,
                                'memory_used': 0,
                                'memory_free': 0,
                                'temperature': 0,
                                'load': 0,
                                'uuid': ''
                            })
                else:
                    print(f"  [WARN] Nessuna GPU rilevata (GPUtil error: {e})")
            
        return gpu_info
    
    def optimize_for_ollama(self, model_name: str = None) -> Dict[str, Any]:
        """Ottimizza le impostazioni per Ollama basandosi sull'hardware disponibile"""
        if model_name is None:
            model_name = self.config_manager.get('ollama_model', 'llama3:8b') if self.config_manager else 'llama3:8b'
            
        optimizations = {}
        
        # Ottimizzazione CPU - privilegia velocità con contesto ridotto
        cpu_count = self.system_info['cpu_count']
        if cpu_count >= 8:
            optimizations['num_ctx'] = 1024  # Ridotto per evitare saturazione
            optimizations['num_thread'] = min(4, cpu_count)  # Max 4 thread per non saturare
        elif cpu_count >= 4:
            optimizations['num_ctx'] = 512  # Ridotto per velocità
            optimizations['num_thread'] = min(2, cpu_count)  # Max 2 thread
        else:
            optimizations['num_ctx'] = 256  # Minimo per velocità
            optimizations['num_thread'] = 1  # Solo 1 thread
        
        # Parametri ottimizzati per velocità
        optimizations['num_predict'] = 100  # Limita lunghezza risposta (ridotto da 150)
        optimizations['temperature'] = 0.3  # Bassa temperatura per risposte più deterministiche e coerenti
            
        # Override con configurazione se presente
        if self.config_manager:
            cpu_threads = self.config_manager.get('cpu_threads')
            if cpu_threads:
                optimizations['num_thread'] = int(cpu_threads)
                
        # Ottimizzazione memoria
        available_memory_gb = self.system_info['memory_available'] / (1024**3)
        max_memory_usage = self.config_manager.get('max_memory_usage', 80) if self.config_manager else 80
        
        # Assicurati che max_memory_usage non sia None
        if max_memory_usage is None:
            max_memory_usage = 80
        
        # Calcola memoria disponibile considerando il limite
        usable_memory_gb = available_memory_gb * (max_memory_usage / 100)
        
        if usable_memory_gb >= 16:
            optimizations['num_gpu'] = -1  # Usa tutta la GPU disponibile
        elif usable_memory_gb >= 8:
            optimizations['num_gpu'] = 0   # Usa solo CPU per sicurezza
        elif usable_memory_gb >= 4:
            # RAM limitata (4-8GB) - riduci ulteriormente
            optimizations['num_ctx'] = min(optimizations['num_ctx'], 512)
            optimizations['num_predict'] = 100  # Risposte più corte
            optimizations['num_gpu'] = 0
            print(f"  [WARN] RAM limitata ({usable_memory_gb:.1f}GB) - ottimizzazioni conservative applicate")
        else:
            # RAM molto bassa (< 4GB) - modalità ultra-conservativa
            optimizations['num_ctx'] = 256  # Contesto minimo
            optimizations['num_predict'] = 75  # Risposte brevi
            optimizations['num_thread'] = max(1, optimizations['num_thread'] // 2)  # Meno thread
            optimizations['num_gpu'] = 0
            print(f"  [WARN] RAM molto bassa ({usable_memory_gb:.1f}GB disponibili)")
            print(f"  [INFO] CONSIGLIO: Chiudi applicazioni pesanti o usa modelli tiny (llama3.2:1b, tinyllama)")
            
        # Ottimizzazione GPU
        # NOTA: Ollama usa automaticamente la GPU se disponibile
        # num_gpu = layers da caricare sulla GPU (-1 = tutte, 0 = nessuna)
        if self.system_info['gpu_available'] and self.config_manager.get('gpu_enabled', True) if self.config_manager else True:
            # Verifica che ci sia almeno una GPU con info valide
            if len(self.system_info['gpus']) > 0:
                gpu = self.system_info['gpus'][0]
                vram_total_mb = gpu.get('memory_total', 0)
                vram_free_mb = gpu.get('memory_free', 0)
                vram_used_mb = gpu.get('memory_used', 0)
                
                # Se non abbiamo info sulla memoria, assume conservativamente
                if vram_total_mb == 0:
                    print(f"  ⚠️  GPU rilevata ma memoria non disponibile - usando solo CPU per sicurezza")
                    optimizations['num_gpu'] = 0
                else:
                    vram_gb = vram_total_mb / 1024
                    vram_free_gb = vram_free_mb / 1024 if vram_free_mb > 0 else vram_gb
                    
                    print(f"  GPU rilevata: {gpu.get('name', 'Unknown')} ({vram_gb:.1f}GB VRAM, {vram_free_gb:.1f}GB liberi)")
                    
                    # Per modelli grandi (120B), usa sempre GPU se disponibile (anche con offloading parziale)
                    is_large_model = model_name and ('120b' in str(model_name).lower() or '70b' in str(model_name).lower())
                    
                    # Usa memoria libera per decisioni, non totale
                    # Riduci soglie per essere più conservativi e evitare OOM
                    if vram_free_gb >= 4.0:  # 4GB+ liberi - usa GPU completamente
                        optimizations['num_gpu'] = -1  # Tutte le layers sulla GPU
                        print(f"  Memoria GPU sufficiente: tutte le layers sulla GPU")
                    elif vram_free_gb >= 2.5:  # 2.5-4GB liberi - usa parzialmente
                        optimizations['num_gpu'] = 15  # Alcune layers
                        print(f"  Memoria GPU media: 15 layers sulla GPU")
                    elif vram_free_gb >= 1.5:  # 1.5-2.5GB liberi - usa molto poco
                        if is_large_model:
                            # Per modelli grandi, usa comunque la GPU (offloading parziale)
                            optimizations['num_gpu'] = -1  # Prova tutte le layers, Ollama gestirà l'offloading
                            print(f"  Memoria GPU limitata ma modello grande: tutte le layers sulla GPU (offloading automatico)")
                        else:
                            optimizations['num_gpu'] = 8  # Poche layers sulla GPU, resto su RAM
                            print(f"  Memoria GPU limitata: 8 layers sulla GPU + RAM")
                            print(f"  Prestazioni moderate - considera modelli più piccoli (llama3.2:1b)")
                    elif vram_free_gb >= 1.0:  # 1-1.5GB liberi - minimo supporto
                        if is_large_model:
                            # Per modelli grandi, prova comunque la GPU
                            optimizations['num_gpu'] = -1
                            print(f"  Memoria GPU molto limitata ma modello grande: tutte le layers sulla GPU (offloading automatico)")
                        else:
                            optimizations['num_gpu'] = 3  # Pochissime layers
                            print(f"  Memoria GPU molto limitata: solo 3 layers sulla GPU")
                            print(f"  Consigliato usare solo CPU o modelli tiny")
                    else:
                        if is_large_model and vram_gb >= 30:  # GPU con almeno 30GB totali
                            # Per modelli grandi con GPU potente, prova comunque
                            optimizations['num_gpu'] = -1
                            print(f"  VRAM occupata ma GPU potente ({vram_gb:.1f}GB): tutte le layers sulla GPU (offloading automatico)")
                        else:
                            optimizations['num_gpu'] = 0
                            print(f"  VRAM insufficiente ({vram_free_gb:.1f}GB liberi), uso solo CPU")
            else:
                optimizations['num_gpu'] = 0
                print(f"  GPU rilevata ma senza info memoria - usando solo CPU per sicurezza")
        else:
            optimizations['num_gpu'] = 0
            if not self.system_info['gpu_available']:
                print(f"  Nessuna GPU rilevata - usando CPU")
            else:
                print(f"  GPU disabilitata nella configurazione")
                
        return optimizations
    
    def check_system_health(self) -> Dict[str, Any]:
        """Controlla la salute del sistema e restituisce dettagli"""
        health_status = {
            'healthy': True,
            'warnings': [],
            'errors': [],
            'recommendations': []
        }
        
        # Controllo memoria
        memory_percent = self.system_info['memory_percent']
        if memory_percent > 95:
            health_status['healthy'] = False
            health_status['errors'].append(f"Memoria critica: {memory_percent:.1f}%")
        elif memory_percent > 85:
            health_status['warnings'].append(f"Memoria alta: {memory_percent:.1f}%")
            
        # Controllo CPU
        cpu_percent = self.system_info['cpu_percent']
        if cpu_percent > 95:
            health_status['warnings'].append(f"CPU sovraccarica: {cpu_percent:.1f}%")
            
        # Controllo disco
        disk_usage = self.system_info['disk_usage']
        if disk_usage > 95:
            health_status['healthy'] = False
            health_status['errors'].append(f"Disco pieno: {disk_usage:.1f}%")
        elif disk_usage > 85:
            health_status['warnings'].append(f"Disco quasi pieno: {disk_usage:.1f}%")
            
        # Controllo GPU
        if self.system_info['gpu_available']:
            for gpu in self.system_info['gpus']:
                if gpu['temperature'] > 85:
                    health_status['warnings'].append(f"GPU {gpu['name']} troppo calda: {gpu['temperature']}°C")
                if gpu['memory_used'] / gpu['memory_total'] > 0.95:
                    health_status['warnings'].append(f"VRAM GPU {gpu['name']} quasi esaurita")
                    
        # Raccomandazioni
        if memory_percent > 70:
            health_status['recommendations'].append("Considera di chiudere altre applicazioni")
        if not self.system_info['gpu_available']:
            health_status['recommendations'].append("Nessuna GPU rilevata - le performance potrebbero essere limitate")
            
        return health_status
    
    def print_system_info(self, detailed: bool = False):
        """Stampa le informazioni del sistema"""
        print("INFORMAZIONI HARDWARE")
        print("=" * 40)
        
        # Info di base
        print(f"CPU: {self.system_info['cpu_count']} core, {self.system_info['cpu_percent']:.1f}% utilizzo")
        print(f"RAM: {self.system_info['memory_total'] / (1024**3):.1f}GB totali, {self.system_info['memory_percent']:.1f}% utilizzata")
        print(f"Disco: {self.system_info['disk_usage']:.1f}% utilizzato")
        print(f"Piattaforma: {self.system_info['platform']}")
        
        # Info GPU
        if self.system_info['gpu_available']:
            print(f"GPU: {self.system_info['gpu_count']} dispositivi trovati")
            for i, gpu in enumerate(self.system_info['gpus']):
                print(f"  GPU {i}: {gpu['name']}")
                if detailed:
                    print(f"    VRAM: {gpu['memory_total']}MB totali, {gpu['memory_used']}MB usati")
                    print(f"    Temperatura: {gpu['temperature']}°C, Load: {gpu['load']:.1f}%")
        else:
            print("GPU: Nessuna GPU trovata")
            
        # Info dettagliate se richieste
        if detailed:
            print(f"Python: {self.system_info['python_version']}")
            print(f"Memoria disponibile: {self.system_info['memory_available'] / (1024**3):.1f}GB")
            
    def get_optimized_model_params(self, model_name: str = None) -> Dict[str, Any]:
        """Restituisce i parametri ottimizzati per il modello"""
        optimizations = self.optimize_for_ollama(model_name)
        
        base_params = {
            'model': model_name or (self.config_manager.get('ollama_model', 'llama3.2:1b') if self.config_manager else 'llama3.2:1b'),
            'options': {
                'num_ctx': optimizations.get('num_ctx', 2048),
                'num_thread': optimizations.get('num_thread', 4),
                'num_gpu': optimizations.get('num_gpu', 0),
                'num_predict': optimizations.get('num_predict', 100),
                'temperature': 0.3,  # Bassa temperatura per coerenza
                'top_p': 0.9,
                'repeat_penalty': 1.1,
                'top_k': 40
            }
        }
        
        # Aggiungi parametri specifici per modello se necessario
        if model_name and 'llama' in model_name.lower():
            base_params['options']['num_ctx'] = min(base_params['options']['num_ctx'], 4096)
        elif model_name and 'codellama' in model_name.lower():
            base_params['options']['temperature'] = 0.2  # Più deterministico per codice
            
        return base_params
        
    def get_performance_recommendations(self) -> List[str]:
        """Ottiene raccomandazioni per migliorare le performance"""
        recommendations = []
        
        # Raccomandazioni basate sull'hardware
        if self.system_info['cpu_count'] < 4:
            recommendations.append("Considera un processore con almeno 4 core per migliori performance")
            
        if self.system_info['memory_total'] / (1024**3) < 8:
            recommendations.append("8GB+ di RAM raccomandati per modelli grandi")
            
        if not self.system_info['gpu_available']:
            recommendations.append("Una GPU dedicata accelererà significativamente le inferenze")
            
        # Raccomandazioni basate sull'utilizzo
        if self.system_info['memory_percent'] > 70:
            recommendations.append("Chiudi altre applicazioni per liberare memoria")
            
        if self.system_info['disk_usage'] > 80:
            recommendations.append("Libera spazio su disco per evitare rallentamenti")
            
        return recommendations
        
    def benchmark_system(self) -> Dict[str, Any]:
        """Esegue un benchmark veloce del sistema"""
        import time
        
        benchmark_results = {
            'cpu_score': 0,
            'memory_score': 0,
            'gpu_score': 0,
            'overall_score': 0
        }
        
        # Benchmark CPU (calcolo semplice)
        start_time = time.time()
        sum_result = sum(i * i for i in range(100000))
        cpu_time = time.time() - start_time
        benchmark_results['cpu_score'] = max(0, 100 - cpu_time * 1000)  # Score inverso al tempo
        
        # Score memoria (basato su quantità e velocità)
        memory_gb = self.system_info['memory_total'] / (1024**3)
        benchmark_results['memory_score'] = min(100, memory_gb * 10)  # 10 punti per GB
        
        # Score GPU (basato su presenza e VRAM)
        if self.system_info['gpu_available']:
            gpu = self.system_info['gpus'][0]
            benchmark_results['gpu_score'] = min(100, gpu['memory_total'] / 100)  # 1 punto per 100MB VRAM
        else:
            benchmark_results['gpu_score'] = 0
            
        # Score complessivo
        benchmark_results['overall_score'] = (
            benchmark_results['cpu_score'] * 0.4 +
            benchmark_results['memory_score'] * 0.4 +
            benchmark_results['gpu_score'] * 0.2
        )
        
        return benchmark_results

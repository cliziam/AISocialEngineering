#!/usr/bin/env python3
"""
Script di diagnostica GPU per Social Engineering Tool
Esegue controlli completi dell'hardware e fornisce raccomandazioni

Nota: esegui questo script dalla root del progetto:
    python scripts/diagnose_gpu.py
"""

import sys
from pathlib import Path

# Import con prefisso src.
from src.core.config_manager import ConfigManager
from src.core.hardware_optimizer import HardwareOptimizer


def print_separator(char="=", length=60):
    print(char * length)


def main():
    print("\n" + "=" * 60)
    print(" DIAGNOSTICA HARDWARE - Social Engineering Tool")
    print("=" * 60 + "\n")

    # Inizializza
    config = ConfigManager()
    optimizer = HardwareOptimizer(config)

    # 1. Informazioni sistema di base
    print(" INFORMAZIONI SISTEMA")
    print_separator("-")
    optimizer.print_system_info(detailed=True)
    print()

    # 2. Stato GPU dettagliato
    print("\n DETTAGLI GPU")
    print_separator("-")
    sys_info = optimizer.system_info

    if sys_info['gpu_available']:
        print(f" GPU Rilevata: {sys_info['gpu_count']} dispositivo(i)")
        print(f" CUDA Disponibile: {'Sì' if sys_info['cuda_available'] else 'No'}")

        for i, gpu in enumerate(sys_info['gpus']):
            print(f"\n GPU {i}:")
            print(f" Nome: {gpu.get('name', 'Unknown')}")
            print(
                f" VRAM Totale: {gpu.get('memory_total', 0):.0f} MB "
                f"({gpu.get('memory_total', 0) / 1024:.2f} GB)")
            print(
                f" VRAM Usata: {gpu.get('memory_used', 0):.0f} MB "
                f"({gpu.get('memory_used', 0) / 1024:.2f} GB)")
            print(
                f" VRAM Libera: {gpu.get('memory_free', 0):.0f} MB "
                f"({gpu.get('memory_free', 0) / 1024:.2f} GB)")

            if gpu.get('temperature', 0) > 0:
                temp = gpu['temperature']
                temp_status = "" if temp > 85 else "" if temp > 75 else ""
                print(f" Temperatura: {temp_status} {temp}°C")

            if gpu.get('load', 0) > 0:
                load = gpu['load']
                load_status = "" if load > 90 else "" if load > 70 else ""
                print(f" Carico: {load_status} {load:.1f}%")
    else:
        print(" Nessuna GPU rilevata")
        if not sys_info['cuda_available']:
            print(" CUDA non disponibile - driver GPU mancanti o non installati")
    print()

    # 3. Salute sistema
    print("\n SALUTE SISTEMA")
    print_separator("-")
    health = optimizer.check_system_health()

    if health['healthy']:
        print(" Sistema: SANO")
    else:
        print(" Sistema: PROBLEMI RILEVATI")

    if health['errors']:
        print("\n Errori Critici:")
        for error in health['errors']:
            print(f" {error}")

    if health['warnings']:
        print("\n Avvertimenti:")
        for warning in health['warnings']:
            print(f" {warning}")

    if health['recommendations']:
        print("\n Raccomandazioni:")
        for rec in health['recommendations']:
            print(f" {rec}")
    print()

    # 4. Parametri ottimizzati per Ollama
    print("\n PARAMETRI OTTIMIZZATI OLLAMA")
    print_separator("-")
    model_name = config.get('ollama_model', 'llama3:8b')
    optimizations = optimizer.optimize_for_ollama(model_name)

    print(f"Modello: {model_name}")
    print(f"\nParametri suggeriti:")
    for key, value in optimizations.items():
        if key == 'num_gpu':
            status = " GPU" if value != 0 else " CPU-only"
            if value == -1:
                print(f" {key}: {value} (tutte le layers sulla GPU) {status}")
            elif value > 0:
                print(f" {key}: {value} (layers sulla GPU) {status}")
            else:
                print(f" {key}: {value} {status}")
        else:
            print(f" {key}: {value}")
    print()

    # 5. Benchmark veloce
    print("\n BENCHMARK SISTEMA")
    print_separator("-")
    print("Esecuzione benchmark veloce...")
    benchmark = optimizer.benchmark_system()

    print(f"\nRisultati:")
    print(f" CPU Score: {benchmark['cpu_score']:.1f}/100")
    print(f" Memoria Score: {benchmark['memory_score']:.1f}/100")
    print(f" GPU Score: {benchmark['gpu_score']:.1f}/100")
    print(f" Score Complessivo: {benchmark['overall_score']:.1f}/100")

    # Interpretazione
    overall = benchmark['overall_score']
    if overall >= 70:
        print(f"\n Sistema OTTIMO per modelli AI")
    elif overall >= 50:
        print(f"\n Sistema ADEGUATO per modelli AI piccoli/medi")
    else:
        print(f"\n Sistema LIMITATO - considera solo modelli piccoli")
    print()

    # 6. Raccomandazioni specifiche
    print("\n RACCOMANDAZIONI")
    print_separator("-")
    recommendations = optimizer.get_performance_recommendations()

    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec}")
    else:
        print(" Nessuna raccomandazione - sistema ben configurato!")

    # 7. Raccomandazioni modelli
    print("\n\n MODELLI OLLAMA CONSIGLIATI")
    print_separator("-")

    vram_available = 0
    if sys_info['gpu_available'] and len(sys_info['gpus']) > 0:
        vram_available = sys_info['gpus'][0].get('memory_free', 0) / 1024

    ram_available = sys_info['memory_available'] / (1024**3)

    print(f"Memoria disponibile: {ram_available:.1f}GB RAM", end="")
    if vram_available > 0:
        print(f", {vram_available:.1f}GB VRAM")
    else:
        print()

    print("\nModelli suggeriti:")

    if vram_available >= 6 or (vram_available == 0 and ram_available >= 16):
        print(" llama3:8b - Modello principale (qualità alta)")
        print(" llama3.1:8b - Modello aggiornato")
        print(" codellama:7b - Per generazione codice")

    if vram_available >= 3 or (vram_available == 0 and ram_available >= 8):
        print(" llama3.2:3b - Buon compromesso qualità/velocità")
        print(" phi3:medium - Ottimo per risorse limitate")

    if vram_available < 6 or ram_available < 8:
        print(" llama3.2:1b - CONSIGLIATO per il tuo sistema")
        print(" phi3:mini - Veloce e efficiente")
        print(" tinyllama - Minimo ingombro")

    # 8. Test connessione Ollama
    print("\n\n TEST CONNESSIONE OLLAMA")
    print_separator("-")
    try:
        import ollama
        client = ollama.Client(
            host=config.get('ollama_host', 'http://localhost:11434'))
        models = client.list()
        print(" Connessione Ollama: OK")
        print(f"\nModelli installati: {len(models.get('models', []))}")
        for model in models.get('models', []):
            print(f" - {model.get('name', 'unknown')}")
    except Exception as e:
        print(f" Connessione Ollama: FALLITA")
        print(f" Errore: {e}")
        print("\n Soluzione:")
        print(" 1. Avvia Ollama: ollama serve")
        print(" 2. Verifica che sia in esecuzione: tasklist | findstr ollama")

    # 9. Configurazione attuale
    print("\n\n CONFIGURAZIONE ATTUALE")
    print_separator("-")
    print(f"GPU Abilitata: {config.get('gpu_enabled', True)}")
    print(f"Modello: {config.get('ollama_model', 'llama3:8b')}")
    print(f"Max Memory Usage: {config.get('max_memory_usage', 80)}%")
    print(f"CPU Threads: {config.get('cpu_threads', 'Auto')}")
    print(f"Timeout: {config.get('ollama_timeout', 30)}s")

    # 10. Comandi utili
    print("\n\n COMANDI UTILI")
    print_separator("-")
    print("Verifica Ollama:")
    print(" ollama list # Lista modelli installati")
    print(" ollama pull llama3.2:1b # Scarica modello piccolo")
    print(" ollama serve # Avvia server Ollama")
    print("\nGestione GPU:")
    print(" nvidia-smi # Info GPU NVIDIA")
    print(" tasklist | findstr ollama # Controlla processo Ollama")
    print("\nRiavvio Ollama:")
    print(" taskkill /F /IM ollama.exe # Ferma Ollama")
    print(" ollama serve # Riavvia Ollama")

    print("\n" + "=" * 60)
    print(" Diagnostica completata!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n Diagnostica interrotta dall'utente")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n Errore durante la diagnostica: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script di avvio per Social Engineering Research Tool
Esegui questo file dalla directory root del progetto
"""

import asyncio
import sys
import os
import io
import builtins
from io import UnsupportedOperation

# ============================================================================
# CONFIGURAZIONE VARIABILI D'AMBIENTE 
# ============================================================================
# Carica da file .env se esiste
try:
    from dotenv import load_dotenv  # pyright: ignore[reportMissingImports]
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        # Non sovrascrive variabili già impostate
        load_dotenv(env_file, override=False)
    else:
        # Prova anche config/default.env
        default_env = os.path.join(
            os.path.dirname(__file__),
            'config',
            'default.env')
        if os.path.exists(default_env):
            load_dotenv(default_env, override=False)
except ImportError:
    # python-dotenv non installato, continua senza
    pass

# FIX CRITICO: Forza OLLAMA_HOST corretto se è impostato a 0.0.0.0
# 0.0.0.0 è un indirizzo di binding per server, NON per client!
ollama_host = os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434')

if '0.0.0.0' in ollama_host:
    ollama_host = ollama_host.replace('0.0.0.0', '127.0.0.1')
    os.environ['OLLAMA_HOST'] = ollama_host

# Assicurati che abbia lo schema http://
if not ollama_host.startswith('http'):
    ollama_host = f'http://{ollama_host}'

# Assicurati che abbia la porta :11434
if ':11434' not in ollama_host and not ollama_host.endswith(':11434'):
    # Rimuovi eventuali porte esistenti e aggiungi :11434
    if '://' in ollama_host:
        base = ollama_host.split('://')[1].split(':')[0]
        schema = ollama_host.split('://')[0]
        ollama_host = f'{schema}://{base}:11434'
    else:
        ollama_host = f'{ollama_host}:11434'

os.environ['OLLAMA_HOST'] = ollama_host

# ============================================================================

# Importa il main dalla CLI
from src.cli.main_cli import main

# Fix encoding per Windows console 
if sys.platform == 'win32':
    try:
        # Configura stdout solo se necessario
        needs_stdout_fix = True
        if isinstance(sys.stdout, io.TextIOWrapper):
            encoding = getattr(
                sys.stdout,
                'encoding',
                '').lower().replace(
                '-',
                '')
            if encoding in ('utf8', 'utf'):
                needs_stdout_fix = False

        if needs_stdout_fix and hasattr(sys.stdout, 'buffer'):
            try:
                # Ottieni il buffer sottostante
                if isinstance(sys.stdout, io.TextIOWrapper):
                    # Se è già un TextIOWrapper, usa detach() per ottenere il buffer
                    # senza chiudere il wrapper (se supportato)
                    try:
                        buffer = sys.stdout.detach()
                    except (AttributeError, UnsupportedOperation):
                        # Se detach() non è supportato, usa il buffer
                        # direttamente
                        buffer = sys.stdout.buffer
                else:
                    buffer = sys.stdout.buffer

                # Crea nuovo wrapper con UTF-8
                sys.stdout = io.TextIOWrapper(
                    buffer,
                    encoding='utf-8',
                    errors='replace',
                    line_buffering=True
                )
            except (AttributeError, ValueError, OSError, UnsupportedOperation):
                # Se fallisce, continua senza modifiche
                pass

        # Stesso per stderr
        needs_stderr_fix = True
        if isinstance(sys.stderr, io.TextIOWrapper):
            encoding = getattr(
                sys.stderr,
                'encoding',
                '').lower().replace(
                '-',
                '')
            if encoding in ('utf8', 'utf'):
                needs_stderr_fix = False

        if needs_stderr_fix and hasattr(sys.stderr, 'buffer'):
            try:
                if isinstance(sys.stderr, io.TextIOWrapper):
                    try:
                        buffer = sys.stderr.detach()
                    except (AttributeError, UnsupportedOperation):
                        buffer = sys.stderr.buffer
                else:
                    buffer = sys.stderr.buffer

                sys.stderr = io.TextIOWrapper(
                    buffer,
                    encoding='utf-8',
                    errors='replace',
                    line_buffering=True
                )
            except (AttributeError, ValueError, OSError, UnsupportedOperation):
                pass
    except Exception:
        # Se tutto fallisce, continua senza modifiche
        pass

# Importa e esegui il main


async def select_ollama_model():
    """Permette all'utente di selezionare il modello Ollama"""
    print("\n[MODELLI] Modelli disponibili:")

    try:
        import subprocess

        result = subprocess.run(
            ['ollama', 'list'], capture_output=True, text=True, timeout=5)

        if result.returncode != 0:
            return None

        lines = result.stdout.strip().split('\n')
        if len(lines) < 2:
            return None

        models = []
        for line in lines[1:]:
            parts = line.split()
            if parts:
                models.append(parts[0])

        if not models:
            return None

        for idx, model in enumerate(models, 1):
            print(f"  {idx}. {model}")

       
        choice = input(f"Scegli (1-{len(models)} o INVIO): ").strip()

        if not choice:
            return None

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                return models[idx]
        except ValueError:
            pass

        return None

    except Exception:
        return None

if __name__ == "__main__":
    print("=" * 70)
    print("[TOOL] Social Engineering Research Tool v1.0")
    print("=" * 70)
    print()
    print("Strumento avanzato di ricerca OSINT per analisi comportamentale.")
    print("Utilizza AI locale (Ollama) per analizzare informazioni pubbliche")
    print("e generare profili target per test di social engineering.")
    print()
    print("FUNZIONALITA:")
    print("  • Ricerca multi-fonte (web search, social media)")
    print("  • Analisi AI avanzata con modelli locali")
    print("  • Generazione messaggi social engineering")
    print("  • Integrazione WhatsApp per test realistici")
    print()
    print("NOTA: Solo per scopi educativi e di sicurezza.")
    print("=" * 70)
    print()
    
    # Selezione modello prima dell'inizializzazione
    selected_model = asyncio.run(select_ollama_model())
    if selected_model:
        os.environ['OLLAMA_MODEL'] = selected_model
    
    # Avvia il tool principale (inizializzazione in main_cli.py)
    asyncio.run(main())

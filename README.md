## Social Engineering Research Tool

**Social Engineering Research Tool** è uno strumento di ricerca sperimentale che integra **ricerca web**, **modelli di intelligenza artificiale** (Ollama) e **WhatsApp Web** per studiare, in un contesto controllato, tecniche di **social engineering** applicate alla comunicazione digitale.

---

## Contesto della tesi e obiettivi

Questo repository fa parte di un progetto di tesi il cui obiettivo è:

- **Analizzare** come la combinazione di fonti aperte, modelli linguistici e canali di messaggistica possa supportare la costruzione di messaggi di social engineering.
- **Valutare** rischi, limiti e potenzialità dell’uso di AI generativa in scenari di social engineering mirato e comunicazione persuasiva.
- **Dimostrare** un workflow integrato: raccolta informazioni → analisi automatica del profilo → generazione di messaggi → simulazione di invio su WhatsApp.

---

## Funzionalità

### Raccolta informazioni sul target
- Ricerca web automatizzata su un soggetto
- Formattazione dell'input e controlli di sicurezza

### Analisi AI del profilo
- Integrazione con Ollama
- Estrazione informazioni chiave
- Generazione profilo sintetico

### Generazione messaggi
- Creazione automatica di messaggi WhatsApp
- Simulazione di attacchi social engineering

### Integrazione WhatsApp Web
- Connessione tramite automazione browser
- Invio messaggi automatizzato
- Conversazione AI contestuale

### Gestione file e logging
- Salvataggio risultati in JSON/TXT
- Logging di sicurezza
- Tracciamento input malevoli


---

## Requisiti di sistema

 - Windows 10/11 
 - Linux / macOS 

 - Python 3.10+ 
 - Ollama installato e in esecuzione
---

## Installazione

1. **Clona il repository**

 ```bash
 git clone <URL_DEL_REPO>
 cd SocialEngineering
 ```

2. **Crea e attiva un virtual environment**

3. **Installa le dipendenze**

4. **Configura l’ambiente**
 - Crea un file `.env` nella root (oppure usa `config/default.env`).
 - Verifica in particolare:
 - **`OLLAMA_HOST`** (es. `http://127.0.0.1:11434`, non `0.0.0.0`).
 - **`OLLAMA_MODEL`** (es. `llama3.2:1b` o il modello che preferisci).
 - Controlla `config/config.yaml` per la scelta del backend AI:
 - `ai_backend: "ollama"` oppure `ai_backend: "vllm"` o `"auto"`.

---

## Configurazione

I principali parametri sono definiti in `config/config.yaml`:

1. **Backend AI**
 - `ai_backend`: `"ollama"`, `"vllm"` o `"auto"`.

2. **Sezione `vllm`**
 - `model`: nome del modello (es. `"microsoft/Phi-3-mini-4k-instruct"`).
 - `max_tokens`, `temperature`, `gpu_memory_utilization`, `max_model_len`.

3. **Sezione `ollama`**
 - `host`: URL del server Ollama (es. `"http://localhost:11434"`).
 - `model`: nome del modello (es. `"llama3.2:1b"`).
 - `timeout`: timeout per le richieste al modello.

4. **Web search, WhatsApp, files, performance, logging**
 - Parametri per numero risultati, timeout, directory di output, livello di logging, ecc.

---

## Utilizzo

### Avvio rapido (interfaccia interattiva)

Dalla root del progetto:

```bash
python main.py
```
L’applicazione esegue un test di connessione a Ollama e poi avvia la **modalità interattiva**, in cui si può:

- inserire un **target** (nome e cognome);
- eseguire la **ricerca web**;
- lasciare che l’AI costruisca un **profilo** del soggetto;
- generare e inviare un **messaggio WhatsApp** (facoltativamente).





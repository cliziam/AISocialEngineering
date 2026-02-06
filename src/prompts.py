"""
Template di prompt per il modello AI (Ollama)
Centralizza tutti i prompt per facilità di manutenzione e testing
"""

import re
from typing import Dict, List, Any


class AIPrompts:
    """Template di prompt per diverse operazioni AI"""

    @staticmethod
    def fix_conversation_message_syntax(message: str, conversation_history: str = "", target_info: str = "") -> str:
        """
        Prompt per correggere sintassi di messaggi in una CONVERSAZIONE ATTIVA
        Più conservativo: NON aggiunge contenuto, SOLO virgole
        
        Args:
            message: Messaggio da correggere
            conversation_history: Storico conversazione per contesto
            target_info: Informazioni sul target (opzionale)
            
        Returns:
            Prompt formattato per correzione sintassi conversazionale
        """
        # Estrai ultimo messaggio del target dallo storico
        last_target_message = ""
        if conversation_history and conversation_history.strip():
            # Pattern per timestamp tipo "19:20" o righe solo numeri
            time_only_re = re.compile(r'^\d{1,2}:\d{2}$')
            digits_only_re = re.compile(r'^\d+$')
            # Cerca l'ultimo messaggio che non è "Tu:" e non è timestamp/numerico
            lines = conversation_history.strip().split('\n')
            for line in reversed(lines):
                if line.strip() and not line.strip().startswith('Tu:'):
                    if ':' in line:
                        content = line.split(':', 1)[1].strip()
                        # Salta timestamp (19:20) o solo numeri (20) che inquinano l'estrazione
                        if not content or len(content) < 3:
                            continue
                        if time_only_re.match(content) or digits_only_re.match(content):
                            continue
                        last_target_message = content
                        break
        
        # Costruisci sezione storico se disponibile
        history_section = ""
        if conversation_history and conversation_history.strip():
            # Limita lunghezza storico (max 500 caratteri)
            clean_history = conversation_history[-500:] if len(conversation_history) > 500 else conversation_history
            history_section = f"""
STORICO CONVERSAZIONE (per contesto):
{clean_history}

"""

        # Costruisci sezione informazioni target se disponibili
        target_section = ""
        if target_info and target_info.strip():
            target_section = f"""
INFORMAZIONI SUL TARGET (per verifica coerenza):
{target_info[:300]}

"""

        # Costruisci sezione messaggio target
        target_message_section = ""
        if last_target_message:
            target_message_section = f"""
ULTIMO MESSAGGIO DEL TARGET:
{last_target_message}

"""

        return f"""Sto facendo una conversazione con un target.
{target_message_section}
TUA RISPOSTA DA CORREGGERE:
{message}

La conversazione è la seguente:

{history_section}{target_section}

🎯 OBIETTIVO: IL MESSAGGIO DEVE ESSERE DIRETTO E RISPONDERE ALL'ULTIMO MESSAGGIO DEL TARGET SENZA AGGIUNGERE ALTRE INFORMAZIONI, 
PIù è DIRETTO, MEGLIO SARA' IL MESSAGGIO.
DEVI ESSERE NATURALE, NON UN MESSAGGIO AI.

REGOLE CRITICHE PER CONVERSAZIONI:
1. ⚠️ NON aggiungere frasi o dettagli che non sono nel messaggio originale
2. ⚠️ Mantieni il messaggio BREVE - è una conversazione WhatsApp, non una email
3. ⚠️ Non salutare il target, se lo ha già fatto, non salutarlo di nuovo.

Correggi il messaggio e rispondi SOLO con il messaggio corretto:"""

    @staticmethod
    def fix_message_syntax(message: str, target_info: str = "") -> str:
        """
        Prompt per correggere la sintassi e verificare la coerenza del messaggio
        
        Args:
            message: Messaggio da correggere
            target_info: Informazioni sul target per verificare coerenza (opzionale)
            
        Returns:
            Prompt formattato per correzione sintassi e verifica contenuto
        """
        # Costruisci sezione informazioni target se disponibili
        target_section = ""
        if target_info and target_info.strip():
            target_section = f"""

INFORMAZIONI SUL TARGET (per verifica coerenza):
{target_info[:500]}

⚠️ DOUBLE CHECK CONTENUTO:
- Verifica che il messaggio menzioni informazioni presenti sopra E CHE SIANO COERENTI
- Se il messaggio parla di progetti/competenze NON presenti, RIMUOVILI
- NON inventare dettagli non verificabili
- Non ESSERE PROLISSO, CERCA DI ESSERE BREVE E CONCISO
- Mantieni solo riferimenti generici al settore se non hai dettagli specifici
"""

        return f"""
Trasforma questo messaggio in un messaggio WhatsApp VERO E NATURALE che una persona italiana scriverebbe davvero.
inoltre, non deve essere un messaggio di AI, deve essere un messaggio naturale e umano, quindi aggiungi POCHE informazioni che 
possono essere vere sul soggetto che scrive il messaggio. NON SUL TARGET, MA SUL SOGGETTO CHE SCRIVE IL MESSAGGIO.
NON ESSERE PROLISSO, CERCA DI ESSERE BREVE E CONCISO E NON FARE RIPETIZIONI.

MESSAGGIO ORIGINALE:
{message}
{target_section}
🎯 OBIETTIVO: Aggiungi virgole e migliora la punteggiatura rendilo umano e naturale, MA mantieni il contenuto!

⚠️ REGOLA FONDAMENTALE:
**NON RIMUOVERE INFORMAZIONI!** 

Rispondi SOLO con il messaggio corretto senza spiegazioni:"""

    @staticmethod
    def analyze_text(text: str) -> str:
        """
        Prompt per analisi generale del testo

        Args:
            text: Testo da analizzare

        Returns:
            Prompt formattato
        """
        return f"""
Analizza il seguente testo e restituisci un JSON con le seguenti informazioni:
- sentiment: sentiment del testo (positivo, negativo, neutro)
- key_points: lista dei punti chiave (massimo 5)
- summary: riassunto in 2-3 frasi
- entities: entità menzionate (persone, luoghi, organizzazioni)

Testo da analizzare:
{text}

Rispondi SOLO con il JSON, senza altre spiegazioni.
"""

    @staticmethod
    def summarize_information(
        information_list: List[str],
        max_sentences: int = 3
    ) -> str:
        """Prompt per riassunto di informazioni multiple"""
        combined_text = "\n".join(information_list)

        return f"""
Riassumi le seguenti informazioni in {max_sentences} frasi concise, evidenziando i punti più importanti:

{combined_text}

Riassunto:
"""

    @staticmethod
    def generate_whatsapp_message(
        content: str,
        tone: str = "professionale",
        max_length: int = 1000
    ) -> str:
        """Prompt per generare messaggio WhatsApp standard"""
        return f"""
Crea un messaggio WhatsApp per il seguente contenuto, con tono {tone}:

{content}

Requisiti:
- Massimo {max_length} caratteri
- NON usare emoji o emoticon
- Linguaggio naturale e coinvolgente
- Mantieni le informazioni essenziali
- Specifica chiaramente chi sta parlando e il suo ruolo all'inizio del messaggio

Messaggio:
"""

    @staticmethod
    def generate_social_engineering_message(
        name: str,
        context_info: str,
        impersonation_context: str,
        scenario_desc: str,
        work: str = "",
        ai_summary: str = "",
        max_length: int = 1000
    ) -> str:
        """
        Prompt per generare messaggio di social engineering REALISTICO

        Args:
            name: Nome della persona target (NON dell'impersonatore)
            context_info: Informazioni contestuali sul target (lavoro, interessi, ecc.)
            impersonation_context: Chi fingi di essere (es: "collega", "parente", "fornitore")
            scenario_desc: Descrizione dello scenario (es: "ha bisogno urgente di soldi")
            work: Informazioni sul lavoro del target (opzionale)
            ai_summary: Riassunto AI in linguaggio naturale per creare contesto (opzionale)
            max_length: Lunghezza massima del messaggio

        Returns:
            Prompt formattato per generare un messaggio convincente
        """
        # Estrai solo il nome di battesimo (non il cognome)
        first_name = name.split()[0] if name else "la persona"
        
        # Costruisci la sezione del riassunto AI se disponibile
        ai_context_section = ""
        if ai_summary and ai_summary.strip():
            ai_context_section = f"""
CONTESTO DETTAGLIATO DEL TARGET (USA TUTTE QUESTE INFORMAZIONI per creare un messaggio personalizzato e credibile):
{ai_summary}

ISTRUZIONI PER PERSONALIZZAZIONE:
- Usa dettagli specifici dall'occupazione e competenze per sembrare credibile
- Fai riferimento al settore/ambito lavorativo in modo naturale
- Se conosci progetti o realizzazioni specifiche, puoi accennarvi vagamente
- Mostra di conoscere l'ambito professionale del target

"""
        
        return f"""
Scrivi un messaggio WhatsApp REALISTICO per fare social engineering su {name}.

INFORMAZIONI SUL TARGET ({name.upper()}):
{context_info}
{f"Lavoro: {work}" if work else ""}

{ai_context_section}OBIETTIVO: {scenario_desc}

SCELTA DELL'IDENTITÀ (IMPORTANTE):
Basandoti sulle informazioni del target, DEVI scegliere l'identità più credibile tra:
- COLLEGA: se lavora in ambito professionale/aziendale
- CLIENTE: se offre servizi/consulenze 
- FORNITORE: se ha un'azienda o gestisce acquisti
- AMICO/CONOSCENTE: se sembra più accessibile/informale
- PARENTE: solo se hai informazioni familiari 

Scegli l'identità che rende il messaggio PIÙ CREDIBILE dato il suo lavoro e settore.
IMPORTANTE: Fingi di essere quella persona, non dire "{impersonation_context}"!

❌ NON usare emoji o emoticon
❌ NON usare punti finali (.) - su WhatsApp non si usano!
❌ NON usare virgolette o formattazione
❌ NON menzionare MAI: "AI", "social engineering", "ricerca", "analisi", "report"

🎯 FORMATO MESSAGGIO (IMPORTANTE - SEGUI ALLA LETTERA):

1. **INIZIO** (OBBLIGATORIO): 
   "Ciao {first_name}, sono [NOME ITALIANO CREDIBILE]"
   - Esempi nomi: Marco, Luca, Andrea, Francesco, Giulia, Matteo
   - DEVI sempre iniziare così
   
2. **CONTESTO** (breve, 1-2 frasi):
   - Chi sei (ruolo credibile basato sul target)
   - Come lo hai trovato: "ti scrivo perché..." / "mi hanno parlato di te..." / "ho visto il tuo profilo..."
   
3. **MOTIVO** (1 frase):
   - Cosa vuoi: consulenza/collaborazione/info
   - Soft e non aggressivo
   - Dettaglio credibile ma generico

4. **CHIUSURA** (opzionale):
   - "potresti darmi una mano" / "saresti disponibile" / "possiamo sentirci"

📝 REGOLE DI SCRITTURA NATURALE:

✅ **FRASI CORTE**: max 15-20 parole per frase
✅ **VIRGOLE**: usa virgole per separare i concetti
✅ **COLLOQUIALE**: parla come su WhatsApp, non come email formale
✅ **SPONTANEO**: deve sembrare scritto da persona vera

❌ **EVITA ASSOLUTAMENTE**:
- Frasi lunghe 40+ parole senza pause
- Linguaggio formale tipo "sollecitare", "interlocutore"  
- Tutto in una frase unica senza virgole
- Costruzioni complesse

📏 LIMITI:
- Massimo {max_length} caratteri
- 3-4 frasi brevi separate da virgole
- NO punto finale
- NO troncare


Scrivi SOLO il messaggio (INIZIA con "Ciao {first_name}, sono..."), nient'altro:
"""

    @staticmethod
    def extract_name(text: str) -> str:
        """
        Prompt per estrarre solo il nome completo da un testo
        
        Args:
            text: Testo da cui estrarre il nome
            
        Returns:
            Prompt per estrazione nome
        """
        return f"""
Estrai SOLO il nome completo (nome e cognome) da questo testo.

Testo:
{text}

Rispondi SOLO con il nome completo, senza altre spiegazioni.
Se non trovi un nome, rispondi "Sconosciuto".

Nome:
"""

    @staticmethod
    def generate_search_queries(subject: str, context: str = "") -> str:
        """
        Prompt per generare query di ricerca su una persona
        
        Args:
            subject: Nome della persona
            context: Contesto aggiuntivo (opzionale)
            
        Returns:
            Prompt per generazione query
        """
        return f"""
Analizza queste informazioni iniziali su "{subject}" e genera 3-5 query di ricerca aggiuntive 
per trovare informazioni più dettagliate online.

{f"Contesto: {context}" if context else ""}

OBIETTIVO: Trovare informazioni professionali e di contatto utili per approccio professionale.

Genera query specifiche e mirate come:
- "[Nome] [Cognome] LinkedIn"
- "[Nome] [Cognome] azienda lavoro"
- "[Nome] [Cognome] profilo professionale"

Rispondi SOLO con una lista di query (una per riga), senza numerazione o spiegazioni:
"""

    @staticmethod
    def analyze_profile_for_contact(context: str) -> str:
        """
        Prompt per analizzare profilo e identificare approccio migliore
        
        Args:
            context: Informazioni sul profilo da analizzare
            
        Returns:
            Prompt per analisi profilo
        """
        return f"""
Analizza questo profilo e identifica caratteristiche utili per un primo contatto professionale.

{context}

Rispondi SOLO con JSON:
{{
  "communication_style": "formale/informale/tecnico",
  "likely_interests": ["interesse1", "interesse2"],
  "professional_pain_points": ["problema1", "problema2"],
  "best_approach": "strategia di contatto consigliata",
  "conversation_topics": ["topic1", "topic2"],
  "time_sensitivity": "alta/media/bassa"
}}
"""

    @staticmethod
    def analyze_social_media_presence(profile_name: str, work: str, social_data: str) -> str:
        """
        Prompt per analizzare presenza sui social media
        
        Args:
            profile_name: Nome del profilo
            work: Lavoro/occupazione
            social_data: Dati social da analizzare
            
        Returns:
            Prompt per analisi social media
        """
        return f"""
Analizza l'attività social di questa persona:

Profilo: {profile_name} - {work}

Attività social:
{social_data}

Rispondi SOLO con JSON:
{{
  "activity_level": "alta/media/bassa",
  "posting_frequency": "quotidiana/settimanale/mensile",
  "main_topics": ["topic1", "topic2", "topic3"],
  "tone": "professionale/casual/misto",
  "engagement_patterns": "descrizione breve",
  "best_contact_time": "mattina/pomeriggio/sera"
}}
"""

    @staticmethod
    def generate_followup_message(
        conversation_history: str,
        target_name: str,
        goal: str = "maintain_engagement"
    ) -> str:
        """
        Prompt per generare messaggio di follow-up naturale
        
        Args:
            conversation_history: Storico conversazione
            target_name: Nome del target
            goal: Obiettivo (maintain_engagement/request_action/provide_info/build_trust)
            
        Returns:
            Prompt per follow-up
        """
        goal_descriptions = {
            "maintain_engagement": "Mantieni il contatto vivo, mostra interesse",
            "request_action": "Chiedi un'azione specifica (incontro, chiamata, informazione)",
            "provide_info": "Fornisci informazioni utili per costruire fiducia",
            "build_trust": "Costruisci fiducia e credibilità"
        }
        goal_desc = goal_descriptions.get(goal, goal_descriptions["maintain_engagement"])
        
        return f"""
Continua questa conversazione WhatsApp in modo NATURALE.

CONVERSAZIONE FINORA:
{conversation_history}

OBIETTIVO: {goal_desc}

REGOLE:
- Rispondi in modo naturale e colloquiale
- Massimo 150 caratteri
- NON usare emoji o emoticon
- Mantieni il tono coerente con la conversazione
- Se {target_name} ha fatto domande, rispondi prima di proseguire

Scrivi SOLO la risposta:
"""

    @staticmethod
    def generate_reply_to_response(
        original_message: str,
        target_response: str,
        target_name: str,
        context: str = ""
    ) -> str:
        """
        Prompt per generare risposta a una risposta del target
        
        Args:
            original_message: Messaggio originale inviato
            target_response: Risposta ricevuta dal target
            target_name: Nome del target
            context: Contesto aggiuntivo
            
        Returns:
            Prompt per risposta
        """
        return f"""
Il target ha risposto al tuo messaggio. Genera una risposta appropriata.

TUO MESSAGGIO ORIGINALE:
{original_message}

RISPOSTA DI {target_name.upper()}:
{target_response}

{f"CONTESTO: {context}" if context else ""}

REGOLE:
- Rispondi DIRETTAMENTE a quello che ha scritto
- Mantieni tono naturale e professionale
- Massimo 150 caratteri
- NON usare emoji o emoticon
- Se mostra interesse, fornisci più dettagli
- Se ha resistenze, non insistere troppo

Scrivi SOLO la risposta:
"""

    @staticmethod
    def create_comprehensive_profile(context: str, new_info: str) -> str:
        """
        Prompt per creare profilo completo e dettagliato
        
        Args:
            context: Contesto e informazioni precedenti
            new_info: Nuove informazioni da integrare
            
        Returns:
            Prompt per creazione profilo
        """
        return f"""
Basandoti sulla conversazione precedente e su queste nuove informazioni, crea un profilo completo e dettagliato.

INFORMAZIONI PRECEDENTI:
{context}

NUOVE INFORMAZIONI:
{new_info}

REGOLE CRITICHE:
- Integra tutte le informazioni in un profilo coerente
- Organizza per categorie (Personale, Professionale, Contatti, Interessi, etc.)
- Sii specifico e dettagliato
- Evidenzia informazioni utili per il contatto
- Formato: testo strutturato e leggibile

Profilo completo:
"""
    
    @staticmethod
    def generate_conversational_response(
        conversation_history: List[Dict[str, str]],
        target_info: Dict[str, Any],
        impersonation_context: str = "auto",
        scenario: str = "richiesta_aiuto",
        max_length: int = 500
    ) -> str:
        """
        Prompt per generare risposta di social engineering nella conversazione
        OBIETTIVO: Portare gradualmente alla richiesta di soldi

        Args:
            conversation_history: Lista di messaggi [{"role": "user/assistant", "content": "..."}]
            target_info: Informazioni sul target (nome, lavoro, ecc.)
            impersonation_context: Chi fingi di essere (collega, parente, cliente, ecc.)
            scenario: Scenario della conversazione
            max_length: Lunghezza massima della risposta

        Returns:
            Prompt formattato per generare una risposta convincente
        """

        name = target_info.get('name', 'il destinatario')
        work = target_info.get('work', '')
        
        # Estrai il contesto completo se disponibile
        full_context = target_info.get('full_context', '')
        
        # Costruisci sezione contesto dettagliato
        context_section = ""
        if full_context:
            context_section = f"""
INFORMAZIONI DETTAGLIATE SUL TARGET (usa per personalizzare la risposta):
{full_context[:1500]}

"""

        # Costruisci lo storico della conversazione
        conversation_text = ""
        for i, msg in enumerate(conversation_history[-6:], 1):  # Ultimi 6 messaggi
            role = "Tu" if msg.get('role') == 'assistant' else name
            content = msg.get('content', '')
            conversation_text += f"{role}: {content}\n"

        # Conta i messaggi per capire a che punto siamo
        num_messages = len(conversation_history)

        # Gestisci "auto" per impersonation_context
        context_instruction = ""
        if impersonation_context == "auto":
            context_instruction = """
- Chi fingi di essere: SCEGLI TU l'identità più credibile (collega, cliente, fornitore, conoscente) basandoti sul lavoro del target
"""
        else:
            context_instruction = f"""
- Chi fingi di essere: {impersonation_context}
"""
        
        # Estrai l'ultimo messaggio del target per analizzarlo
        last_target_message = ""
        for msg in reversed(conversation_history):
            if msg.get('role') != 'assistant':
                last_target_message = msg.get('content', '')
                break
        
        return f"""
Sei in una conversazione WhatsApp con {name}. Stai facendo SOCIAL ENGINEERING per ottenere soldi.

CONTESTO:
{context_instruction}- Scenario: {scenario}
- Target: {name} ({work if work else 'professionista'})
- Turno conversazione: {num_messages}

{context_section}STORICO CONVERSAZIONE:
{conversation_text}

⚠️ ULTIMO MESSAGGIO DI {name.upper()}:
"{last_target_message}"

🎯 REGOLA FONDAMENTALE: DEVI RISPONDERE A QUESTO ULTIMO MESSAGGIO DEL TARGET!


COME COSTRUIRE LA RISPOSTA:
1. PRIMA: Rispondi direttamente al suo ultimo messaggio messaggio
2. POI (opzionale): Aggiungi 1 frase per far progredire la strategia verso soldi
3. SEMPRE: Mantieni tono colloquiale e naturale

REGOLE CRITICHE:
- ⚠️ PRIMA di tutto RISPONDI al suo messaggio
- Massimo {max_length} caratteri
- Tono COLLOQUIALE italiano (WhatsApp)
- NON usare emoji, punti finali (.), virgolette
- Sii BREVE, DIRETTO, NATURALE
- Scrivi come PERSONA REALE

Risposta (SOLO il messaggio, SENZA punto finale):
"""


class SocialEngineeringPromptBuilder:
    """Builder specializzato per prompt di social engineering"""

    @staticmethod
    def build_context_info(
        name: str,
        work: str = "",
        location: str = "",
        interests: List[str] = None,
        recent_activities: List[str] = None
    ) -> str:
        """
        Costruisce la sezione informazioni contestuali

        Args:
            name: Nome della persona
            work: Lavoro/posizione
            location: Località
            interests: Lista di interessi
            recent_activities: Attività recenti

        Returns:
            Stringa con informazioni formattate
        """
        info_parts = [f"Nome: {name}"]

        if work:
            info_parts.append(f"Lavoro: {work}")
        if location:
            info_parts.append(f"Località: {location}")
        if interests:
            info_parts.append(f"Interessi: {', '.join(interests[:3])}")
        if recent_activities:
            info_parts.append(f"Attività recenti: {', '.join(recent_activities[:2])}")

        return "\n".join(info_parts)

    @staticmethod
    def get_rules() -> List[str]:
        """Ottiene le regole standard per social engineering"""
        return [
            "NON menzionare MAI parole come 'ricerca', 'analisi', 'AI', 'social engineering', 'report'",
            "Scrivi in PRIMA PERSONA",
            "Specifica chiaramente chi sei e il tuo ruolo",
            "Usa un tono NATURALE e COLLOQUIALE italiano",
            "NON usare emoji o emoticon",
            "NON includere frasi tipo 'Ecco un messaggio' o 'Messaggio WhatsApp'",
            "Mantieni il messaggio breve e diretto"]

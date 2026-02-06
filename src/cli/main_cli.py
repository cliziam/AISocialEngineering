"""
Interfaccia a riga di comando principale
"""

import asyncio
import argparse
from typing import Dict, Any
from datetime import datetime

# Import con prefisso src. (root del progetto)
from src.core.config_manager import ConfigManager
from src.core.hardware_optimizer import HardwareOptimizer
from src.core.file_manager import FileManager
from src.integrations.ollama_client import OllamaClient
from src.integrations.web_searcher import WebSearcher
from src.integrations.whatsapp_client import WhatsAppClient
from src.utils.formatters import format_search_results, format_system_info
from src.utils.helpers import get_timestamp

class SocialEngineeringTool:
    """Tool principale per ricerca sociale e comunicazione"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.hardware_optimizer = HardwareOptimizer(self.config_manager)
        self.file_manager = FileManager(self.config_manager)
        self.ollama_client = OllamaClient(self.config_manager)
        self.web_searcher = WebSearcher(self.config_manager)
        self.whatsapp_client = WhatsAppClient(self.config_manager)
        
        self.search_results = []
        self.analysis = {}
        self.summary = ""
        
    async def initialize(self):
        """Inizializza tutti i componenti"""
        print("[INIT] Inizializzazione...", end=" ", flush=True)
        await self.ollama_client.initialize()
        print("[OK]")
        
    async def research_subject(self, subject: str, 
                             custom_search_terms: list = None,
                             auto_send_whatsapp: bool = False,
                             whatsapp_contact: str = None) -> Dict[str, Any]:
        """Esegue la ricerca completa su un soggetto"""
        
        # Sanitizza input
        from src.utils.validators import sanitize_search_term, detect_sql_injection, detect_xss_attempt
        from src.utils.security_logger import get_security_logger
        
        security_logger = get_security_logger()
        
        # Controlla injection attempts
        if detect_sql_injection(subject):
            security_logger.log_injection_attempt('subject', subject, 'SQL_INJECTION', 'research_subject')
            print("[ERR] Input non valido")
            return {}
        
        if detect_xss_attempt(subject):
            security_logger.log_injection_attempt('subject', subject, 'XSS', 'research_subject')
            print("[ERR] Input non valido")
            return {}
        
        # Sanitizza
        subject = sanitize_search_term(subject)
        
        if not subject:
            print("[ERR] Input non valido")
            return {}
        
        print(f"\n[SEARCH] Ricerca: {subject}")
        
        # Esegui ricerca web
        print("[WEB] Ricerca web...", end=" ", flush=True)
        self.search_results = await self.web_searcher.search_subject(
            subject, custom_search_terms
        )
        
        if not self.search_results:
            print("[ERR]")
            return {}
            
        print(f"[OK] ({len(self.search_results)} risultati)")
        
        # Analizza i risultati con Ollama
        print("[AI] Analisi AI...", end=" ", flush=True)
        
        # Usa il nuovo metodo che fa ricerche aggiuntive guidate da LLM e crea profilo completo
        self.analysis = await self.ollama_client.analyze_target_profile(
            self.search_results, 
            web_searcher=self.web_searcher
        )
        
        if self.analysis:
            print("[OK] Profilo target completato")
            
            # Mostra informazioni estratte
            print(f"\n[PROFILO] PROFILO:")
            if self.analysis.get('name'):
                print(f"   [NOME] {self.analysis['name']}")
            if self.analysis.get('work'):
                print(f"   [WORK] {self.analysis['work']}")
            if self.analysis.get('location'):
                print(f"   [LOC] {self.analysis['location']}")
            if self.analysis.get('explanation'):
                print(f"\n   [INFO] SPIEGAZIONE:")
                print(f"   {self.analysis['explanation']}")
            if self.analysis.get('key_achievements'):
                print(f"\n   [KEY] REALIZZAZIONI CHIAVE:")
                for achievement in self.analysis['key_achievements'][:3]:
                    print(f"   • {achievement}")
            
            # Salva il summary dall'analisi
            self.summary = self.analysis.get('summary', '')
            
            # NUOVO: Salva automaticamente l'analisi AI in un file TXT dedicato
            print("\n[SAVE] Salvataggio analisi AI...")
            ai_analysis_file = self.file_manager.save_ai_analysis(
                analysis=self.analysis,
                subject=subject,
                search_results_count=len(self.search_results)
            )
            if ai_analysis_file:
                print(f"   [OK] Analisi AI salvata: {ai_analysis_file}")
        else:
            print("[WARN] Analisi AI non completata")
        
        # Salva le informazioni
        print("\n[SAVE] Salvataggio...")
        file_path = self.file_manager.save_research_results(
            self.search_results, 
            self.analysis, 
            self.summary,
            subject,
            format_type="both"
        )
        
        if file_path:
            print(f"[OK] Salvato")
            
        # Invio automatico messaggio WhatsApp se richiesto
        if auto_send_whatsapp and whatsapp_contact:
            print("\n[WA] INVIO AUTOMATICO WHATSAPP")
            try:
                # Determina se è un numero o nome contatto
                if whatsapp_contact.isdigit() or whatsapp_contact.startswith('+'):
                    success = await self.send_whatsapp_report(phone_number=whatsapp_contact)
                else:
                    success = await self.send_whatsapp_report(contact_name=whatsapp_contact)
                    
                if success:
                    print("[OK] Messaggio inviato!")
                else:
                    print("[ERR] Invio fallito")
            except Exception as e:
                print(f"[ERR] Errore nell'invio automatico: {e}")
            
        return {
            'subject': subject,
            'search_results': self.search_results,
            'analysis': self.analysis,
            'summary': self.summary,
            'file_path': file_path
        }
        
    async def send_whatsapp_report(self, phone_number: str = None, 
                                 contact_name: str = None,
                                 use_social_engineering: bool = True,
                                 scenario: str = "richiesta_aiuto",
                                 context: str = "auto",
                                 use_robust_method: bool = True) -> bool:
        """Invia un messaggio via WhatsApp
        
        Args:
            phone_number: Numero di telefono destinatario
            contact_name: Nome contatto WhatsApp destinatario
            use_social_engineering: Se True, genera messaggio di social engineering convincente
                                   Se False, genera report tecnico
            scenario: Scenario del messaggio (richiesta_aiuto, urgenza, opportunità, ecc.)
            context: Contesto di impersonificazione ("auto" = LLM sceglie automaticamente, oppure: collega, amico, familiare, cliente, fornitore)
            use_robust_method: Se True, usa il metodo robusto con retry automatici (CONSIGLIATO)
        """
        
        if not self.search_results:
            print("[ERR] Devi prima fare una ricerca!")
            return False
            
        # Inizializza WhatsApp
        print("\n[WA] Connessione WhatsApp...")
        if not await self.whatsapp_client.initialize():
            print("[ERR] Impossibile connettersi")
            return False
        
        # Genera il messaggio in base al tipo
        if use_social_engineering:
            # Estrai informazioni dalla ricerca per social engineering
            target_info = self._extract_target_info()
            
            print(f"[SE] Social Engineering - {scenario}")
            work_info = target_info.get('work', 'N/A') or 'N/A'
            print(f"[TARGET] Target: {target_info.get('name', 'N/A')}, {work_info}")
            
            # Costruisci contesto completo con TUTTE le informazioni disponibili
            full_ai_context = self._build_full_context_for_ai()
            
            whatsapp_message = await self.ollama_client.generate_social_engineering_message(
                target_info=target_info,
                impersonation_context=context,
                scenario=scenario,
                max_length=1000,  # Aumentato per messaggi più completi
                ai_summary=full_ai_context  # Passa TUTTO il contesto invece del solo summary
            )
        else:
            # Genera report tecnico (modalità originale)
            print("[REPORT] Report tecnico")
            report_content = self._generate_whatsapp_report()
            whatsapp_message = await self.ollama_client.generate_whatsapp_message(
                report_content, "professionale"
            )
        
        
        # Verifica che il messaggio sia stato generato
        if not whatsapp_message or len(whatsapp_message.strip()) == 0:
            print("[ERR] Errore: messaggio vuoto generato da Ollama")
            print("[INFO] WhatsApp è stato caricato correttamente, ma non posso generare messaggi senza Ollama.")
            print("[INFO] Soluzioni:")
            print("   1. Avvia Ollama (ollama serve) e riprova")
            print("   2. Oppure inserisci manualmente il messaggio quando richiesto")
            return False
        
        # Chiedi conferma prima di inviare
        print("Cosa vuoi fare?")
        print("   [s] Invia il messaggio")
        print("   [m] Modifica il messaggio")
        print("   [n] Annulla (non inviare)")
        confirm = input("Scelta (s/m/n, default s): ").strip().lower()
        
        if confirm in ['n', 'no']:
            print("[STOP] Invio annullato dall'utente.")
            return False
        elif confirm in ['m', 'modifica', 'modify']:
            print("\n[EDIT] Inserisci il messaggio modificato:")
            whatsapp_message = input("> ").strip()
            if not whatsapp_message:
                print("[STOP] Messaggio vuoto, invio annullato.")
                return False
            print(f"\n[OK] Messaggio modificato:\n{whatsapp_message}\n")
        
        # Invia il messaggio iniziale
        success = False
        
        if use_robust_method:
            # USA METODO ROBUSTO (CONSIGLIATO)
            print("\n[ROBUST] Uso metodo robusto con retry automatici...")
            
            # Usa timeout dalla configurazione
            whatsapp_timeout = self.config_manager.get('whatsapp_timeout', 120)
            
            if phone_number:
                print(f"[SEND] Invio a numero: {phone_number}")
                success = await self.whatsapp_client.send_message_robust(
                    phone_number, whatsapp_message, timeout=whatsapp_timeout
                )
            elif contact_name:
                print(f"[SEND] Invio a contatto: {contact_name}")
                success = await self.whatsapp_client.send_message_to_contact_robust(
                    contact_name, whatsapp_message, timeout=whatsapp_timeout
                )
            else:
                print("[ERR] Specifica un numero di telefono o nome contatto")
                return False
        else:
            # USA METODO STANDARD (LEGACY)
            print("\n[WARN] Uso metodo standard (meno affidabile)...")
            print("[INFO] Suggerimento: Usa use_robust_method=True per maggiore affidabilità")
            
            if phone_number:
                print(f"[SEND] Invio messaggio a numero: {phone_number}")
                success = await self.whatsapp_client.send_message(phone_number, whatsapp_message)
            elif contact_name:
                print(f"[SEND] Invio messaggio a contatto: {contact_name}")
                success = await self.whatsapp_client.send_message_to_contact(contact_name, whatsapp_message)
            else:
                print("[ERR] Specifica un numero di telefono o nome contatto")
                return False
        
        if not success:
            print("\n[ERR] Invio fallito")
            print("[INFO] Verifica che WhatsApp Web sia caricato e il contatto esista")
            return False
        
        print("\n[OK] Messaggio inviato!")
        
        # Avvia automaticamente la conversazione
        print("\n[CONV] Modalità conversazione attiva")
        
        # Estrai informazioni target se necessario
        target_info_for_conversation = None
        if use_social_engineering:
            target_info_for_conversation = self._extract_target_info()
        
        await self._continue_conversation(
            phone_number=phone_number,
            contact_name=contact_name,
            target_info=target_info_for_conversation,
            impersonation_context=context if use_social_engineering else "assistente",
                scenario=scenario if use_social_engineering else "richiesta_aiuto",
                initial_message=whatsapp_message
            )
            
        return success
    
    async def _continue_conversation(self,
                                   phone_number: str = None,
                                   contact_name: str = None,
                                   target_info: Dict[str, Any] = None,
                                   impersonation_context: str = "collega",
                                   scenario: str = "richiesta_aiuto",
                                   initial_message: str = None):
        """Continua la conversazione attendendo risposte e generando risposte contestuali
        
        Args:
            phone_number: Numero di telefono (se usato)
            contact_name: Nome contatto (se usato)
            target_info: Informazioni sul target
            impersonation_context: Contesto di impersonificazione
            scenario: Scenario della conversazione
            initial_message: Messaggio iniziale inviato
        """
        
        # Inizializza lo storico della conversazione
        conversation_history = []
        
        # Aggiungi il messaggio iniziale allo storico se disponibile
        if initial_message:
            conversation_history.append({"role": "assistant", "content": initial_message})
        
        print("\n[CONV] MODALITÀ CONVERSAZIONE ATTIVA")
        print("=" * 40)
        print(f"[WAIT] Attendo risposte in loop continuo...")
        print("[INFO] Premi Ctrl+C per interrompere\n")
        
        turn_count = 0
        
        try:
            while True:  # Loop infinito
                turn_count += 1
                print(f"\n[TURN] Turno {turn_count}")
                
                # Attendi un messaggio
                received_message = await self.whatsapp_client.wait_for_message(timeout=300)
                
                if not received_message:
                    print("[TIMEOUT] Nessuna risposta ricevuta. Conversazione terminata.")
                    break
                
                # Aggiungi il messaggio ricevuto allo storico
                conversation_history.append({"role": "user", "content": received_message})
                
                # Stampa il messaggio ricevuto completo
                print(f"[RX] Ricevuto: {received_message}")
                
                # Genera risposta contestuale se abbiamo informazioni sul target
                if target_info:
                    print("[AI] Generazione risposta contestuale...")
                    
                    # Arricchisci target_info con il contesto completo
                    full_context = self._build_full_context_for_ai()
                    target_info_enriched = target_info.copy()
                    target_info_enriched['full_context'] = full_context
                    
                    response = await self.ollama_client.generate_conversational_response(
                        conversation_history=conversation_history,
                        target_info=target_info_enriched,
                        impersonation_context=impersonation_context,
                        scenario=scenario,
                        max_length=500  # Aumentato anche per le risposte
                    )
                else:
                    # Fallback: risposta generica
                    response = "Grazie per la risposta! Ti scrivo presto con i dettagli."
                
                
                # Chiedi conferma con opzioni
                print("\nCosa vuoi fare?")
                print("   [s] Invia")
                print("   [m] Modifica")
                print("   [n] Salta (non inviare)")
                choice = input("Scelta (s/m/n, default s): ").strip().lower()
                
                if choice == 'n' or choice == 'no':
                    print("[STOP] Messaggio non inviato. Conversazione terminata.")
                    break
                elif choice == 'm' or choice == 'modifica':
                    print("\n[EDIT] Inserisci il messaggio modificato:")
                    response = input("> ").strip()
                    if not response:
                        print("[STOP] Messaggio vuoto, conversazione terminata.")
                        break
                    print(f"[OK] Messaggio modificato: {response}")
                
                # Invia la risposta nella chat corrente (già aperta)
                whatsapp_timeout = self.config_manager.get('whatsapp_timeout', 120)
                
                print("[TX] Invio risposta nella chat corrente...")
                success = await self.whatsapp_client.send_message_in_current_chat(
                    response, timeout=whatsapp_timeout
                )
                
                # Fallback: se fallisce, prova con il metodo standard
                if not success:
                    print("[WARN] Fallback: provo con metodo standard...")
                    if phone_number:
                        success = await self.whatsapp_client.send_message_robust(
                            phone_number, response, timeout=whatsapp_timeout
                        )
                    elif contact_name:
                        success = await self.whatsapp_client.send_message_to_contact_robust(
                            contact_name, response, timeout=whatsapp_timeout
                        )
                    else:
                        print("[ERR] Errore: nessun contatto specificato")
                        break
                
                if not success:
                    print("[ERR] Errore nell'invio della risposta")
                    break
                
                # Aggiungi la risposta inviata allo storico
                conversation_history.append({"role": "assistant", "content": response})
                
                # Continua automaticamente
                print(f"\n[AUTO] In attesa automatica della prossima risposta...")
                
        except KeyboardInterrupt:
            print("\n[STOP] Conversazione interrotta dall'utente.")
        except Exception as e:
            print(f"\n[ERR] Errore nella conversazione: {e}")
        
        print(f"\n[STATS] Conversazione completata: {len(conversation_history)} messaggi scambiati")
        
    def _build_full_context_for_ai(self) -> str:
        """
        Costruisce un contesto completo con TUTTE le informazioni disponibili
        per il prompt dell'LLM, massimizzando la qualità del messaggio generato
        """
        context_parts = []
        
        # 1. INFORMAZIONI PRINCIPALI
        if self.analysis:
            if self.analysis.get('name'):
                context_parts.append(f"NOME COMPLETO: {self.analysis['name']}")
            
            if self.analysis.get('work'):
                context_parts.append(f"OCCUPAZIONE: {self.analysis['work']}")
            
            if self.analysis.get('location'):
                context_parts.append(f"POSIZIONE: {self.analysis['location']}")
            
            if self.analysis.get('summary'):
                context_parts.append(f"RIASSUNTO: {self.analysis['summary']}")
            
            # 2. SPIEGAZIONE DETTAGLIATA
            if self.analysis.get('explanation'):
                context_parts.append(f"\nDETTAGLI:\n{self.analysis['explanation']}")
            
            # 3. COMPETENZE
            if self.analysis.get('skills'):
                skills_text = ", ".join(self.analysis['skills'][:10])
                context_parts.append(f"\nCOMPETENZE: {skills_text}")
            
            # 4. REALIZZAZIONI E PROGETTI
            if self.analysis.get('key_achievements'):
                achievements_text = "\n- ".join(self.analysis['key_achievements'][:5])
                context_parts.append(f"\nREALIZZAZIONI CHIAVE:\n- {achievements_text}")
            
            # 5. INTERESSI
            if self.analysis.get('interests'):
                interests_text = ", ".join(self.analysis['interests'][:5])
                context_parts.append(f"\nINTERESSI: {interests_text}")
            elif self.analysis.get('key_points'):
                interests_text = ", ".join(self.analysis['key_points'][:5])
                context_parts.append(f"\nAREE DI FOCUS: {interests_text}")
            
            # 6. EDUCAZIONE
            if self.analysis.get('education'):
                context_parts.append(f"\nEDUCAZIONE: {self.analysis['education']}")
            
            # 7. PROFILI SOCIAL
            if self.analysis.get('social_profiles'):
                profiles_text = ", ".join(self.analysis['social_profiles'][:3])
                context_parts.append(f"\nPROFILI SOCIAL: {profiles_text}")
            
            # 8. ATTIVITÀ RECENTI
            if self.analysis.get('recent_activities'):
                activities_text = "\n- ".join(self.analysis['recent_activities'][:3])
                context_parts.append(f"\nATTIVITÀ RECENTI:\n- {activities_text}")
        
        # 9. INFORMAZIONI DAI RISULTATI DI RICERCA (anteprime più rilevanti)
        if self.search_results:
            context_parts.append("\n\nCONTESTO AGGIUNTIVO DAI RISULTATI DI RICERCA:")
            for i, result in enumerate(self.search_results[:5], 1):
                snippet = result.get('snippet', '')
                if snippet and len(snippet) > 30:
                    context_parts.append(f"{i}. {snippet[:300]}")
        
        # Unisci tutto
        full_context = "\n".join(context_parts)
        
        # Limita lunghezza totale per non sovraccaricare il prompt (max 3000 caratteri)
        if len(full_context) > 3000:
            full_context = full_context[:3000] + "\n[... altre informazioni disponibili ...]"
        
        return full_context
        
    def _extract_target_info(self) -> Dict[str, Any]:
        """Estrae informazioni strutturate usando l'analisi AI già fatta (ottimizzato)"""
        
        # Usa direttamente l'analisi AI già fatta invece di riprocessare
        name = self.analysis.get('name', 'sconosciuto') if self.analysis else 'sconosciuto'
        work = self.analysis.get('work', '') if self.analysis else ''
        location = self.analysis.get('location', '') if self.analysis else ''
        skills = self.analysis.get('skills', []) if self.analysis else []
        
        # IMPORTANTE: Pulisci il nome da descrizioni lavorative
        # Se il nome contiene keyword lavorative, probabilmente è sbagliato
        work_keywords = ['CTP', 'CTU', 'Perizie', 'Forensi', 'Informatiche', 'ambito', 
                        'Civile', 'Penale', 'Consulente', 'Esperto', 'Specializzato',
                        'Manager', 'Director', 'Engineer', 'Developer']
        
        # Controlla se il nome è effettivamente una descrizione lavorativa
        if name and name != 'sconosciuto':
            name_lower = name.lower()
            # Se contiene più di 2 keyword lavorative, è probabilmente una descrizione
            keyword_count = sum(1 for kw in work_keywords if kw.lower() in name_lower)
            
            if keyword_count >= 2 or len(name) > 60:
                # È una descrizione, non un nome - cerca il nome vero
                name = 'sconosciuto'
        
        # Fallback al primo risultato se l'AI non ha estratto il nome o è invalido
        if name == 'sconosciuto' and self.search_results:
            first_result = self.search_results[0]
            title = first_result.get('title', '')
            
            # Rimuovi suffissi comuni
            for remove_part in [' - LinkedIn', ' | LinkedIn', ' - Facebook', ' - Wikipedia', 
                               ' - Bio', ' (@', ' profile', ' profilo']:
                if remove_part in title:
                    title = title.split(remove_part)[0]
            
            # Estrai solo la prima parte (prima di virgole/parentesi/punti)
            clean_title = title.split(',')[0].split('(')[0].split('|')[0].split('.')[0].strip()
            
            # Rimuovi keyword lavorative comuni
            for kw in work_keywords:
                if kw.lower() in clean_title.lower():
                    # Prova a prendere solo la parte prima della keyword
                    parts = clean_title.split(kw)
                    if parts[0].strip():
                        clean_title = parts[0].strip()
                    else:
                        clean_title = ''
                    break
            
            # Valida che sia un nome ragionevole (max 50 caratteri, almeno 2 parole)
            if clean_title and len(clean_title) <= 50 and len(clean_title.split()) >= 1:
                # Controlla che non contenga ancora keyword lavorative
                if not any(kw.lower() in clean_title.lower() for kw in work_keywords):
                    name = clean_title
                else:
                    # Se contiene ancora keyword, prova a estrarre solo le prime 2-3 parole
                    words = clean_title.split()
                    if len(words) >= 2:
                        # Prendi solo nome e cognome (primi 2-3 elementi)
                        name = ' '.join(words[:3])
                    else:
                        name = 'sconosciuto'
            else:
                name = 'sconosciuto'
        
        # Se ancora non abbiamo un nome valido, usa un placeholder generico
        if name == 'sconosciuto' or len(name) > 50:
            # Prova a estrarre dalle prime parole del work se disponibile
            if work:
                # Prendi solo le prime 2-3 parole del lavoro come fallback
                work_words = work.split()[:3]
                if work_words:
                    name = ' '.join(work_words)
                else:
                    name = 'Professionista'  # Fallback generico
            else:
                name = 'Professionista'
        
        # Interessi dai key_points
        interests = self.analysis.get('key_points', [])[:3] if self.analysis else []
        
        # Attività recenti dal summary
        recent_activities = []
        if self.summary:
            summary_sentences = self.summary.split('.')[:2]
            recent_activities = [s.strip() for s in summary_sentences if s.strip() and len(s.strip()) > 10]
        
        # Descrizione sintetica
        target_description = name
        if work:
            target_description += f", {work}"
        if location:
            target_description += f" - {location}"
        
        return {
            'name': name,
            'work': work,
            'interests': interests,
            'location': location,
            'recent_activities': recent_activities,
            'skills': skills,
            'description': target_description,
            'raw_data': {
                'summary': self.summary[:300] if self.summary else "",
                'analysis': self.analysis
            }
        }
    
    def _generate_whatsapp_report(self) -> str:
        """Genera il contenuto del report per WhatsApp (modalità report tecnico)"""
        
        report = f"RICERCA SOCIAL ENGINEERING\n\n"
        
        if self.summary:
            report += f"RIASSUNTO:\n{self.summary[:200]}...\n\n"
            
        if self.analysis:
            report += f"ANALISI AI:\n"
            report += f"Sentiment: {self.analysis.get('sentiment', 'N/A')}\n"
            
            if self.analysis.get('key_points'):
                report += f"Punti chiave: {len(self.analysis['key_points'])} trovati\n"
                
        report += f"TOTALE RISULTATI: {len(self.search_results)}\n"
        report += f"GENERATO: {get_timestamp('%d/%m/%Y %H:%M')}"
        
        return report
        
    async def _handle_research_target(self):
        """Gestisce l'opzione di ricerca target"""
        print("\nRICERCA TARGET")
        print("Inserisci il nome completo della persona da ricercare")
        print("   Esempio:  'Mario Rossi', ecc.")
        
        # Sanitizza input
        from src.utils.validators import sanitize_input, detect_sql_injection, detect_xss_attempt
        
        subject = input("\nNome e Cognome del target: ").strip()
        
        if not subject:
            print("[ERRORE] Nome non valido!")
            return
        
        # Controlla tentativi di injection
        if detect_sql_injection(subject) or detect_xss_attempt(subject):
            print("[ERRORE] Input non valido: caratteri sospetti rilevati")
            return
        
        # Sanitizza
        subject = sanitize_input(subject, max_length=100, allow_special_chars=False)
        
        if not subject:
            print("[ERRORE] Nome non valido dopo sanitizzazione!")
            return
        
        whatsapp_contact = input("\nNumero telefono o nome contatto WhatsApp: ").strip()
        
        if whatsapp_contact:
            whatsapp_contact = sanitize_input(whatsapp_contact, max_length=50, allow_special_chars=False)
        
        await self.research_subject(
            subject, 
            auto_send_whatsapp=bool(whatsapp_contact), 
            whatsapp_contact=whatsapp_contact
        )
    
    async def _handle_load_saved_research(self):
        """Gestisce il caricamento di una ricerca salvata"""
        files = self.file_manager.list_files()
        json_files = [f for f in files if f['name'].endswith('.json') and '_data_' in f['name']]
        
        if not json_files:
            print("[ERRORE] Nessuna ricerca salvata trovata!")
            print("Esegui prima una ricerca (opzione 1)")
            return False
        
        print(f"\nRICERCHE SALVATE ({len(json_files)}):")
        print("=" * 40)
        for i, file_info in enumerate(json_files[:10], 1):
            filename = file_info['name']
            subject_match = filename.split('_data_')[0].replace('_', ' ').title()
            print(f"{i}. {subject_match}")
            print(f"   {file_info['modified']}")
        
        file_choice = input(f"\nScegli ricerca (1-{min(len(json_files), 10)}): ").strip()
        
        try:
            file_idx = int(file_choice) - 1
            if 0 <= file_idx < len(json_files):
                selected_file = json_files[file_idx]
                file_path = self.file_manager.output_dir / selected_file['name']
                
                print(f"\nCaricamento ricerca: {selected_file['name']}...")
                data = self.file_manager.load_data(str(file_path), format_type="json")
                
                if data:
                    self.search_results = data.get('search_results', [])
                    self.analysis = data.get('analysis', {})
                    self.summary = data.get('summary', '')
                    subject = data.get('metadata', {}).get('subject', 'Sconosciuto')
                    print(f"[OK] Ricerca caricata: {subject}")
                    print(f"   {len(self.search_results)} risultati")
                    return True
                else:
                    print("[ERRORE] Errore nel caricamento della ricerca")
                    return False
            else:
                print("[ERRORE] Scelta non valida")
                return False
        except ValueError:
            print("[ERRORE] Inserisci un numero valido")
            return False
    
    async def interactive_mode(self):
        """Modalità interattiva per l'utente"""
        
        print("\nSOCIAL ENGINEERING TOOL")
        print("Workflow: Ricerca -> Analisi AI -> Messaggio -> WhatsApp\n")
        
        while True:
            print("\nMenu:")
            print("1. Ricerca target")
            print("2. Invia messaggio WhatsApp")
            print("3. Statistiche sistema")
            print("4. File salvati")
            print("5. Test connessioni")
            print("6. Configurazione")
            print("7. Chiudi WhatsApp")
            print("8. Pulisci cache")
            print("9. Esci")
            
            choice = input("\nScelta (1-9): ").strip()
            
            if choice == "1":
                await self._handle_research_target()
                    
            elif choice == "2":
                # Opzione 1: Usa ricerca corrente o carica una salvata
                if not self.search_results:
                    print("\nNessuna ricerca corrente. Vuoi caricare una ricerca salvata?")
                    load_choice = input("   (s/n, default s): ").strip().lower()
                    
                    if load_choice in ['s', 'si', 'y', 'yes', '']:
                        if not await self._handle_load_saved_research():
                            continue
                    else:
                        print("[ERRORE] Devi prima fare una ricerca (opzione 1)!")
                        continue
                
                # Inizializza WhatsApp se non è già connesso
                if not self.whatsapp_client.is_connected:
                    print("\n[WA] Inizializzazione WhatsApp...")
                    print("Scansiona il QR code se richiesto...")
                    
                    if not await self.whatsapp_client.initialize():
                        print("[ERRORE] Impossibile connettersi a WhatsApp")
                        print("Verifica che:")
                        print("   - WhatsApp sia installato sul telefono")
                        print("   - Il telefono sia connesso a Internet")
                        print("   - Hai scansionato il QR code correttamente")
                        continue
                    
                    print("[OK] WhatsApp connesso!")
                
                # Analizza conversazione WhatsApp esistente se disponibile
                # (disabilitato per velocizzare - per riabilitarlo, decommentare)
                conversation_context = None
                # if self.whatsapp_client.is_connected:
                #     print("\n[CONV] Analizzare conversazione esistente? (s/n): ", end='')
                #     analyze_conv = input().strip().lower()
                #     if analyze_conv in ['s', 'si', 'y', 'yes']:
                #         conversation_context = await self._select_and_analyze_conversation()
                #         if conversation_context:
                #             print(f"[OK] {len(conversation_context.get('messages', []))} messaggi analizzati")
                
                # Parametri automatici per velocità
                # Usa sempre Social Engineering con scenario ottimale
                use_se = True
                scenario = "richiesta_aiuto"  # Scenario più naturale e convincente
                context = "auto"  # L'LLM sceglie automaticamente il contesto più credibile
                
                print("\n[SE] Generazione messaggio Social Engineering...")
                print(f"   [INFO] Scenario: {scenario} | Contesto: L'LLM sceglierà automaticamente")
                
                # Genera messaggio considerando la conversazione se disponibile
                if conversation_context and use_se:
                    print("\n[AI] Generazione messaggio basato sulla conversazione...")
                    target_info = self._extract_target_info()
                    # Aggiungi contesto conversazione al target_info
                    target_info['conversation_context'] = conversation_context
                    
                    # Genera messaggio contestuale
                    whatsapp_message = await self._generate_contextual_message(
                        target_info=target_info,
                        conversation_context=conversation_context,
                        scenario=scenario,
                        context=context
                    )
                    
                    print(f"\n[MSG] Messaggio generato:\n{whatsapp_message}\n")
                    
                    # Destinatario (invio diretto senza conferma)
                    phone = input("\nInserisci numero telefono (o lascia vuoto per nome contatto): ").strip()
                    if phone:
                        success = await self.whatsapp_client.send_message(phone, whatsapp_message)
                    else:
                        contact = input("Inserisci nome contatto: ").strip()
                        if contact:
                            success = await self.whatsapp_client.send_message_to_contact(contact, whatsapp_message)
                        else:
                            print("[ERR] Nessun destinatario specificato")
                            continue
                    
                    if success:
                        print("[OK] Messaggio inviato!")
                        # Avvia automaticamente la conversazione
                        print("\n[CONV] MODALITÀ CONVERSAZIONE ATTIVA")
                        print("="*70)
                        await self._continue_conversation(
                            phone_number=phone if phone else None,
                            contact_name=contact if not phone else None,
                            target_info=target_info,
                            impersonation_context=context,
                            scenario=scenario
                        )
                    else:
                        print("[ERR] Invio fallito")
                else:
                    # Comportamento originale se non c'è conversazione da analizzare
                    phone = input("\nInserisci numero telefono (o lascia vuoto per nome contatto): ").strip()
                    success = False
                    if phone:
                        success = await self.send_whatsapp_report(
                            phone_number=phone,
                            use_social_engineering=use_se,
                            scenario=scenario,
                            context=context
                        )
                    else:
                        contact = input("Inserisci nome contatto: ").strip()
                        if contact:
                            success = await self.send_whatsapp_report(
                                contact_name=contact,
                                use_social_engineering=use_se,
                                scenario=scenario,
                                context=context
                            )
                        else:
                            print("[ERR] Nessun destinatario specificato")
                            continue
                    
                    if success:
                        print("[OK] Messaggio inviato con successo!")
                    else:
                        print("[ERR] Errore nell'invio del messaggio")
                        
            elif choice == "3":
                self._show_system_stats()
                
            elif choice == "4":
                self._show_saved_files()
                
            elif choice == "5":
                await self._test_connections()
                
            elif choice == "6":
                self._show_configuration()
                
            elif choice == "7":
                self.whatsapp_client.close(force_close=True)
                print("[OK] WhatsApp chiuso")
            
            elif choice == "8":
                # Pulisci cache ricerche
                self.web_searcher.clear_cache()
                print("[OK] Cache ricerche pulita")
                
            elif choice == "9":
                print("Arrivederci!")
                break
                
            else:
                print("[ERRORE] Opzione non valida")
                
    def _show_system_stats(self):
        """Mostra statistiche del sistema"""
        
        print("\n[STATS] STATISTICHE SISTEMA")
        
        # Info hardware
        self.hardware_optimizer.print_system_info()
        
        # Info Ollama
        ollama_info = self.ollama_client.get_model_info()
        print(f"\n[OLLAMA] Ollama:")
        print(f"  Modelli disponibili: {len(ollama_info['available_models'])}")
        print(f"  Modello corrente: {ollama_info['current_model']}")
        
        # Info file
        files = self.file_manager.list_files()
        if files:
            print(f"\n[FILES] File salvati:")
            print(f"  Numero file: {len(files)}")
            print(f"  Ultimo file: {files[0]['name']}")
            
        # Info WhatsApp
        whatsapp_status = self.whatsapp_client.get_connection_status()
        print(f"\n[WA] WhatsApp:")
        print(f"  Connesso: {whatsapp_status['connected']}")
        
        # Info Web Search
        search_stats = self.web_searcher.get_search_stats()
        print(f"\n[SEARCH] Ricerca Web:")
        print(f"  Ricerche totali: {search_stats['total_searches']}")
        print(f"  Successo: {search_stats['success_rate']}%")
        
    def _show_saved_files(self):
        """Mostra i file salvati"""
        
        files = self.file_manager.list_files()
        
        if not files:
            print("[ERR] Nessun file salvato trovato")
            return
            
        print(f"\n[FILES] FILE SALVATI ({len(files)}):")
        
        for i, file_info in enumerate(files[:10], 1):  # Mostra max 10 file
            print(f"{i}. {file_info['name']}")
            print(f"   Dimensione: {file_info['size_mb']} MB")
            print(f"   Modificato: {file_info['modified']}")
            
        if len(files) > 10:
            print(f"... e altri {len(files) - 10} file")
            
    async def _test_connections(self):
        """Testa le connessioni"""
        
        print("\n[TEST] TEST CONNESSIONI")
        print("=" * 20)
        
        # Test Ollama
        print("[OLLAMA] Test Ollama...")
        ollama_ok = await self.ollama_client.test_connection()
        print(f"  {'[OK] OK' if ollama_ok else '[ERR] FALLITO'}")
        
        # Test Web Search
        print("[SEARCH] Test ricerca web...")
        web_ok = await self.web_searcher.test_connection()
        print(f"  {'[OK] OK' if web_ok else '[ERR] FALLITO'}")
        
        # Test WhatsApp
        print("[WA] Test WhatsApp...")
        whatsapp_ok = await self.whatsapp_client.test_connection()
        print(f"  {'[OK] OK' if whatsapp_ok else '[ERR] FALLITO'}")
        
        print(f"\n[STATS] Risultato: {sum([ollama_ok, web_ok, whatsapp_ok])}/3 connessioni OK")
        
    def _show_configuration(self):
        """Mostra la configurazione corrente"""
        
        self.config_manager.print_config()
    
    async def _select_and_analyze_conversation(self) -> Dict[str, Any]:
        """
        Permette di selezionare una chat dalla lista e poi la analizza.
        
        Returns:
            Dict con informazioni sulla conversazione analizzata
        """
        if not self.whatsapp_client.is_connected or not self.whatsapp_client.driver:
            print("  [WARN] WhatsApp non connesso")
            return None
        
        try:
            # Naviga alla home di WhatsApp per essere sicuri di vedere la lista chat
            print("  [HOME] Navigazione alla schermata principale...")
            await self.whatsapp_client.navigate_to_home()
            
            # Ottieni lista chat disponibili
            print("  [CHAT] Caricamento lista chat...")
            chats = await self.whatsapp_client.get_available_chats(max_chats=15)
            
            if not chats:
                print("\n  [WARN] Impossibile recuperare la lista delle chat")
                print("  [INFO] Assicurati che:")
                print("     - WhatsApp Web sia completamente caricato")
                print("     - La lista delle chat sia visibile sulla sinistra")
                print("     - Non ci siano popup o finestre di dialogo aperte")
                
                # Offri opzione alternativa
                use_current = input("\n  [SELECT] Vuoi analizzare la chat attualmente aperta? (s/n): ").strip().lower()
                if use_current in ['s', 'si', 'y', 'yes']:
                    print("  [ANALYZE] Analisi della chat corrente...")
                    return await self._analyze_current_conversation()
                else:
                    return None
            
            # Mostra lista chat
            print("\n[CHATS] CHAT DISPONIBILI:")
            print("=" * 60)
            for chat in chats:
                chat_name = chat.get('name', 'Sconosciuto')
                last_msg = chat.get('last_message', '')
                last_msg_preview = f" - {last_msg[:30]}..." if last_msg else ''
                print(f"{chat['index'] + 1}. {chat_name}{last_msg_preview}")
            
            # Chiedi quale chat analizzare
            print("=" * 60)
            chat_choice = input(f"\n[SELECT] Quale chat vuoi analizzare? (1-{len(chats)}, 0 per annullare): ").strip()
            
            try:
                chat_idx = int(chat_choice) - 1
                if chat_idx < 0:
                    print("  [STOP] Analisi annullata")
                    return None
                if chat_idx >= len(chats):
                    print("  [WARN] Numero non valido")
                    return None
            except ValueError:
                print("  [WARN] Inserisci un numero valido")
                return None
            
            # Apri la chat selezionata
            selected_chat = chats[chat_idx]
            print(f"\n  [OPEN] Apertura chat: {selected_chat.get('name', 'Sconosciuto')}...")
            
            if not await self.whatsapp_client.open_chat_by_index(chat_idx):
                print("  [ERR] Impossibile aprire la chat")
                return None
            
            # Ora analizza la chat aperta
            return await self._analyze_current_conversation()
            
        except Exception as e:
            print(f"  [ERR] Errore nella selezione chat: {e}")
            import traceback
            print(f"  [INFO] Dettagli: {traceback.format_exc()[:200]}")
            return None
    
    async def _analyze_current_conversation(self) -> Dict[str, Any]:
        """
        Analizza la conversazione WhatsApp corrente per estrarre contesto.
        
        Returns:
            Dict con informazioni sulla conversazione (messaggi, tono, argomenti, ecc.)
        """
        if not self.whatsapp_client.is_connected or not self.whatsapp_client.driver:
            return None
        
        try:
            print("  [READ] Lettura messaggi dalla chat corrente...")
            messages = await self.whatsapp_client._get_chat_messages()
            
            if not messages:
                print("  [WARN] Nessun messaggio trovato nella chat corrente")
                return None
            
            # Separa messaggi ricevuti e inviati
            received_messages = [m for m in messages if m.get('is_received', False)]
            sent_messages = [m for m in messages if not m.get('is_received', False)]
            
            # Prendi gli ultimi messaggi per analisi (max 20)
            recent_received = received_messages[-10:] if len(received_messages) > 10 else received_messages
            recent_sent = sent_messages[-10:] if len(sent_messages) > 10 else sent_messages
            
            # Combina tutti i messaggi recenti per analisi
            all_recent = (recent_received + recent_sent)[-20:]
            
            if not all_recent:
                return None
            
            # Estrai testo dei messaggi
            conversation_text = "\n".join([m.get('text', '') for m in all_recent if m.get('text')])
            
            if not conversation_text.strip():
                return None
            
            print(f"  [AI] Analisi conversazione con AI...")
            # Analizza la conversazione con Ollama
            analysis_prompt = f"""
Analizza questa conversazione WhatsApp e estrai informazioni utili per generare un messaggio di risposta appropriato.

CONVERSAZIONE:
{conversation_text[:1500]}

Rispondi SOLO con questo JSON (niente altro):
{{
  "tone": "formale/informale/amichevole/professionale",
  "main_topics": ["argomento1", "argomento2"],
  "last_message_from_user": "ultimo messaggio ricevuto",
  "user_needs": ["bisogno1", "bisogno2"],
  "conversation_stage": "inizio/mezzo/fine",
  "suggested_response_style": "breve descrizione dello stile di risposta suggerito",
  "key_points_to_address": ["punto1", "punto2"]
}}
"""
            
            analysis_response = await self.ollama_client.generate_response(analysis_prompt)
            conversation_analysis = self.ollama_client._parse_json_response(analysis_response)
            
            return {
                'messages': all_recent,
                'received_count': len(received_messages),
                'sent_count': len(sent_messages),
                'conversation_text': conversation_text,
                'analysis': conversation_analysis,
                'last_received': recent_received[-1].get('text', '') if recent_received else '',
                'last_sent': recent_sent[-1].get('text', '') if recent_sent else ''
            }
            
        except Exception as e:
            print(f"  [WARN] Errore nell'analisi conversazione: {e}")
            return None
    
    async def _generate_contextual_message(self,
                                         target_info: Dict[str, Any],
                                         conversation_context: Dict[str, Any],
                                         scenario: str = "richiesta_aiuto",
                                         context: str = "collega") -> str:
        """
        Genera un messaggio WhatsApp basato sulla ricerca e sulla conversazione esistente.
        
        Args:
            target_info: Informazioni sul target dalla ricerca
            conversation_context: Contesto della conversazione WhatsApp
            scenario: Scenario del messaggio
            context: Contesto relazionale
            
        Returns:
            Messaggio WhatsApp generato
        """
        # Estrai informazioni dalla conversazione
        conv_analysis = conversation_context.get('analysis', {})
        last_received = conversation_context.get('last_received', '')
        tone = conv_analysis.get('tone', 'informale')
        main_topics = conv_analysis.get('main_topics', [])
        
        # Costruisci prompt per generare messaggio contestuale
        # Proteggi contro valori None
        target_name = target_info.get('name', 'N/A') or 'N/A'
        target_work = target_info.get('work', 'N/A') or 'N/A'
        target_desc = target_info.get('description', 'N/A') or 'N/A'
        
        prompt = f"""
Genera un messaggio WhatsApp NATURALE e CREDIBILE che continua questa conversazione.

TARGET (dalla ricerca):
- Nome: {target_name}
- Lavoro: {target_work}
- Descrizione: {target_desc[:200]}

CONTESTO CONVERSAZIONE:
- Tono attuale: {tone}
- Argomenti discussi: {', '.join(main_topics[:3]) if main_topics else 'Nessuno specifico'}
- Ultimo messaggio ricevuto: "{last_received[:200]}"

SCENARIO: {scenario}
RUOLO: {context}

REGOLE:
- Continua NATURALMENTE la conversazione esistente
- Riferisciti agli argomenti già discussi se appropriato
- Mantieni lo stesso tono ({tone})
- Sii BREVE e DIRETTO (max 180 caratteri)
- MAX 1 emoji solo se appropriata
- NON ripetere informazioni già dette
- Sii CREDIBILE e NATURALE

Scrivi SOLO il messaggio, niente altro:
"""
        
        message = await self.ollama_client.generate_response(prompt)
        return self.ollama_client._clean_message(message, max_length=180)
        
    async def cleanup(self, force_close_whatsapp: bool = False):
        """Pulizia risorse"""
        
        print("\n[CLEAN] Pulizia risorse...")
        self.whatsapp_client.close(force_close=force_close_whatsapp)
        print("[OK] Pulizia completata")

async def main():
    """Funzione principale"""
    
    parser = argparse.ArgumentParser(description='Social Engineering Research Tool')
    parser.add_argument('--research', type=str, help='Soggetto da ricercare')
    parser.add_argument('--whatsapp', type=str, help='Numero WhatsApp per invio report')
    parser.add_argument('--contact', type=str, help='Nome contatto WhatsApp per invio report')
    parser.add_argument('--auto-send', action='store_true', help='Invia automaticamente il report dopo la ricerca')
    parser.add_argument('--interactive', action='store_true', help='Modalità interattiva')
    parser.add_argument('--config', action='store_true', help='Mostra configurazione')
    parser.add_argument('--test', action='store_true', help='Testa connessioni')
    
    args = parser.parse_args()
    
    tool = SocialEngineeringTool()
    
    try:
        await tool.initialize()
        
        if args.config:
            tool._show_configuration()
            
        if args.test:
            await tool._test_connections()
            
        if args.research:
            # Determina il contatto WhatsApp per l'invio automatico
            whatsapp_contact = None
            if args.auto_send:
                if args.whatsapp:
                    whatsapp_contact = args.whatsapp
                elif args.contact:
                    whatsapp_contact = args.contact
                else:
                    whatsapp_contact = input("Inserisci numero telefono o nome contatto WhatsApp per l'invio automatico: ").strip()
            
            await tool.research_subject(
                args.research, 
                auto_send_whatsapp=args.auto_send,
                whatsapp_contact=whatsapp_contact
            )
            
        if args.whatsapp and not args.research:
            await tool.send_whatsapp_report(phone_number=args.whatsapp)
            
        if args.contact and not args.research:
            await tool.send_whatsapp_report(contact_name=args.contact)
            
        if args.interactive or not any([args.research, args.whatsapp, args.contact, args.config, args.test]):
            # Vai direttamente alla ricerca target senza mostrare il menu
            await tool._handle_research_target()
            
    except KeyboardInterrupt:
        print("\n[STOP] Interruzione da utente")
    except Exception as e:
        print(f"\n[ERR] Errore: {e}")
    finally:
        # Chiudi WhatsApp solo se non è in modalità interattiva o se è un comando singolo
        force_close = not args.interactive or any([args.research, args.whatsapp, args.contact, args.config, args.test])
        await tool.cleanup(force_close_whatsapp=force_close)

if __name__ == "__main__":
    print("[TOOL] Social Engineering Research Tool v1.0")
    print("Integra Ollama + Ricerca Web + WhatsApp")
    print("=" * 50)
    
    asyncio.run(main())

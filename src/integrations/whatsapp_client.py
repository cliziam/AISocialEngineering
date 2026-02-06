import asyncio
import os
import json
import time
import qrcode
from io import BytesIO
from typing import List, Dict, Any, Optional
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from src.core.config_manager import ConfigManager
from src.integrations.whatsapp_helpers import WhatsAppClicker
from src.integrations.whatsapp_fix import WhatsAppContactFixer

class WhatsAppMessageSender:
    """Classe helper per invio messaggi senza duplicazioni"""
    
    @staticmethod
    async def insert_text_no_duplicate(driver, input_box, message: str) -> bool:
        """
        Inserisce testo senza duplicazioni usando Selenium send_keys diretto
        
        Returns:
            True se inserimento riuscito
        """
        
        try:
            # Rimuovi emoji prima di inserire (ChromeDriver non le supporta - solo caratteri BMP)
            from src.utils.text_utils import remove_emoji
            message = remove_emoji(message)
            
            # METODO SEMPLIFICATO: Usa Selenium send_keys direttamente
            # (più affidabile di JavaScript per WhatsApp Web)
            
            # Step 1: Focus sull'input
            input_box.click()
            await asyncio.sleep(0.3)
            
            # Step 2: Verifica che sia vuoto (dovrebbe essere stato pulito prima)
            existing = input_box.text or input_box.get_attribute('innerText') or ''
            if existing.strip():
                return False
            
            # Step 3: Inserisci carattere per carattere (più lento ma più affidabile)
            # WhatsApp Web a volte perde caratteri con send_keys diretto
            chunk_size = 50  # Inserisci a blocchi di 50 caratteri
            for i in range(0, len(message), chunk_size):
                chunk = message[i:i+chunk_size]
                input_box.send_keys(chunk)
                await asyncio.sleep(0.1)  # Piccola pausa tra i chunk
            
            await asyncio.sleep(0.5)  # Attesa rendering finale
            
            # Step 4: Verifica che il testo sia stato inserito correttamente
            final_text = input_box.text or input_box.get_attribute('innerText') or ''
            final_len = len(final_text.strip())
            expected_len = len(message)
            
            # Considera successo se:
            # - Ha almeno l'80% del testo atteso
            # - Non ha più del 120% (duplicazione)
            if final_len >= expected_len * 0.8 and final_len <= expected_len * 1.3:
                return True
            else:
                return False
                
        except Exception as e:
            return False
    
    @staticmethod
    async def send_message_optimized(driver, phone_number: str, message: str) -> bool:
        """
        Invia messaggio ottimizzato senza duplicazioni
        
        Args:
            driver: Selenium WebDriver
            phone_number: Numero WhatsApp (formato +39...)
            message: Testo messaggio
            
        Returns:
            True se invio riuscito
        """
        
        try:
            print(f"📤 Invio a {phone_number}...")
            
            # Vai alla chat
            chat_url = f"https://web.whatsapp.com/send?phone={phone_number.lstrip('+')}"
            driver.get(chat_url)
            await asyncio.sleep(4)
            
            # Trova input box
            input_box = None
            input_selectors = [
                "[data-testid='conversation-compose-box-input']",
                "div[contenteditable='true'][data-tab='10']",
                "div[contenteditable='true'][role='textbox']",
                "footer div[contenteditable='true']"
            ]
            
            for selector in input_selectors:
                try:
                    input_box = WebDriverWait(driver, 8).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    print(f"  Input box trovata")
                    break
                except:
                    continue
            
            if not input_box:
                print("  ❌ Input box non trovata")
                return False
            
            # Inserisci testo SENZA duplicazioni
            text_ok = await WhatsAppMessageSender.insert_text_no_duplicate(
                driver, input_box, message
            )
            
            if not text_ok:
                print("  ❌ Inserimento testo fallito")
                return False
            
            # Invia con ENTER
            print("  📨 Invio messaggio...")
            try:
                input_box.send_keys(Keys.ENTER)
                await asyncio.sleep(2)
                print("  Messaggio inviato!")
                return True
            except:
                # Fallback: pulsante send
                try:
                    send_btn = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='send']"))
                    )
                    send_btn.click()
                    await asyncio.sleep(2)
                    print("  Messaggio inviato (pulsante)!")
                    return True
                except:
                    print("  ❌ Invio fallito")
                    return False
                    
        except Exception as e:
            print(f"Errore invio: {e}")
            return False


# ============================================================================
# INTEGRATION NEL TUO WHATSAPP CLIENT
# ============================================================================

class WhatsAppClient:
    """Client WhatsApp ottimizzato - usa nelle tue funzioni esistenti"""
    
    def __init__(self, config_manager: ConfigManager = None):
        self.config_manager = config_manager or ConfigManager()
        self.message_sender = WhatsAppMessageSender()
        
        # Configurazione WhatsApp
        whatsapp_config = self.config_manager.get_whatsapp_config()
        self.session_path = whatsapp_config.get('session_path', './sessions')
        self.timeout = whatsapp_config.get('timeout', 30)
        
        self.driver = None
        self.is_connected = False
        self.qr_timeout = self.config_manager.get('whatsapp_qr_timeout', 300)
        self.clicker = None  # Verrà inizializzato quando driver è disponibile
        
        # Statistiche
        self.stats = {
            'messages_sent': 0,
            'messages_failed': 0,
            'connections_attempted': 0,
            'connections_successful': 0
        }
    
    async def send_message(self, phone_number: str, message: str) -> bool:
        """Versione ottimizzata senza duplicazioni"""
        
        if not self.is_connected:
            print("WhatsApp non connesso")
            return False
        
        try:
            # Rimuovi emoji prima di inviare (ChromeDriver non le supporta)
            from src.utils.text_utils import remove_emoji
            message = remove_emoji(message)
            
            # Usa il nuovo metodo ottimizzato
            success = await self.message_sender.send_message_optimized(
                self.driver, phone_number, message
            )
            
            if success:
                self.stats['messages_sent'] += 1
            else:
                self.stats['messages_failed'] += 1
                
            return success
            
        except Exception as e:
            print(f"Errore: {e}")
            self.stats['messages_failed'] += 1
            return False
    
    async def send_message_to_contact(self, contact_name: str, message: str, timeout: int = 90) -> bool:
        """Versione ottimizzata per contatti con timeout di sicurezza
        
        Args:
            contact_name: Nome del contatto da cercare
            message: Messaggio da inviare
            timeout: Timeout massimo in secondi (default: 60)
        """
        
        if not self.is_connected:
            print("WhatsApp non connesso - impossibile inviare messaggio")
            print("Chiama prima whatsapp_client.initialize()")
            return False
        
        # Usa asyncio.wait_for per applicare un timeout generale
        try:
            return await asyncio.wait_for(
                self._send_message_to_contact_impl(contact_name, message),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            print(f"Timeout ({timeout}s) durante l'invio del messaggio a {contact_name}")
            print("Suggerimenti:")
            print("   - Verifica che WhatsApp Web sia responsive")
            print("   - Chiudi eventuali popup o notifiche")
            print("   - Riprova con un contatto diverso")
            self.stats['messages_failed'] += 1
            return False
        except Exception as e:
            print(f"Errore durante l'invio: {e}")
            self.stats['messages_failed'] += 1
            return False
    
    async def _send_message_to_contact_impl(self, contact_name: str, message: str) -> bool:
        """Implementazione interna di send_message_to_contact (senza timeout)"""
        try:
            # Assicurati che il clicker sia inizializzato se il driver esiste
            if self.driver and not self.clicker:
                self.clicker = WhatsAppClicker(self.driver)
            
            # 0. Verifica che la pagina sia responsive
            try:
                current_url = self.driver.current_url
                if "web.whatsapp.com" not in current_url:
                    print("Non sei su WhatsApp Web, ricarico...")
                    self.driver.get("https://web.whatsapp.com")
                    await asyncio.sleep(3)
            except Exception as url_error:
                print(f"Errore verifica URL: {str(url_error)[:50]}")
            
            # 1. Cerca contatto (tuo codice esistente)
            name_variations = self._generate_name_variations(contact_name)
            
            for search_term in name_variations:
                print(f"🔍 Cerco: {search_term}")
                
                # Ricerca contatto - trova la search box ogni volta (potrebbe cambiare)
                search_box = await self._find_search_box()
                if not search_box:
                    print("  ⚠️  Barra di ricerca non trovata")
                    continue
                
                # Metodo alternativo: chiudi e riapri la ricerca per resettarla completamente
                try:
                    # Chiudi la ricerca con ESC
                    search_box.send_keys(Keys.ESCAPE)
                    await asyncio.sleep(0.5)
                except:
                    pass
                
                # Pulisci correttamente la barra di ricerca prima di inserire il nuovo termine
                await self._clear_search_box(search_box)
                await asyncio.sleep(0.5)
                
                # Verifica che sia pulita prima di inserire
                try:
                    current_text = search_box.text or search_box.get_attribute('innerText') or ''
                    if current_text.strip():
                        print(f"  ⚠️  Barra non completamente pulita, riprovo...")
                        # Prova a chiudere completamente e riaprire
                        try:
                            search_box.send_keys(Keys.ESCAPE)
                            await asyncio.sleep(0.5)
                        except:
                            pass
                        await self._clear_search_box(search_box)
                        await asyncio.sleep(0.5)
                except:
                    pass
                
                # Inserisci il nuovo termine di ricerca
                try:
                    # Ricarica la search box per sicurezza
                    search_box = await self._find_search_box()
                    if not search_box:
                        continue
                    
                    # Clicca per attivare la ricerca
                    search_box.click()
                    await asyncio.sleep(0.3)
                    
                    # Verifica ancora una volta che sia vuota
                    try:
                        check_text = search_box.text or search_box.get_attribute('innerText') or ''
                        if check_text.strip() and check_text.strip() != search_term:
                            # Se c'è ancora testo vecchio, pulisci di nuovo
                            search_box.send_keys(Keys.CONTROL + "a")
                            search_box.send_keys(Keys.BACKSPACE)
                            await asyncio.sleep(0.2)
                    except:
                        pass
                    
                    # Ora inserisci il nuovo termine
                    search_box.send_keys(search_term)
                    await asyncio.sleep(4)
                except Exception as e:
                    print(f"  ⚠️  Errore inserimento termine ricerca: {e}")
                    continue
                
                # Cerca il risultato che corrisponde al contatto
                matching_chat = await self._find_matching_chat_result(contact_name, search_term)
                if not matching_chat:
                    print(f"  ⚠️  Nessun risultato corrispondente trovato per '{search_term}'")
                    continue
                
                print(f"  Contatto trovato: {matching_chat.get('name', 'N/A')}")
                
                # Usa WhatsAppClicker con multiple strategie per il click
                print("  🖱️  Clic sul contatto...")
                contact_element = matching_chat['element']
                contact_name = matching_chat.get('name', 'contatto')
                
                # IMPORTANTE: Salva lo stato prima del click per verificare il cambiamento
                url_before = self.driver.current_url
                
                # Diagnostica: verifica che l'elemento sia visibile e cliccabile
                try:
                    is_displayed = contact_element.is_displayed()
                    is_enabled = contact_element.is_enabled()
                    print(f"  📊 Elemento - Visibile: {is_displayed}, Abilitato: {is_enabled}")
                except Exception as diag_error:
                    print(f"  ⚠️  Errore diagnostica elemento: {str(diag_error)[:80]}")
                    # Se l'elemento è stale, riprova a trovarlo
                    print(f"  🔄 Elemento potrebbe essere stale, riprovo a trovarlo...")
                    matching_chat = await self._find_matching_chat_result(contact_name, search_term)
                    if not matching_chat:
                        print(f"  ❌ Impossibile ritrovare il contatto dopo errore")
                        continue
                    contact_element = matching_chat['element']
                
                # Assicurati che il clicker sia inizializzato
                if not self.clicker and self.driver:
                    self.clicker = WhatsAppClicker(self.driver)
                
                # Tenta il click con multiple strategie
                click_successful = False
                for click_attempt in range(3):  # Max 3 tentativi di click
                    if click_attempt > 0:
                        print(f"  🔄 Tentativo click {click_attempt + 1}/3...")
                        # Ricarica l'elemento se è stale
                        try:
                            matching_chat = await self._find_matching_chat_result(contact_name, search_term)
                            if matching_chat:
                                contact_element = matching_chat['element']
                        except:
                            pass
                    
                    if not self.clicker:
                        print("  ❌ Clicker non disponibile, uso metodo standard...")
                        try:
                            contact_element.click()
                            print("  Click standard eseguito")
                            click_successful = True
                            break
                        except Exception as e:
                            print(f"  ⚠️  Click standard fallito: {str(e)[:80]}")
                            if click_attempt < 2:
                                await asyncio.sleep(1)
                                continue
                    else:
                        # Usa il clicker con multiple strategie
                        click_success = await self.clicker.click_element(
                            contact_element, 
                            element_name=f"contatto '{contact_name}'"
                        )
                        
                        if click_success:
                            print("  Click eseguito con successo")
                            click_successful = True
                            break
                        
                        if click_attempt < 2:
                            print(f"  ⚠️  Click fallito, provo metodo alternativo...")
                            # Metodo alternativo: scroll + JavaScript
                            try:
                                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", contact_element)
                                await asyncio.sleep(1)
                                self.driver.execute_script("arguments[0].click();", contact_element)
                                await asyncio.sleep(1)
                                print(f"  Click JavaScript eseguito")
                                click_successful = True
                                break
                            except Exception as js_error:
                                print(f"  ⚠️  Click JavaScript fallito: {str(js_error)[:80]}")
                                if click_attempt < 2:
                                    await asyncio.sleep(1)
                                    continue
                
                if not click_successful:
                    print(f"  ❌ Impossibile cliccare sul contatto dopo 3 tentativi")
                    print(f"  💡 Possibili cause:")
                    print(f"     - Elemento coperto da overlay/popup")
                    print(f"     - WhatsApp Web non responsive")
                    print(f"     - Elemento non più presente nel DOM")
                    continue
                
                # VERIFICA CRITICA: Controlla che la chat si sia aperta
                print("  🔍 Verifica apertura chat...")
                chat_opened = False
                
                for check_attempt in range(5):  # Max 5 tentativi, 1.5s ciascuno = 7.5s totali
                    await asyncio.sleep(1.5)
                    
                    # Verifica 1: URL è cambiato (indica navigazione)
                    try:
                        url_after = self.driver.current_url
                        if url_after != url_before:
                            print(f"  URL cambiato (indica navigazione)")
                    except:
                        pass
                    
                    # Verifica 2: Header conversazione presente
                    try:
                        chat_header = self.driver.find_elements(By.CSS_SELECTOR, 
                            "[data-testid='conversation-header'], header[data-testid='conversation-header'], div[data-testid='conversation-header']")
                        if chat_header and any(h.is_displayed() for h in chat_header):
                            print(f"  Header conversazione trovato (tentativo {check_attempt + 1})")
                            chat_opened = True
                            break
                    except:
                        pass
                    
                    # Verifica 3: Footer con input box presente
                    try:
                        footer = self.driver.find_elements(By.CSS_SELECTOR, "footer")
                        if footer and any(f.is_displayed() for f in footer):
                            footer_inputs = footer[0].find_elements(By.CSS_SELECTOR, "[contenteditable='true']")
                            if footer_inputs:
                                print(f"  Footer con input trovato (tentativo {check_attempt + 1})")
                                chat_opened = True
                                break
                    except:
                        pass
                    
                    # Verifica 4: Pannello messaggi presente
                    try:
                        message_panel = self.driver.find_elements(By.CSS_SELECTOR, 
                            "[data-testid='conversation-panel-body'], div[data-testid='conversation-panel-messages'], div[role='application']")
                        if message_panel and any(p.is_displayed() for p in message_panel):
                            print(f"  Pannello messaggi trovato (tentativo {check_attempt + 1})")
                            chat_opened = True
                            break
                    except:
                        pass
                    
                    # Verifica 5: Input box direttamente
                    try:
                        test_input = await self._find_input_box()
                        if test_input and test_input.is_displayed():
                            print(f"  Input box trovato direttamente (tentativo {check_attempt + 1})")
                            chat_opened = True
                            break
                    except:
                        pass
                
                if not chat_opened:
                    print("  ❌ Chat NON aperta dopo il click!")
                    print("  💡 Il click potrebbe non aver funzionato correttamente")
                    print("  🔄 Riprovo con un nuovo tentativo di ricerca...")
                    # Riprova con la prossima variazione del nome
                    continue
                
                print("  Chat aperta e verificata!")
                await asyncio.sleep(1)  # Attesa finale per stabilità
                
                # IMPORTANTE: Abbiamo trovato il contatto corretto, NON cercare altre variazioni!
                # Prova a inviare il messaggio, anche con retry se necessario
                
                # 2. Trova input box con retry e diagnostica migliorata
                input_box = None
                
                # PRIMA: Chiudi eventuali popup/overlay che potrebbero bloccare
                try:
                    from selenium.webdriver.common.action_chains import ActionChains
                    # Premi ESC più volte per chiudere qualsiasi popup
                    actions = ActionChains(self.driver)
                    actions.send_keys(Keys.ESCAPE)
                    actions.send_keys(Keys.ESCAPE)
                    actions.perform()
                    await asyncio.sleep(0.5)
                except:
                    pass
                
                for attempt in range(3):
                    print(f"  🔍 Ricerca input box (tentativo {attempt + 1}/3)...")
                    
                    try:
                        input_box = await self._find_input_box()
                    except Exception as find_error:
                        print(f"  ⚠️  Errore ricerca: {str(find_error)[:100]}")
                        input_box = None
                    
                    if input_box:
                        print(f"  Input box trovata!")
                        
                        # Verifica che l'input box sia stabile (non in fase di rendering)
                        await asyncio.sleep(0.5)
                        
                        # Verifica che sia ancora presente e interagibile
                        try:
                            if input_box.is_displayed() and input_box.is_enabled():
                                print(f"  Input box verificata e pronta")
                                break
                            else:
                                print(f"  ⚠️  Input box non interagibile")
                                input_box = None
                        except Exception as verify_error:
                            print(f"  ⚠️  Errore verifica: {str(verify_error)[:50]}")
                            input_box = None
                    
                    if not input_box:
                        print(f"  ⚠️  Input box non trovata, diagnostica...")
                        
                        # Diagnostica: verifica lo stato della pagina
                        try:
                            current_url = self.driver.current_url
                            print(f"  📍 URL corrente: {current_url[:50]}...")
                            
                            # Verifica se ci sono popup o overlay
                            try:
                                overlays = self.driver.find_elements(By.CSS_SELECTOR, "div[role='dialog'], div.modal, div[data-testid='popup']")
                                if overlays:
                                    print(f"  ⚠️  Trovati {len(overlays)} popup/overlay, provo a chiuderli...")
                                    # Prova a chiudere con ESC
                                    from selenium.webdriver.common.action_chains import ActionChains
                                    actions = ActionChains(self.driver)
                                    actions.send_keys(Keys.ESCAPE)
                                    actions.perform()
                                    await asyncio.sleep(1)
                            except Exception as overlay_error:
                                print(f"  ⚠️  Errore chiusura popup: {str(overlay_error)[:50]}")
                            
                        except Exception as diag_error:
                            print(f"  ⚠️  Errore diagnostica: {str(diag_error)[:50]}")
                        
                        if attempt < 2:
                            print(f"  🔄 Riprovo tra 2 secondi...")
                            await asyncio.sleep(2)
                
                if not input_box:
                    print("  ❌ Impossibile trovare input box dopo 3 tentativi")
                    
                    # FALLBACK: Prova a ricaricare la pagina della chat
                    print("  🔄 Tentativo fallback: ricarico la chat...")
                    try:
                        # Ricarica la pagina WhatsApp
                        current_url = self.driver.current_url
                        self.driver.refresh()
                        await asyncio.sleep(3)
                        
                        # Riprova a trovare l'input box
                        print("  🔍 Nuovo tentativo ricerca input box...")
                        input_box = await self._find_input_box()
                        
                        if not input_box:
                            print("  ❌ Fallback non riuscito")
                            print("  💡 Suggerimenti:")
                            print("     - Verifica che la chat sia completamente caricata")
                            print("     - Chiudi eventuali popup o notifiche")
                            print("     - Verifica che il contatto esista")
                            print("     - Prova a usare il numero di telefono invece del nome")
                            self.stats['messages_failed'] += 1
                            return False
                        else:
                            print("  Input box trovata dopo fallback!")
                    except Exception as fallback_error:
                        print(f"  ❌ Errore fallback: {str(fallback_error)[:50]}")
                        self.stats['messages_failed'] += 1
                        return False
                
                # 3. INSERISCI TESTO SENZA DUPLICAZIONI con retry
                text_ok = False
                
                for attempt in range(3):
                    print(f"  ⌨️  Tentativo inserimento testo {attempt + 1}/3...")
                    
                    # IMPORTANTE: Ricarica SEMPRE l'input box prima di ogni tentativo
                    # per evitare di usare un elemento "stale" (ricreato da WhatsApp)
                    try:
                        print("  🔄 Ricarico input box per sicurezza...")
                        fresh_input_box = await self._find_input_box()
                        if not fresh_input_box:
                            print("  ❌ Input box non più disponibile")
                            if attempt < 2:
                                print("  Attendo 2 secondi e riprovo...")
                                await asyncio.sleep(2)
                                continue
                            else:
                                break
                        
                        # Usa l'input box fresco
                        input_box = fresh_input_box
                        
                        # Verifica che l'input box sia interagibile
                        try:
                            if not input_box.is_displayed() or not input_box.is_enabled():
                                print("  ⚠️  Input box non interagibile")
                                if attempt < 2:
                                    await asyncio.sleep(2)
                                    continue
                                else:
                                    break
                        except:
                            pass
                        
                        # Pulisci con Selenium (più affidabile per WhatsApp Web)
                        # Prima verifica se c'è già testo
                        try:
                            existing_text = input_box.text or input_box.get_attribute('innerText') or ''
                            if existing_text.strip():
                                print(f"  Rilevato testo esistente ({len(existing_text)} caratteri), pulisco...")
                                
                                # Metodo 1: CTRL+A + BACKSPACE (più affidabile)
                                input_box.click()
                                await asyncio.sleep(0.2)
                                input_box.send_keys(Keys.CONTROL + "a")
                                await asyncio.sleep(0.1)
                                input_box.send_keys(Keys.BACKSPACE)
                                await asyncio.sleep(0.3)
                                
                                # Verifica se la pulizia ha funzionato
                                after_clear = input_box.text or input_box.get_attribute('innerText') or ''
                                if after_clear.strip():
                                    # Se ancora c'è testo, prova di nuovo
                                    print(f"  🔄 Primo tentativo non ha pulito tutto, riprovo...")
                                    input_box.send_keys(Keys.CONTROL + "a")
                                    await asyncio.sleep(0.1)
                                    input_box.send_keys(Keys.DELETE)
                                    await asyncio.sleep(0.3)
                                    
                                    # Ultimo tentativo: cancella carattere per carattere (fallback)
                                    final_check = input_box.text or input_box.get_attribute('innerText') or ''
                                    if final_check.strip():
                                        print(f"  ⚠️  Ancora {len(final_check)} caratteri, provo pulizia JS...")
                                        js_clear = """
                                        const el = arguments[0];
                                        el.innerHTML = '';
                                        el.textContent = '';
                                        while(el.firstChild) el.removeChild(el.firstChild);
                                        """
                                        self.driver.execute_script(js_clear, input_box)
                                        await asyncio.sleep(0.3)
                                
                                print(f"  Input pulito")
                        except Exception as clear_err:
                            print(f"  ⚠️  Errore pulizia: {clear_err}")
                        
                    except Exception as clear_error:
                        print(f"  ⚠️  Errore pulizia: {clear_error}")
                    
                    # Inserisci il testo
                    text_ok = await self.message_sender.insert_text_no_duplicate(
                        self.driver, input_box, message
                    )
                    
                    if text_ok:
                        # Verifica finale che il testo sia corretto (non duplicato!)
                        try:
                            final_check = input_box.text or input_box.get_attribute('innerText') or ''
                            final_len = len(final_check.strip())
                            expected_len = len(message)
                            
                            # Il testo è OK se è nella range corretta (80%-120%)
                            # MA NON se è troppo lungo (potrebbe essere duplicato)
                            if final_len >= expected_len * 0.8 and final_len <= expected_len * 1.3:
                                print(f"  Verifica finale OK: {final_len} caratteri (atteso: {expected_len})")
                                break
                            else:
                                print(f"  ⚠️  Verifica finale fallita: {final_len} caratteri (atteso: {expected_len})")
                                if final_len > expected_len * 1.5:
                                    print(f"  🔄 Testo probabilmente duplicato, pulisco e riprovo...")
                                text_ok = False
                        except:
                            # Se non possiamo verificare, assumiamo che sia OK
                            break
                    
                    if text_ok:
                        break
                    
                    if attempt < 2:
                        print(f"  ⚠️  Inserimento fallito, riprovo...")
                        await asyncio.sleep(1.5)
                
                if not text_ok:
                    print("  ❌ Impossibile inserire testo dopo 3 tentativi")
                    print("  💡 Suggerimento: Verifica che la chat sia aperta e l'input sia disponibile")
                    self.stats['messages_failed'] += 1
                    return False
                
                # Verifica finale prima di inviare
                await asyncio.sleep(0.5)
                try:
                    final_text_check = input_box.text or input_box.get_attribute('innerText') or ''
                    if len(final_text_check.strip()) < len(message) * 0.8:
                        print(f"  ⚠️  Testo non completo prima dell'invio: {len(final_text_check)}/{len(message)} caratteri")
                        print("  ❌ Invio annullato per evitare messaggio incompleto")
                        self.stats['messages_failed'] += 1
                        return False
                except:
                    pass
                
                # 4. Invia con retry (SOLO UNA VOLTA se il testo è corretto)
                sent_successfully = False
                
                # IMPORTANTE: Ricarica l'input box prima di inviare (potrebbe essere stale)
                try:
                    print("  🔄 Ricarico input box prima dell'invio...")
                    final_input_box = await self._find_input_box()
                    if final_input_box:
                        input_box = final_input_box
                    else:
                        print("  ⚠️  Input box non più disponibile, uso quello precedente")
                except:
                    print("  ⚠️  Errore ricaricamento input box, uso quello precedente")
                
                for attempt in range(2):  # Massimo 2 tentativi per evitare duplicazioni
                    try:
                        # Verifica che il testo sia ancora presente
                        verify_text = input_box.text or input_box.get_attribute('innerText') or input_box.get_attribute('textContent') or ''
                        if not verify_text.strip():
                            print("  ⚠️  Testo scomparso prima dell'invio, riprovo inserimento...")
                            # Riprova inserimento una volta
                            if attempt == 0:
                                try:
                                    input_box.click()
                                    await asyncio.sleep(0.3)
                                    input_box.send_keys(message)
                                    await asyncio.sleep(0.5)
                                    verify_text = input_box.text or input_box.get_attribute('innerText') or ''
                                except:
                                    pass
                            
                            if not verify_text.strip():
                                print("  ❌ Impossibile recuperare testo per invio")
                                break
                        
                        print(f"  📤 Invio messaggio ({len(verify_text)} caratteri)...")
                        
                        # Focus sull'input
                        input_box.click()
                        await asyncio.sleep(0.2)
                        
                        # Strategia 1: ENTER key (più affidabile)
                        input_box.send_keys(Keys.ENTER)
                        await asyncio.sleep(2.5)  # Attesa invio
                        
                        # Verifica che il messaggio sia stato inviato (l'input dovrebbe essere vuoto)
                        try:
                            after_send = input_box.text or input_box.get_attribute('innerText') or input_box.get_attribute('textContent') or ''
                            after_len = len(after_send.strip())
                            before_len = len(verify_text.strip())
                            
                            if after_len < before_len * 0.3:  # Almeno 70% del testo è stato rimosso
                                print("Messaggio inviato con ENTER!")
                                self.stats['messages_sent'] += 1
                                sent_successfully = True
                                break
                            else:
                                print(f"  ⚠️  Testo ancora presente dopo ENTER ({after_len}/{before_len} caratteri)")
                                # Prova con pulsante send
                                if attempt == 0:
                                    raise Exception("ENTER non ha funzionato, provo pulsante")
                        except Exception as verify_error:
                            # Se la verifica fallisce o ENTER non ha funzionato, prova pulsante
                            if attempt == 0:
                                print("  🔹 Tentativo con pulsante Send...")
                                try:
                                    send_selectors = [
                                        "[data-testid='send']",
                                        "button[aria-label='Invia']",
                                        "button[aria-label='Send']",
                                        "span[data-icon='send']",
                                        "button[data-tab='11']"
                                    ]
                                    
                                    send_btn = None
                                    for sel in send_selectors:
                                        try:
                                            send_btn = WebDriverWait(self.driver, 2).until(
                                                EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                                            )
                                            if send_btn.is_displayed():
                                                break
                                        except:
                                            continue
                                    
                                    if send_btn:
                                        if self.clicker:
                                            click_ok = await self.clicker.click_element(send_btn, "pulsante Send")
                                            if click_ok:
                                                await asyncio.sleep(2.5)
                                                print("Messaggio inviato con pulsante Send!")
                                                self.stats['messages_sent'] += 1
                                                sent_successfully = True
                                                break
                                        else:
                                            send_btn.click()
                                            await asyncio.sleep(2.5)
                                            print("Messaggio inviato con pulsante Send!")
                                            self.stats['messages_sent'] += 1
                                            sent_successfully = True
                                            break
                                    else:
                                        print("  ⚠️  Pulsante Send non trovato")
                                except Exception as btn_error:
                                    print(f"  ⚠️  Click pulsante fallito: {str(btn_error)[:80]}")
                            
                            # Se non possiamo verificare, assumiamo che sia stato inviato dopo ENTER
                            if not sent_successfully:
                                print("Messaggio presumibilmente inviato (verifica non disponibile)")
                                self.stats['messages_sent'] += 1
                                sent_successfully = True
                                break
                            
                    except Exception as send_error:
                        print(f"  ⚠️  Errore invio: {str(send_error)[:80]}")
                        if attempt < 1:
                            await asyncio.sleep(2)
                            continue
                
                if not sent_successfully:
                    print("  ❌ Impossibile inviare messaggio dopo i tentativi")
                    self.stats['messages_failed'] += 1
                    return False
                
                return True
            
            print("Contatto non trovato")
            self.stats['messages_failed'] += 1
            return False
            
        except Exception as e:
            print(f"Errore: {e}")
            self.stats['messages_failed'] += 1
            return False
    
    # Helper methods
    def _driver_is_alive(self) -> bool:
        """Verifica se il driver Selenium è ancora valido"""
        if not self.driver:
            return False
        try:
            _ = self.driver.current_url
            return True
        except Exception:
            return False
    
    def _safe_close_driver(self) -> None:
        """Chiude il driver in sicurezza e resetta lo stato"""
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass
        finally:
            self.driver = None
            self.is_connected = False
    
    def _check_authenticated(self) -> bool:
        """Verifica se WhatsApp è autenticato usando più metodi"""
        if not self.driver:
            return False
        
        driver = self.driver
        
        try:
            driver.implicitly_wait(1)
            
            selectors = [
                "[data-testid='chat-list']",
                "[data-testid='chat']",
                "div[role='grid']",
                "#pane-side",
                "div._2Ts6I",
                "div[data-testid='conversation-list']"
            ]
            for selector in selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        for element in elements[:3]:
                            try:
                                if element.is_displayed():
                                    driver.implicitly_wait(10)
                                    return True
                            except Exception:
                                continue
                except Exception:
                    continue
            
            try:
                qr_selectors = [
                    "canvas[aria-label*='QR']",
                    "div[data-ref]",
                    "div._2EZ_m",
                    "div[data-ref*='qr']"
                ]
                qr_found = False
                for selector in qr_selectors:
                    try:
                        qr_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for qr_element in qr_elements[:2]:
                            try:
                                if qr_element.is_displayed():
                                    qr_found = True
                                    break
                            except Exception:
                                continue
                        if qr_found:
                            break
                    except Exception:
                        continue
                
                if qr_found:
                    driver.implicitly_wait(10)
                    return False
            except Exception:
                pass
            
            try:
                current_url = driver.current_url
                if "web.whatsapp.com" in current_url:
                    if "qr" not in current_url.lower():
                        try:
                            page_source = driver.page_source.lower()[:5000]
                            if "chat" in page_source or "conversation" in page_source:
                                if "qr code" not in page_source and "scan" not in page_source:
                                    driver.implicitly_wait(10)
                                    return True
                        except Exception:
                            pass
            except Exception:
                pass
            
            driver.implicitly_wait(10)
            return False
        except Exception:
            try:
                driver.implicitly_wait(10)
            except Exception:
                pass
            return False
    
    async def _find_search_box(self):
        """Trova casella ricerca con timeout ridotto"""
        selectors = [
            "[data-testid='chat-list-search']",
            "div[contenteditable='true'][data-tab='3']"
        ]
        for sel in selectors:
            try:
                return WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                )
            except:
                continue
        return None
    
    async def _clear_search_box(self, search_box):
        """Pulisce correttamente la barra di ricerca WhatsApp"""
        try:
            # Metodo 1: Chiudi eventuali risultati aperti con ESC
            try:
                search_box.send_keys(Keys.ESCAPE)
                await asyncio.sleep(0.2)
            except:
                pass
            
            # Metodo 2: Clicca e seleziona tutto con Ctrl+A
            try:
                search_box.click()
                await asyncio.sleep(0.2)
                # Seleziona tutto il testo più volte per sicurezza
                search_box.send_keys(Keys.CONTROL + "a")
                await asyncio.sleep(0.1)
                search_box.send_keys(Keys.CONTROL + "a")
                await asyncio.sleep(0.1)
                # Cancella con BACKSPACE e DELETE
                search_box.send_keys(Keys.BACKSPACE)
                search_box.send_keys(Keys.DELETE)
                await asyncio.sleep(0.2)
            except Exception as e:
                print(f"  ⚠️  Errore pulizia con tastiera: {e}")
            
            # Metodo 3: Usa JavaScript per pulire completamente
            js_clear = """
            const element = arguments[0];
            
            // Focus sull'elemento
            element.focus();
            
            // Seleziona tutto il contenuto
            if (window.getSelection && document.createRange) {
                const range = document.createRange();
                range.selectNodeContents(element);
                const sel = window.getSelection();
                sel.removeAllRanges();
                sel.addRange(range);
            }
            
            // Usa execCommand per cancellare
            if (document.execCommand) {
                document.execCommand('selectAll', false, null);
                document.execCommand('delete', false, null);
                document.execCommand('delete', false, null); // Doppio per sicurezza
            }
            
            // Pulisci anche innerHTML e textContent
            element.innerHTML = '';
            element.textContent = '';
            
            // Rimuovi anche eventuali span o altri elementi figli
            while (element.firstChild) {
                element.removeChild(element.firstChild);
            }
            
            // Trigger eventi per notificare WhatsApp
            const inputEvent = new Event('input', { bubbles: true });
            const changeEvent = new Event('change', { bubbles: true });
            element.dispatchEvent(inputEvent);
            element.dispatchEvent(changeEvent);
            
            // Verifica che sia vuoto
            const isEmpty = !element.innerText && !element.textContent && element.innerHTML === '';
            return isEmpty;
            """
            
            result = self.driver.execute_script(js_clear, search_box)
            await asyncio.sleep(0.4)  # Attesa per il rendering
            
            # Verifica finale: se non è vuoto, riprova
            try:
                current_text = search_box.text or search_box.get_attribute('innerText') or ''
                if current_text.strip():
                    print(f"  🔄 Testo residuo trovato, ripulitura...")
                    # Riprova con metodo più aggressivo
                    search_box.click()
                    await asyncio.sleep(0.2)
                    for _ in range(3):  # Prova 3 volte
                        search_box.send_keys(Keys.CONTROL + "a")
                        search_box.send_keys(Keys.BACKSPACE)
                        await asyncio.sleep(0.1)
                    # Pulisci anche con JavaScript finale
                    self.driver.execute_script("arguments[0].innerHTML = ''; arguments[0].textContent = '';", search_box)
                    await asyncio.sleep(0.3)
            except:
                pass
                
        except Exception as e:
            print(f"  ⚠️  Errore pulizia barra ricerca: {e}")
            # Fallback finale: prova con metodi standard
            try:
                search_box.click()
                await asyncio.sleep(0.2)
                for _ in range(5):  # Prova più volte
                    search_box.send_keys(Keys.CONTROL + "a")
                    search_box.send_keys(Keys.BACKSPACE)
                    await asyncio.sleep(0.1)
            except:
                pass
    
    async def _find_first_chat_result(self):
        """Trova primo risultato ricerca"""
        try:
            return WebDriverWait(self.driver, 8).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='cell-frame-container']"))
            )
        except:
            return None
    
    async def _find_matching_chat_result(self, original_name: str, search_term: str):
        """
        Trova il risultato della ricerca che corrisponde al contatto cercato.
        Verifica il nome del contatto prima di selezionarlo.
        
        Returns:
            Dict con 'element' e 'name' se trovato, None altrimenti
        """
        try:
            # Attendi che i risultati appaiano
            await asyncio.sleep(2)
            
            # Trova tutti i risultati della ricerca usando selettori Selenium
            result_selectors = [
                "[data-testid='cell-frame-container']",
                "div[role='row']",
                "div[data-testid='chat']",
                "div._8nE1Y",
                "div[role='grid'] > div[role='row']"
            ]
            
            results = []
            for selector in result_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        # Filtra solo gli elementi visibili e che hanno contenuto
                        visible_elements = []
                        for elem in elements[:15]:  # Controlla fino a 15 elementi
                            try:
                                if elem.is_displayed():
                                    # Verifica che abbia contenuto (nome del contatto)
                                    text = elem.text or elem.get_attribute('innerText') or ''
                                    if text.strip():
                                        visible_elements.append(elem)
                            except:
                                continue
                        
                        if visible_elements:
                            results = visible_elements[:10]  # Limita a primi 10 risultati
                            print(f"  Trovati {len(results)} risultati con selettore: {selector}")
                            break
                except Exception as sel_error:
                    continue
            
            if not results:
                print(f"  ⚠️  Nessun risultato trovato nella ricerca")
                return None
            
            print(f"  Trovati {len(results)} risultati da analizzare")
            
            # Normalizza il nome originale per il confronto
            original_normalized = self._normalize_name(original_name)
            search_normalized = self._normalize_name(search_term)
            
            # Cerca il risultato che corrisponde
            for result_element in results:
                try:
                    # Estrai il nome del contatto dal risultato usando JavaScript (più affidabile)
                    # Basato sulla struttura HTML di WhatsApp: <span title="Nome">...</span>
                    try:
                        js_get_name = """
                        const elem = arguments[0];
                        
                        // Metodo 1: Cerca span con attributo title (più affidabile)
                        const spansWithTitle = elem.querySelectorAll('span[title]');
                        for (let span of spansWithTitle) {
                            const title = span.getAttribute('title');
                            if (title && title.trim()) {
                                return title.trim();
                            }
                        }
                        
                        // Metodo 2: Cerca span con classe matched-text
                        const matchedTextSpans = elem.querySelectorAll('span.matched-text, span._ao3e');
                        for (let span of matchedTextSpans) {
                            const text = span.textContent || span.innerText || '';
                            if (text.trim()) {
                                return text.trim();
                            }
                        }
                        
                        // Metodo 3: Cerca il primo span con testo significativo
                        const allSpans = elem.querySelectorAll('span');
                        for (let span of allSpans) {
                            const text = span.textContent || span.innerText || '';
                            const trimmed = text.trim();
                            // Prendi solo testo che sembra un nome (non troppo lungo, non solo numeri)
                            if (trimmed && trimmed.length > 0 && trimmed.length < 50 && 
                                !/^[0-9\\s\\-\\+]+$/.test(trimmed)) {
                                return trimmed;
                            }
                        }
                        
                        // Metodo 4: Fallback - tutto il testo dell'elemento
                        const fullText = elem.textContent || elem.innerText || '';
                        const trimmed = fullText.trim();
                        // Rimuovi caratteri di controllo e prendi la prima parte significativa
                        const cleaned = trimmed.split(/[\\n\\r\\t]/)[0].trim();
                        if (cleaned && cleaned.length < 50) {
                            return cleaned;
                        }
                        
                        return '';
                        """
                        contact_name = self.driver.execute_script(js_get_name, result_element)
                        contact_name = contact_name.strip() if contact_name else None
                        
                        # Debug: stampa il nome trovato
                        if contact_name:
                            print(f"  🔍 Nome estratto: '{contact_name}'")
                        
                    except Exception as js_error:
                        print(f"  ⚠️  Errore JavaScript estrazione nome: {js_error}")
                        contact_name = None
                    
                    # Fallback: prova con selettori Selenium se JavaScript fallisce
                    if not contact_name:
                        name_selectors = [
                            "span[title]",
                            "span.matched-text",
                            "span._ao3e",
                            "span[dir='auto']",
                            "div[title]"
                        ]
                        
                        for name_sel in name_selectors:
                            try:
                                name_elements = result_element.find_elements(By.CSS_SELECTOR, name_sel)
                                for name_elem in name_elements:
                                    # Prova a ottenere il nome da title o text
                                    name_text = name_elem.get_attribute('title') or name_elem.text or name_elem.get_attribute('innerText') or ''
                                    if name_text.strip() and len(name_text.strip()) < 50:
                                        contact_name = name_text.strip()
                                        print(f"  🔍 Nome estratto (fallback): '{contact_name}'")
                                        break
                                if contact_name:
                                    break
                            except:
                                continue
                    
                    if not contact_name:
                        continue
                    
                    # Normalizza il nome trovato
                    found_normalized = self._normalize_name(contact_name)
                    
                    # Debug: mostra i nomi confrontati
                    print(f"  🔍 Confronto: '{contact_name}' (normalizzato: '{found_normalized}') vs '{original_name}' (normalizzato: '{original_normalized}')")
                    
                    # Verifica corrispondenza
                    if self._names_match(original_normalized, found_normalized, search_normalized):
                        print(f"  Corrispondenza trovata: '{contact_name}' (cercato: '{original_name}')")
                        return {
                            'element': result_element,
                            'name': contact_name
                        }
                    else:
                        print(f"  ⚠️  Nessuna corrispondenza: '{contact_name}' non corrisponde a '{original_name}'")
                    
                except Exception as e:
                    # Continua con il prossimo risultato se c'è un errore
                    print(f"  ⚠️  Errore processando risultato: {e}")
                    continue
            
            # Nessun risultato corrispondente trovato
            print(f"  ❌ Nessun risultato corrispondente trovato tra {len(results)} risultati")
            return None
            
        except Exception as e:
            print(f"  ⚠️  Errore nella ricerca del contatto: {e}")
            return None
    
    def _normalize_name(self, name: str) -> str:
        """Normalizza un nome per il confronto (lowercase, rimuove spazi extra)"""
        if not name:
            return ""
        return " ".join(name.lower().split())
    
    def _names_match(self, original: str, found: str, search_term: str) -> bool:
        """
        Verifica se due nomi corrispondono.
        Considera corrispondenze parziali e variazioni comuni.
        """
        if not original or not found:
            return False
        
        # Corrispondenza esatta
        if original == found:
            return True
        
        # Verifica corrispondenza diretta (contiene)
        if found in original or original in found:
            return True
        
        # Verifica se il nome trovato contiene tutte le parole del nome originale
        original_words = set(original.split())
        found_words = set(found.split())
        
        # Se tutte le parole del nome originale sono nel nome trovato
        if original_words.issubset(found_words):
            return True
        
        # Se tutte le parole del nome trovato sono nel nome originale
        if found_words.issubset(original_words):
            return True
        
        # Verifica corrispondenza con il termine di ricerca (caso più importante!)
        if search_term:
            search_normalized = search_term.lower().strip()
            found_lower = found.lower()
            original_lower = original.lower()
            
            # Se il termine di ricerca corrisponde esattamente al nome trovato
            if search_normalized == found_lower:
                return True
            
            # Se il termine di ricerca è contenuto nel nome trovato
            if search_normalized in found_lower:
                return True
            
            # Se il nome trovato è contenuto nel termine di ricerca
            if found_lower in search_normalized:
                return True
            
            # Verifica corrispondenza parziale: almeno una parola del termine di ricerca nel nome trovato
            search_words = set(search_normalized.split())
            if search_words.intersection(found_words):
                # Se almeno una parola corrisponde e il nome trovato non è troppo lungo
                if len(found_words) <= len(search_words) + 1:  # Permette una parola extra
                    return True
        
        # Verifica corrispondenza inversa: se il nome trovato è simile al nome originale
        # (almeno 70% delle parole corrispondono)
        if len(original_words) > 0:
            matching_words = original_words.intersection(found_words)
            match_ratio = len(matching_words) / len(original_words)
            if match_ratio >= 0.7:
                return True
        
        # Verifica corrispondenza per inizio del nome (es: "Simo" corrisponde a "Simone")
        if len(found) >= 3 and len(original) >= len(found):
            if original.lower().startswith(found.lower()):
                return True
            if found.lower().startswith(original.lower()):
                return True
        
        return False
    
    async def _wait_for_chat_to_load(self, max_wait: int = 5) -> bool:
        """
        Attende che la chat sia completamente caricata e stabile.
        
        Args:
            max_wait: Tempo massimo di attesa in secondi (ridotto a 5)
            
        Returns:
            True se la chat è caricata
        """
        try:
            # Attendi che ci sia almeno un'area messaggi visibile
            for attempt in range(max_wait * 2):  # Check ogni 0.5s
                try:
                    # Cerca elementi che indicano che la chat è caricata
                    chat_indicators = [
                        "[data-testid='conversation-panel-body']",
                        "div[data-testid='conversation-panel-messages']",
                        "div.copyable-area",
                        "div[role='application']",
                        "footer"  # Il footer contiene l'input box
                    ]
                    
                    for indicator in chat_indicators:
                        try:
                            elements = self.driver.find_elements(By.CSS_SELECTOR, indicator)
                            if elements and any(e.is_displayed() for e in elements):
                                # Trovato indicatore, attendi un attimo per stabilità
                                await asyncio.sleep(0.5)
                                return True
                        except:
                            continue
                    
                    # Non trovato, attendi e riprova
                    await asyncio.sleep(0.5)
                        
                except Exception as e:
                    if attempt >= max_wait * 2 - 1:
                        print(f"  ⚠️  Timeout attesa caricamento: {str(e)[:50]}")
                    await asyncio.sleep(0.5)
                    continue
            
            # Timeout ma non è critico
            return False
            
        except Exception as e:
            print(f"  ⚠️  Errore verifica caricamento: {str(e)[:50]}")
            return False
    
    async def _find_input_box(self):
        """Trova input box messaggio con selettori multipli e diagnostica"""
        selectors = [
            "[data-testid='conversation-compose-box-input']",
            "div[contenteditable='true'][data-tab='10']",
            "footer div[contenteditable='true']",
            "div[contenteditable='true'][role='textbox']",
            "div._3Uu1_ div[contenteditable='true']",
            "div[data-tab='10']",
            "footer div[role='textbox']"
        ]
        
        # Primo tentativo: con attesa RIDOTTA (2 secondi invece di 5)
        for idx, sel in enumerate(selectors):
            try:
                box = WebDriverWait(self.driver, 2).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                )
                if box.is_displayed() and box.is_enabled():
                    print(f"  Input box trovata con selettore #{idx+1}: {sel[:40]}...")
                    return box
            except:
                continue
        
        # Secondo tentativo: ricerca JavaScript
        print("  🔍 Tentativo ricerca input box con JavaScript...")
        try:
            js_find_input = """
            // Cerca input box con JavaScript
            const selectors = [
                '[data-testid="conversation-compose-box-input"]',
                'div[contenteditable="true"][data-tab="10"]',
                'footer div[contenteditable="true"]',
                'div[contenteditable="true"][role="textbox"]',
                'div[data-tab="10"]'
            ];
            
            for (let sel of selectors) {
                const elements = document.querySelectorAll(sel);
                for (let elem of elements) {
                    if (elem.offsetParent !== null && elem.contentEditable === 'true') {
                        return elem;
                    }
                }
            }
            
            // Fallback: cerca qualsiasi elemento contenteditable nel footer
            const footer = document.querySelector('footer');
            if (footer) {
                const editables = footer.querySelectorAll('[contenteditable="true"]');
                for (let elem of editables) {
                    if (elem.offsetParent !== null) {
                        return elem;
                    }
                }
            }
            
            return null;
            """
            
            element = self.driver.execute_script(js_find_input)
            if element:
                print("  Input box trovata con JavaScript!")
                return element
        except Exception as js_error:
            print(f"  ⚠️  Ricerca JavaScript fallita: {js_error}")
        
        # Terzo tentativo: cerca QUALSIASI elemento contenteditable visibile
        print("  🔍 Tentativo ricerca elementi contenteditable generici...")
        try:
            all_editables = self.driver.find_elements(By.CSS_SELECTOR, "div[contenteditable='true']")
            print(f"  📊 Trovati {len(all_editables)} elementi contenteditable")
            
            for elem in all_editables:
                try:
                    if elem.is_displayed() and elem.is_enabled():
                        # Verifica che sia nel footer (più probabile che sia l'input giusto)
                        parent_html = elem.get_attribute('outerHTML')[:100]
                        if 'footer' in parent_html.lower() or 'compose' in parent_html.lower():
                            print("  Input box trovata (contenteditable generico)!")
                            return elem
                except:
                    continue
        except Exception as e:
            print(f"  ⚠️  Ricerca generica fallita: {e}")
        
        print("  ❌ Nessun input box trovato con nessun metodo")
        return None
    
    def _generate_name_variations(self, name: str) -> List[str]:
        """Genera variazioni del nome per la ricerca"""
        variations = [name]
        # Aggiungi variazioni comuni
        if ' ' in name:
            parts = name.split()
            variations.append(parts[0])  # Solo nome
            variations.append(parts[-1])  # Solo cognome
        variations.append(name.lower())
        variations.append(name.title())
        return variations
    
    async def initialize(self) -> bool:
        """Inizializza il client WhatsApp Web"""
        try:
            if self.driver:
                if not self._driver_is_alive():
                    print("  ⚠️  Sessione precedente non più valida, la chiudo...")
                    self._safe_close_driver()
                else:
                    if self._check_authenticated():
                        self.is_connected = True
                        print("  🔁 WhatsApp già inizializzato, riutilizzo il browser aperto")
                        return True
                    
                    print("  🔄 Browser aperto ma non autenticato, aggiorno la pagina...")
                    try:
                        self.driver.get("https://web.whatsapp.com")
                        await asyncio.sleep(3)
                        if self._check_authenticated():
                            self.is_connected = True
                            print("  Sessione esistente autenticata correttamente")
                            return True
                    except Exception as reuse_error:
                        print(f"  ⚠️  Riutilizzo sessione fallito: {reuse_error}")
                    
                    print("  ♻️  Riavvio completo della sessione WhatsApp...")
                    self._safe_close_driver()
            
            print("  Configurazione Chrome...")
            chrome_options = Options()
            
            # Opzioni base per stabilità
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--remote-debugging-port=9222")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # Sopprimi errori e warning Google APIs
            chrome_options.add_argument("--disable-logging")
            chrome_options.add_argument("--log-level=3")  # Solo errori fatali
            chrome_options.add_argument("--disable-background-networking")
            chrome_options.add_argument("--disable-background-timer-throttling")
            chrome_options.add_argument("--disable-backgrounding-occluded-windows")
            chrome_options.add_argument("--disable-breakpad")
            chrome_options.add_argument("--disable-client-side-phishing-detection")
            chrome_options.add_argument("--disable-component-update")
            chrome_options.add_argument("--disable-default-apps")
            chrome_options.add_argument("--disable-domain-reliability")
            chrome_options.add_argument("--disable-features=TranslateUI")
            chrome_options.add_argument("--disable-hang-monitor")
            chrome_options.add_argument("--disable-ipc-flooding-protection")
            chrome_options.add_argument("--disable-popup-blocking")
            chrome_options.add_argument("--disable-prompt-on-repost")
            chrome_options.add_argument("--disable-renderer-backgrounding")
            chrome_options.add_argument("--disable-sync")
            chrome_options.add_argument("--disable-translate")
            chrome_options.add_argument("--metrics-recording-only")
            chrome_options.add_argument("--no-first-run")
            chrome_options.add_argument("--safebrowsing-disable-auto-update")
            chrome_options.add_argument("--enable-automation")
            chrome_options.add_argument("--password-store=basic")
            chrome_options.add_argument("--use-mock-keychain")
            
            # Opzioni sperimentali
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_experimental_option("detach", True)  # Mantiene il browser aperto
            
            # Preferenze per evitare crash
            prefs = {
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_settings.popups": 0,
                "profile.managed_default_content_settings.images": 2
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # User data dir per sessione persistente - usa percorso assoluto
            try:
                user_data_dir = os.path.abspath(os.path.join(self.session_path, "whatsapp_session"))
                Path(user_data_dir).mkdir(parents=True, exist_ok=True)
                chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
                print(f"  Sessione salvata in: {user_data_dir}")
            except Exception as dir_error:
                print(f"  ⚠️  Errore creazione directory sessione: {dir_error}")
                # Continua senza user-data-dir se c'è un problema
                # (la sessione non sarà persistente ma almeno funziona)
            
            print("  Avvio browser...")
            try:
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                print("  Browser avviato con successo!")
            except Exception as driver_error:
                print(f"  ❌ Errore avvio ChromeDriver: {driver_error}")
                # Prova senza user-data-dir come fallback
                if "--user-data-dir" in str(chrome_options.arguments):
                    print("  🔄 Tentativo senza user-data-dir...")
                    chrome_options_fallback = Options()
                    chrome_options_fallback.add_argument("--no-sandbox")
                    chrome_options_fallback.add_argument("--disable-dev-shm-usage")
                    chrome_options_fallback.add_argument("--disable-blink-features=AutomationControlled")
                    chrome_options_fallback.add_experimental_option("excludeSwitches", ["enable-automation"])
                    chrome_options_fallback.add_experimental_option('useAutomationExtension', False)
                    service = Service(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=chrome_options_fallback)
                    print("  Browser avviato (modalità fallback)")
            
            # Inizializza il clicker dopo che il driver è disponibile
            if self.driver:
                self.clicker = WhatsAppClicker(self.driver)
            
            self.stats['connections_attempted'] += 1
            
            print("  Caricamento WhatsApp Web...")
            self.driver.get("https://web.whatsapp.com")
            
            print("  Attendo autenticazione WhatsApp...")
            # Attendi che WhatsApp sia caricato
            await asyncio.sleep(5)
            
            # Controlla se è già autenticato
            if self._check_authenticated():
                self.is_connected = True
                print("  WhatsApp già autenticato!")
                self.stats['connections_successful'] += 1
                return True
            
            # Non è autenticato, mostra QR code
            print("  📱 Scansiona il QR code con WhatsApp (hai 5 minuti)")
            print("  Il QR code è visibile nella finestra del browser")
            print("  In attesa della scansione...")
            
            # Attendi autenticazione con controllo periodico
            max_wait = min(self.qr_timeout, 300)  # Max 5 minuti
            start_time = time.time()
            check_count = 0
            last_error = None
            
            while (time.time() - start_time) < max_wait:
                try:
                    await asyncio.sleep(2)
                    check_count += 1
                    
                    # Mostra progresso ogni 10 controlli (20 secondi)
                    if check_count % 10 == 0:
                        elapsed = int(time.time() - start_time)
                        remaining = max(0, max_wait - elapsed)
                        print(f"  Ancora in attesa... ({elapsed}s trascorsi, {remaining}s rimanenti)")
                    
                    # Verifica che il driver sia ancora valido
                    try:
                        # Test semplice: verifica che il driver risponda
                        _ = self.driver.current_url
                    except Exception as driver_error:
                        print(f"  ⚠️  Driver non più valido: {driver_error}")
                        raise Exception("Driver perso durante l'attesa")
                    
                    # Verifica autenticazione con timeout
                    try:
                        if self._check_authenticated():
                            self.is_connected = True
                            print("  Autenticazione completata!")
                            self.stats['connections_successful'] += 1
                            return True
                    except Exception as check_error:
                        # Salva l'ultimo errore ma continua
                        last_error = str(check_error)
                        # Non stampare ogni errore per evitare spam
                        if check_count % 20 == 0:  # Ogni 40 secondi
                            print(f"  ⚠️  Errore controllo autenticazione (continua...): {last_error[:50]}")
                        continue
                        
                except KeyboardInterrupt:
                    print("\n  ⏹️  Interrotto dall'utente")
                    return False
                except Exception as loop_error:
                    print(f"  ❌ Errore nel loop di attesa: {loop_error}")
                    # Se l'errore persiste, esci
                    if "Driver perso" in str(loop_error):
                        return False
                    # Altrimenti continua
                    await asyncio.sleep(5)
                    continue
            
            print("  ❌ Timeout autenticazione - QR code non scansionato entro il tempo limite")
            if last_error:
                print(f"  📋 Ultimo errore rilevato: {last_error[:100]}")
            print("  💡 Suggerimento: Assicurati di aver scansionato il QR code con WhatsApp")
            return False
                    
        except Exception as e:
            print(f"  ❌ Errore inizializzazione: {e}")
            import traceback
            print(f"  📋 Dettagli errore:\n{traceback.format_exc()}")
            self._safe_close_driver()
            return False
    
    async def wait_for_message(self, timeout: int = 300) -> Optional[str]:
        """
        Attende un messaggio in arrivo monitorando la chat WhatsApp.
        
        Args:
            timeout: Tempo massimo di attesa in secondi
            
        Returns:
            Testo del messaggio ricevuto o None se timeout
        """
        if not self.is_connected or not self.driver:
            print("  ⚠️  WhatsApp non connesso")
            return None
        
        try:
            print("  👀 Monitoraggio messaggi in arrivo...")
            
            # Prima estrazione (con debug)
            initial_messages = await self._get_chat_messages_simple(verbose=True)
            
            # Fallback al metodo JavaScript se il semplice non funziona
            if not initial_messages:
                print("  ⚠️  Metodo semplice fallito, provo con JavaScript...")
                initial_messages = await self._get_chat_messages()
            initial_count = len(initial_messages)
            
            # Salva il testo dell'ultimo messaggio per confronto
            last_message_text = initial_messages[-1].get('text', '') if initial_messages else ''
            
            print(f"  📊 Messaggi iniziali nella chat: {initial_count}")
            print(f"  📝 Ultimo messaggio: '{last_message_text[:50]}...'")
            
            # DEBUG: Mostra gli ultimi 3 messaggi con il loro stato
            if initial_messages:
                print("  🔍 Debug - Ultimi 3 messaggi:")
                for msg in initial_messages[-3:]:
                    is_recv = "📨 RICEVUTO" if msg.get('is_received') else "📤 INVIATO"
                    print(f"     {is_recv}: {msg.get('text', '')[:30]}...")
            
            # Monitora per il timeout specificato
            start_time = time.time()
            check_interval = 0.5  # Controlla ogni 0.5 secondi (ULTRA VELOCE)
            last_check_time = start_time
            checks_done = 0
            
            while (time.time() - start_time) < timeout:
                await asyncio.sleep(check_interval)
                checks_done += 1
                
                # Ottieni i messaggi attuali (VELOCE - senza debug)
                current_messages = await self._get_chat_messages_simple(verbose=False)
                if not current_messages:
                    current_messages = await self._get_chat_messages()
                current_count = len(current_messages)
                
                # DEBUG ogni 15 check (15 secondi)
                if checks_done % 15 == 0:
                    print(f"  🔄 Check #{checks_done}: {current_count} messaggi")
                
                # METODO 1: Verifica se il conteggio è aumentato
                if current_count > initial_count:
                    new_messages = current_messages[initial_count:]
                    print(f"  🆕 Rilevati {len(new_messages)} nuovi messaggi (conteggio)!")
                    
                    # Mostra tutti i nuovi messaggi
                    for msg in new_messages:
                        is_recv = msg.get('is_received', False)
                        msg_text = msg.get('text', '').strip()
                        status = "📨 RICEVUTO" if is_recv else "📤 INVIATO"
                        print(f"     {status}: {msg_text[:50]}...")
                        
                        if is_recv and msg_text:
                            print(f"  Messaggio ricevuto: {msg_text[:100]}...")
                            return msg_text
                    
                    # Fallback: prendi l'ultimo
                    last_new_msg = new_messages[-1]
                    msg_text = last_new_msg.get('text', '').strip()
                    if msg_text and len(msg_text) > 2:
                        print(f"  Assumo ultimo messaggio sia ricevuto: {msg_text[:100]}...")
                        return msg_text
                    
                    initial_count = current_count
                    last_message_text = current_messages[-1].get('text', '') if current_messages else ''
                
                # METODO 2: Verifica se l'ultimo messaggio è cambiato (anche senza aumento conteggio)
                elif current_messages:
                    current_last_text = current_messages[-1].get('text', '')
                    
                    if current_last_text != last_message_text and current_last_text.strip():
                        print(f"  🆕 Ultimo messaggio cambiato (senza aumento conteggio)!")
                        print(f"     Prima: '{last_message_text[:30]}...'")
                        print(f"     Ora: '{current_last_text[:30]}...'")
                        
                        # Verifica se è ricevuto
                        is_recv = current_messages[-1].get('is_received', False)
                        status = "📨 RICEVUTO" if is_recv else "📤 INVIATO"
                        print(f"     {status}: {current_last_text[:50]}...")
                        
                        # Accetta qualsiasi messaggio diverso dall'ultimo
                        if len(current_last_text.strip()) > 2:
                            print(f"  Nuovo messaggio rilevato: {current_last_text[:100]}...")
                            return current_last_text.strip()
                        
                        last_message_text = current_last_text
                
                # Mostra progresso ogni 30 secondi
                elapsed = int(time.time() - start_time)
                if elapsed > 0 and elapsed % 30 == 0 and elapsed != last_check_time:
                    remaining = timeout - elapsed
                    print(f"  Ancora in attesa... ({elapsed}s trascorsi, {remaining}s rimanenti)")
                    last_check_time = elapsed
            
            print(f"  ⏱️  Timeout raggiunto ({timeout}s) - nessun messaggio ricevuto")
            return None
            
        except Exception as e:
            print(f"  ❌ Errore attesa messaggio: {e}")
            import traceback
            print(f"  📋 Dettagli: {traceback.format_exc()}")
            return None
    
    async def navigate_to_home(self) -> bool:
        """
        Naviga alla schermata principale di WhatsApp con la lista chat.
        
        Returns:
            True se navigazione riuscita
        """
        try:
            if not self.driver:
                return False
            
            # Verifica se siamo già sulla home
            current_url = self.driver.current_url
            if "web.whatsapp.com" in current_url and "send" not in current_url:
                # Premi ESC per chiudere eventuali chat aperte e tornare alla lista
                try:
                    from selenium.webdriver.common.action_chains import ActionChains
                    actions = ActionChains(self.driver)
                    actions.send_keys(Keys.ESCAPE)
                    actions.perform()
                    await asyncio.sleep(1)
                except:
                    pass
                return True
            
            # Altrimenti vai alla home
            self.driver.get("https://web.whatsapp.com")
            await asyncio.sleep(3)
            return True
            
        except Exception as e:
            print(f"  ⚠️  Errore navigazione home: {e}")
            return False
    
    async def get_available_chats(self, max_chats: int = 20) -> List[Dict[str, Any]]:
        """
        Ottiene la lista delle chat disponibili.
        
        Args:
            max_chats: Numero massimo di chat da recuperare
            
        Returns:
            Lista di dizionari con informazioni sulle chat disponibili
        """
        chats = []
        
        try:
            if not self.driver:
                print("  ⚠️  Driver non disponibile")
                return chats
            
            # Verifica che siamo nella pagina principale di WhatsApp
            try:
                current_url = self.driver.current_url
                if "web.whatsapp.com" not in current_url:
                    print("  ⚠️  Non sei su WhatsApp Web")
                    return chats
            except:
                pass
            
            # Attendi che la lista chat sia caricata
            print("  Attesa caricamento chat...")
            await asyncio.sleep(2)
            
            # JavaScript per estrarre informazioni sulle chat
            js_get_chats = """
            const chats = [];
            
            // Selettori per le chat WhatsApp
            const chatSelectors = [
                '[data-testid="cell-frame-container"]',
                'div[role="row"]',
                'div[data-testid="chat"]'
            ];
            
            let chatElements = [];
            for (let sel of chatSelectors) {
                const elems = document.querySelectorAll(sel);
                if (elems.length > 0) {
                    chatElements = Array.from(elems);
                    break;
                }
            }
            
            // Limita al numero massimo
            const maxChats = arguments[0] || 20;
            chatElements = chatElements.slice(0, maxChats);
            
            // Estrai informazioni da ogni chat
            chatElements.forEach((elem, index) => {
                try {
                    // Cerca il nome del contatto/gruppo
                    let chatName = '';
                    
                    // Metodo 1: span con attributo title
                    const spanWithTitle = elem.querySelector('span[title]');
                    if (spanWithTitle && spanWithTitle.getAttribute('title')) {
                        chatName = spanWithTitle.getAttribute('title').trim();
                    }
                    
                    // Metodo 2: span con testo
                    if (!chatName) {
                        const spans = elem.querySelectorAll('span');
                        for (let span of spans) {
                            const text = span.textContent || span.innerText || '';
                            if (text.trim() && text.length > 0 && text.length < 50) {
                                chatName = text.trim();
                                break;
                            }
                        }
                    }
                    
                    if (!chatName) {
                        return;
                    }
                    
                    // Cerca l'ultimo messaggio (opzionale)
                    let lastMessage = '';
                    const messageSpans = elem.querySelectorAll('span[dir="ltr"], span[dir="auto"]');
                    for (let span of messageSpans) {
                        const text = span.textContent || span.innerText || '';
                        if (text.trim() && text.length > 5 && text.length < 200) {
                            // Verifica che non sia il nome
                            if (text.trim() !== chatName) {
                                lastMessage = text.trim();
                                break;
                            }
                        }
                    }
                    
                    chats.push({
                        index: index,
                        name: chatName,
                        last_message: lastMessage.substring(0, 50),
                        element_id: `chat_${index}`
                    });
                } catch (e) {
                    // Ignora errori su singole chat
                }
            });
            
            return chats;
            """
            
            chats = self.driver.execute_script(js_get_chats, max_chats)
            
            if not chats:
                print("  ⚠️  JavaScript non ha trovato chat, provo con Selenium...")
                # Fallback: prova con selettori Selenium
                try:
                    # Prova diversi selettori
                    selectors_to_try = [
                        "[data-testid='cell-frame-container']",
                        "div[role='row']",
                        "div[data-testid='chat']",
                        "div._8nE1Y"
                    ]
                    
                    chat_elements = []
                    for selector in selectors_to_try:
                        try:
                            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            if elements:
                                print(f"  Trovati {len(elements)} elementi con selettore: {selector}")
                                chat_elements = elements
                                break
                        except:
                            continue
                    
                    if not chat_elements:
                        print("  ⚠️  Nessun elemento chat trovato con nessun selettore")
                        return []
                    
                    for idx, elem in enumerate(chat_elements[:max_chats]):
                        try:
                            # Cerca nome contatto con diversi selettori
                            name = None
                            name_selectors = [
                                "span[title]",
                                "span[dir='auto']",
                                "span.matched-text",
                                "span._ao3e"
                            ]
                            
                            for name_sel in name_selectors:
                                try:
                                    name_elem = elem.find_element(By.CSS_SELECTOR, name_sel)
                                    if name_elem:
                                        # Prova prima con title
                                        name = name_elem.get_attribute('title')
                                        if not name:
                                            # Poi con testo
                                            name = name_elem.text
                                        if name and name.strip():
                                            name = name.strip()
                                            break
                                except:
                                    continue
                            
                            if not name:
                                # Fallback finale: prendi tutto il testo dell'elemento
                                try:
                                    name = elem.text.split('\n')[0].strip()
                                    if len(name) > 50:
                                        name = name[:50]
                                except:
                                    name = f"Chat {idx+1}"
                            
                            if name and len(name) > 0:
                                chats.append({
                                    'index': idx,
                                    'name': name,
                                    'last_message': '',
                                    'element_id': f"chat_{idx}"
                                })
                                print(f"  Chat trovata: {name}")
                        except Exception as e:
                            print(f"  ⚠️  Errore processando elemento {idx}: {e}")
                            continue
                except Exception as e:
                    print(f"  ⚠️  Errore fallback Selenium: {e}")
                    pass
            else:
                print(f"  Trovate {len(chats)} chat con JavaScript")
            
            if not chats:
                print("  ℹ️  Suggerimento: Assicurati di essere nella schermata principale di WhatsApp Web")
                print("  ℹ️  con la lista delle chat visibile sulla sinistra")
            
            return chats if chats else []
            
        except Exception as e:
            print(f"  ⚠️  Errore estrazione chat: {e}")
            return []
    
    async def open_chat_by_index(self, chat_index: int) -> bool:
        """
        Apre una chat specifica dall'indice nella lista.
        
        Args:
            chat_index: Indice della chat (0-based)
            
        Returns:
            True se la chat è stata aperta con successo
        """
        try:
            if not self.driver:
                print("  ⚠️  Driver non disponibile")
                return False
            
            if chat_index < 0:
                print(f"  ⚠️  Indice chat non valido: {chat_index}")
                return False
            
            # Usa JavaScript per cliccare sulla chat (più affidabile)
            js_click_chat = """
            const chatIndex = arguments[0];
            
            // Selettori per le chat WhatsApp (stessi di get_available_chats)
            const chatSelectors = [
                '[data-testid="cell-frame-container"]',
                'div[role="row"]',
                'div[data-testid="chat"]'
            ];
            
            let chatElements = [];
            for (let sel of chatSelectors) {
                const elems = document.querySelectorAll(sel);
                if (elems.length > 0) {
                    chatElements = Array.from(elems);
                    break;
                }
            }
            
            if (chatIndex >= chatElements.length) {
                return { success: false, error: 'Index out of bounds', total: chatElements.length };
            }
            
            const chatElement = chatElements[chatIndex];
            if (!chatElement) {
                return { success: false, error: 'Element not found' };
            }
            
            // Clicca sulla chat
            chatElement.click();
            
            return { success: true, clicked: true };
            """
            
            result = self.driver.execute_script(js_click_chat, chat_index)
            
            if result and result.get('success'):
                await asyncio.sleep(2)
                print(f"  Chat aperta")
                return True
            else:
                error_msg = result.get('error', 'Unknown error') if result else 'No result'
                print(f"  ⚠️  Errore JavaScript: {error_msg}")
                
                # Fallback: prova con Selenium
                print("  🔄 Tentativo con Selenium...")
                return await self._open_chat_by_index_selenium(chat_index)
            
        except Exception as e:
            print(f"  ⚠️  Errore apertura chat (JavaScript): {e}")
            # Fallback: prova con Selenium
            print("  🔄 Tentativo con Selenium...")
            return await self._open_chat_by_index_selenium(chat_index)
    
    async def _open_chat_by_index_selenium(self, chat_index: int) -> bool:
        """
        Fallback: apre chat usando Selenium (usa stessi selettori di get_available_chats)
        """
        try:
            # Prova diversi selettori (stessi di get_available_chats)
            selectors_to_try = [
                "[data-testid='cell-frame-container']",
                "div[role='row']",
                "div[data-testid='chat']",
                "div._8nE1Y"
            ]
            
            chat_elements = []
            for selector in selectors_to_try:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        print(f"  Trovati {len(elements)} elementi con selettore: {selector}")
                        chat_elements = elements
                        break
                except:
                    continue
            
            if not chat_elements:
                print("  ❌ Nessun elemento chat trovato")
                return False
            
            if chat_index >= len(chat_elements):
                print(f"  ⚠️  Indice {chat_index} fuori range (totale: {len(chat_elements)})")
                return False
            
            # Clicca sulla chat
            chat_element = chat_elements[chat_index]
            
            # Scrolla l'elemento in view se necessario
            try:
                self.driver.execute_script("arguments[0].scrollIntoView(true);", chat_element)
                await asyncio.sleep(0.5)
            except:
                pass
            
            chat_element.click()
            await asyncio.sleep(2)
            
            print(f"  Chat aperta (Selenium)")
            return True
            
        except Exception as e:
            print(f"  ❌ Errore apertura chat (Selenium): {e}")
            return False
    
    async def _get_chat_messages_simple(self, verbose: bool = False) -> List[Dict[str, Any]]:
        """
        Metodo JAVASCRIPT PURO - ULTRA VELOCE (10x più veloce di Selenium)
        
        Args:
            verbose: Se True, mostra debug dettagliato
        """
        messages = []
        
        try:
            if not self.driver:
                return messages
            
            # USA JAVASCRIPT DIRETTO (molto più veloce)
            js_code = """
            const messages = [];
            const messageElements = document.querySelectorAll('div.message-in, div.message-out');
            const lastMessages = Array.from(messageElements).slice(-10); // Ultimi 10
            
            lastMessages.forEach((elem, idx) => {
                const text = elem.innerText || elem.textContent || '';
                if (text && text.length < 500) {
                    const isReceived = elem.className.includes('message-in');
                    messages.push({
                        id: idx + '_' + text.substring(0, 20),
                        text: text.trim(),
                        is_received: isReceived,
                        index: idx
                    });
                }
            });
            
            return messages;
            """
            
            messages = self.driver.execute_script(js_code)
            
            if verbose:
                print(f"    {len(messages)} messaggi")
            
            return messages or []
            
            if verbose:
                print(f"    Estratti {len(messages)} messaggi")
            return messages
            
        except Exception as e:
            print(f"    ❌ Errore estrazione messaggi: {e}")
            return messages
    
    async def _get_chat_messages(self) -> List[Dict[str, Any]]:
        """
        Estrae tutti i messaggi dalla chat corrente.
        
        Returns:
            Lista di dizionari con informazioni sui messaggi
        """
        messages = []
        
        try:
            if not self.driver:
                return messages
            
            # Usa JavaScript per estrarre i messaggi dalla chat
            js_get_messages = """
            const messages = [];
            
            // Selettori per i messaggi WhatsApp
            const messageSelectors = [
                '[data-testid="msg-container"]',
                'div[data-id]',
                'div.message',
                'div[role="row"]'
            ];
            
            let messageElements = [];
            for (let sel of messageSelectors) {
                const elems = document.querySelectorAll(sel);
                if (elems.length > 0) {
                    messageElements = Array.from(elems);
                    break;
                }
            }
            
            // Se non trovati, cerca qualsiasi div con testo che sembra un messaggio
            if (messageElements.length === 0) {
                const allDivs = document.querySelectorAll('div[role="row"]');
                messageElements = Array.from(allDivs).filter(div => {
                    const text = div.textContent || '';
                    return text.trim().length > 0 && text.trim().length < 500;
                });
            }
            
            // Estrai informazioni da ogni messaggio
            messageElements.forEach((elem, index) => {
                try {
                    // Determina se è un messaggio ricevuto o inviato
                    // Nuovo approccio: usa le classi CSS di WhatsApp che indicano la direzione
                    const msgContainer = elem.closest('[data-testid="msg-container"]');
                    
                    // Metodo 1: Controlla checkmarks (messaggi inviati hanno checkmarks)
                    const hasDoubleCheck = elem.querySelector('[data-testid="msg-dblcheck"]') !== null;
                    const hasSingleCheck = elem.querySelector('[data-testid="msg-check"]') !== null;
                    const hasAnyCheck = hasDoubleCheck || hasSingleCheck;
                    
                    // Metodo 2: Controlla classi CSS per direzione messaggio
                    let isMessageOut = false;
                    if (msgContainer) {
                        // Controlla diverse classi che indicano messaggi inviati
                        const classList = msgContainer.className || '';
                        isMessageOut = classList.includes('message-out') || 
                                      classList.includes('_1yQkf') ||  // Classe messaggio inviato
                                      msgContainer.getAttribute('data-id')?.includes('true');
                    }
                    
                    // Metodo 3: Controlla il colore di sfondo (messaggi inviati hanno sfondo verde)
                    const bgColor = window.getComputedStyle(elem).backgroundColor;
                    const hasGreenBg = bgColor.includes('rgb(0, 95, 82)') || // Verde WhatsApp scuro
                                      bgColor.includes('rgb(214, 249, 231)') || // Verde chiaro
                                      bgColor.includes('rgb(5, 150, 105)');
                    
                    // Metodo 4: Controlla la posizione (messaggi ricevuti sono a sinistra)
                    // Questo è il metodo più affidabile!
                    let isAlignedLeft = false;
                    if (msgContainer) {
                        const parentDiv = msgContainer.parentElement;
                        if (parentDiv) {
                            const flexClass = parentDiv.className || '';
                            const computedStyle = window.getComputedStyle(parentDiv);
                            // Messaggi ricevuti hanno flex-start, inviati hanno flex-end
                            isAlignedLeft = computedStyle.justifyContent === 'flex-start' ||
                                          flexClass.includes('message-in') ||
                                          flexClass.includes('_1yQkf') === false;
                        }
                    }
                    
                    // Un messaggio è RICEVUTO se:
                    // - NON ha checkmarks O
                    // - È allineato a sinistra E NON ha sfondo verde
                    // Usiamo un approccio multi-check con priorità all'allineamento
                    let isReceived = false;
                    
                    if (!hasAnyCheck && !isMessageOut) {
                        // Metodo principale: nessun check, non marcato out
                        isReceived = true;
                    } else if (isAlignedLeft && !hasGreenBg) {
                        // Fallback: controlla posizione e colore
                        isReceived = true;
                    } else if (!hasAnyCheck && !hasGreenBg) {
                        // Secondo fallback: nessun check e nessun bg verde
                        isReceived = true;
                    }
                    
                    // Estrai il testo del messaggio
                    const textSelectors = [
                        'span.selectable-text',
                        'span[dir="ltr"]',
                        'span[dir="auto"]',
                        'div.selectable-text',
                        'span'
                    ];
                    
                    let messageText = '';
                    for (let sel of textSelectors) {
                        const textElem = elem.querySelector(sel);
                        if (textElem) {
                            messageText = textElem.textContent || textElem.innerText || '';
                            if (messageText.trim()) {
                                break;
                            }
                        }
                    }
                    
                    // Fallback: tutto il testo dell'elemento
                    if (!messageText.trim()) {
                        messageText = elem.textContent || elem.innerText || '';
                    }
                    
                    // Pulisci il testo
                    messageText = messageText.trim();
                    
                    // Salta se è vuoto o troppo lungo (probabilmente non è un messaggio)
                    if (!messageText || messageText.length > 500) {
                        return;
                    }
                    
                    // Crea un ID univoco basato sulla posizione e contenuto
                    const messageId = `${index}_${messageText.substring(0, 20).replace(/[^a-zA-Z0-9]/g, '')}`;
                    
                    messages.push({
                        id: messageId,
                        text: messageText,
                        is_received: isReceived,
                        index: index
                    });
                } catch (e) {
                    // Ignora errori su singoli messaggi
                }
            });
            
            return messages;
            """
            
            messages = self.driver.execute_script(js_get_messages)
            
            if not messages:
                # Fallback: prova con selettori Selenium
                try:
                    message_elements = self.driver.find_elements(By.CSS_SELECTOR, "[data-testid='msg-container']")
                    for idx, elem in enumerate(message_elements[-20:]):  # Ultimi 20 messaggi
                        try:
                            text_elem = elem.find_element(By.CSS_SELECTOR, "span.selectable-text")
                            text = text_elem.text.strip()
                            if text:
                                # Determina se è ricevuto (non ha doppio check)
                                is_received = not elem.find_elements(By.CSS_SELECTOR, "[data-testid='msg-dblcheck']")
                                messages.append({
                                    'id': f"sel_{idx}_{text[:20]}",
                                    'text': text,
                                    'is_received': is_received,
                                    'index': idx
                                })
                        except:
                            continue
                except:
                    pass
            
            return messages if messages else []
            
        except Exception as e:
            print(f"  ⚠️  Errore estrazione messaggi: {e}")
            return []
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Ritorna lo stato della connessione"""
        return {
            'connected': self.is_connected,
            'driver_active': self.driver is not None,
            'stats': self.stats.copy()
        }
    
    async def test_connection(self) -> bool:
        """Testa la connessione WhatsApp"""
        if not self.driver:
            return False
        
        try:
            self.driver.get("https://web.whatsapp.com")
            await asyncio.sleep(3)
            
            # Verifica presenza chat list
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='chat-list']"))
            )
            self.is_connected = True
            return True
        except:
            self.is_connected = False
            return False
    
    # ========== ROBUST METHODS (NEW) ==========
    
    async def send_message_to_contact_robust(self, contact_name: str, message: str, timeout: int = 90) -> bool:
        """
        METODO ROBUSTO per inviare messaggi con gestione migliorata degli errori
        
        Questo metodo usa strategie multiple per:
        1. Trovare il contatto (anche con nomi parziali)
        2. Aprire la chat (verifica effettiva)
        3. Inviare il messaggio (senza duplicazioni)
        
        Args:
            contact_name: Nome del contatto o numero di telefono
            message: Messaggio da inviare
            timeout: Timeout massimo in secondi
            
        Returns:
            True se il messaggio è stato inviato con successo
        """
        
        if not self.is_connected:
            print("WhatsApp non connesso")
            print("Esegui prima: await whatsapp_client.initialize()")
            return False
        
        print(f"\n{'='*70}")
        print(f"📱 INVIO MESSAGGIO ROBUSTO")
        print(f"{'='*70}")
        print(f"👤 Contatto: {contact_name}")
        print(f"📝 Messaggio: {message}")
        print(f"⏱️  Timeout: {timeout}s")
        print(f"{'='*70}\n")
        
        try:
            # Step 1: Find and open contact
            print("🔍 FASE 1: Ricerca e apertura contatto")
            print("-" * 70)
            
            contact_found = await WhatsAppContactFixer.find_and_open_contact_robust(
                self.driver, contact_name, timeout=timeout
            )
            
            if not contact_found:
                print("\n❌ FALLIMENTO: Impossibile trovare o aprire il contatto")
                print("Suggerimenti:")
                print("   1. Verifica che il contatto esista in WhatsApp")
                print("   2. Prova a usare il numero di telefono completo (es: +39...)")
                print("   3. Verifica che WhatsApp Web sia completamente caricato")
                print("   4. Chiudi eventuali popup o notifiche")
                print("   5. Prova a cercare manualmente il contatto per verificare il nome esatto")
                self.stats['messages_failed'] += 1
                return False
            
            print("\nFASE 1 COMPLETATA: Contatto trovato e chat aperta")
            
            # Step 2: Send message
            print("\n📤 FASE 2: Invio messaggio")
            print("-" * 70)
            
            message_sent = await WhatsAppContactFixer.send_message_robust(
                self.driver, message, max_retries=3
            )
            
            if not message_sent:
                print("\n❌ FALLIMENTO: Impossibile inviare il messaggio")
                print("Suggerimenti:")
                print("   1. Verifica che la chat sia ancora aperta")
                print("   2. Controlla che non ci siano popup o notifiche")
                print("   3. Verifica che WhatsApp Web sia responsive")
                self.stats['messages_failed'] += 1
                return False
            
            print("\nFASE 2 COMPLETATA: Messaggio inviato")
            print(f"\n{'='*70}")
            print("🎉 SUCCESSO: Messaggio inviato correttamente!")
            print(f"{'='*70}\n")
            
            self.stats['messages_sent'] += 1
            return True
            
        except asyncio.TimeoutError:
            print(f"\n❌ TIMEOUT: Operazione superata il limite di {timeout}s")
            print("Suggerimenti:")
            print("   1. Aumenta il timeout (parametro timeout)")
            print("   2. Verifica la connessione internet")
            print("   3. Riavvia WhatsApp Web")
            self.stats['messages_failed'] += 1
            return False
            
        except Exception as e:
            print(f"\n❌ ERRORE IMPREVISTO: {e}")
            import traceback
            print(f"📋 Traceback: {traceback.format_exc()[:500]}")
            self.stats['messages_failed'] += 1
            return False
    
    async def send_message_in_current_chat(self, message: str, timeout: int = 60) -> bool:
        """
        Invia un messaggio nella chat ATTUALMENTE APERTA (senza cercare contatto)
        
        Utile per conversazioni dove la chat è già aperta
        
        Args:
            message: Messaggio da inviare
            timeout: Timeout massimo in secondi
            
        Returns:
            True se il messaggio è stato inviato con successo
        """
        
        if not self.is_connected:
            print("WhatsApp non connesso")
            return False
        
        print(f"\n📤 INVIO MESSAGGIO IN CHAT CORRENTE")
        print(f"📝 Messaggio: {message}")
        
        try:
            # Verifica che ci sia una chat aperta (controlla input box)
            try:
                # Cerca input box (più affidabile del header)
                input_box = self.driver.find_elements(By.CSS_SELECTOR, "footer div[contenteditable='true']")
                if not input_box or not any(i.is_displayed() for i in input_box):
                    print("Nessuna chat aperta (no input box)")
                    return False
                print("✓ Chat aperta rilevata")
            except Exception as e:
                print(f"Errore verifica chat: {str(e)[:50]}")
                return False
            
            # Invia il messaggio direttamente
            message_sent = await asyncio.wait_for(
                WhatsAppContactFixer.send_message_robust(self.driver, message, max_retries=3),
                timeout=timeout
            )
            
            if message_sent:
                print("Messaggio inviato nella chat corrente!")
                self.stats['messages_sent'] += 1
                return True
            else:
                print("Invio fallito")
                self.stats['messages_failed'] += 1
                return False
                
        except asyncio.TimeoutError:
            print(f"Timeout ({timeout}s) durante l'invio")
            self.stats['messages_failed'] += 1
            return False
        except Exception as e:
            print(f"Errore: {e}")
            self.stats['messages_failed'] += 1
            return False
    
    async def send_message_robust(self, phone_number: str, message: str, timeout: int = 60) -> bool:
        """
        METODO ROBUSTO per inviare messaggi tramite numero di telefono
        
        Usa navigazione diretta URL per massima affidabilità
        
        Args:
            phone_number: Numero di telefono (formato: +39... o solo numeri)
            message: Messaggio da inviare
            timeout: Timeout massimo in secondi
            
        Returns:
            True se il messaggio è stato inviato con successo
        """
        
        if not self.is_connected:
            print("WhatsApp non connesso")
            return False
        
        print(f"\n{'='*70}")
        print(f"📱 INVIO MESSAGGIO ROBUSTO (NUMERO)")
        print(f"{'='*70}")
        print(f"📞 Numero: {phone_number}")
        print(f"📝 Messaggio: {message}")
        print(f"{'='*70}\n")
        
        try:
            # Clean phone number
            clean_number = phone_number.replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            
            # Navigate directly to chat
            print("Navigazione diretta alla chat...")
            url = f"https://web.whatsapp.com/send?phone={clean_number}"
            self.driver.get(url)
            await asyncio.sleep(5)
            
            # Verify chat opened
            if not await WhatsAppContactFixer._verify_chat_opened(self.driver, timeout=10):
                print("Chat non aperta dopo navigazione URL")
                print("Verifica che il numero sia corretto e registrato su WhatsApp")
                self.stats['messages_failed'] += 1
                return False
            
            print("Chat aperta tramite URL")
            
            # Send message
            print("\n📤 Invio messaggio...")
            message_sent = await WhatsAppContactFixer.send_message_robust(
                self.driver, message, max_retries=3
            )
            
            if message_sent:
                print(f"\n{'='*70}")
                print("🎉 SUCCESSO: Messaggio inviato!")
                print(f"{'='*70}\n")
                self.stats['messages_sent'] += 1
                return True
            else:
                print("\n❌ Invio fallito")
                self.stats['messages_failed'] += 1
                return False
                
        except Exception as e:
            print(f"\n❌ ERRORE: {e}")
            self.stats['messages_failed'] += 1
            return False
    
    def close(self, force_close: bool = False):
        """Chiude la connessione WhatsApp"""
        try:
            if self.driver:
                if force_close:
                    self.driver.quit()
                else:
                    # Mantieni la sessione aperta
                    pass
                self.is_connected = False
                print("  Connessione WhatsApp chiusa")
        except Exception as e:
            print(f"  ⚠️  Errore chiusura: {e}")
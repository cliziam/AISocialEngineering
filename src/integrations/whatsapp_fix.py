"""
WhatsApp Client Fix - Improved Contact Finding and Message Sending
This module provides enhanced methods to fix common issues with WhatsApp Web automation
"""

import asyncio
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import Optional, Dict, Any


class WhatsAppContactFixer:
    """Helper class to fix contact finding and message sending issues"""
    
    @staticmethod
    async def find_and_open_contact_robust(driver, contact_name: str, timeout: int = 60) -> bool:
        """
        Robust method to find and open a contact with multiple fallback strategies
        
        Args:
            driver: Selenium WebDriver
            contact_name: Name of the contact to find
            timeout: Maximum time to wait
            
        Returns:
            True if contact was found and chat opened successfully
        """
        print(f"\nRICERCA ROBUSTA CONTATTO: {contact_name}")
        print("=" * 60)
        
        # Strategy 1: Direct URL navigation (fastest if we have the number)
        if contact_name.startswith('+') or contact_name.isdigit():
            print("Rilevato numero di telefono, uso navigazione diretta...")
            clean_number = contact_name.replace('+', '').replace(' ', '').replace('-', '')
            try:
                url = f"https://web.whatsapp.com/send?phone={clean_number}"
                driver.get(url)
                await asyncio.sleep(5)
                
                # Verify chat opened
                if await WhatsAppContactFixer._verify_chat_opened(driver):
                    print("Chat aperta tramite URL diretto!")
                    return True
                else:
                    print("URL diretto non ha funzionato, provo ricerca...")
            except Exception as e:
                print(f"Errore navigazione diretta: {e}")
        
        # Strategy 2: Search with SOLO 2 variations (più veloce)
        name_variations = [contact_name, contact_name.title()]  # Solo originale e Title Case
        
        for variation_idx, search_term in enumerate(name_variations, 1):
            print(f"\nCerca: '{search_term}'")
            
            # Step 1: Find and clear search box
            search_box = await WhatsAppContactFixer._find_and_prepare_search_box(driver)
            if not search_box:
                print("Impossibile trovare la barra di ricerca")
                continue
            
            # Step 2: Enter search term
            try:
                search_box.click()
                search_box.send_keys(search_term)
                await asyncio.sleep(0.5)  # Ridotto da 0.8s a 0.5s
                print(f"Termine inserito, attendo risultati...")
            except Exception as e:
                print(f"Errore inserimento termine: {e}")
                continue
            
            # Step 3: Find matching result
            matching_result = await WhatsAppContactFixer._find_best_matching_result(
                driver, contact_name, search_term
            )
            
            if not matching_result:
                print(f"Nessun risultato per '{search_term}'")
                continue
            
            print(f"Trovato: {matching_result['name']}")
            
            # Step 3.5: Chiudi eventuali popup
            try:
                close_buttons = driver.find_elements(By.CSS_SELECTOR, "[data-testid='popup-close'], button[aria-label='Close']")
                for btn in close_buttons:
                    if btn.is_displayed():
                        btn.click()
                        await asyncio.sleep(0.2)
            except:
                pass
            
            # Step 4: METODO TASTIERA (più affidabile del click)
            print("Uso tastiera per aprire chat...")
            try:
                # Premi INVIO sulla search box per selezionare il primo risultato
                search_box.send_keys(Keys.ENTER)
                await asyncio.sleep(0.8)
                
                # Verifica se la chat si è aperta
                if await WhatsAppContactFixer._verify_chat_opened(driver, timeout=10):
                    print("CHAT APERTA CON TASTIERA!")
                    return True
                else:
                    print("Tastiera non ha funzionato, potrebbe essere un contatto senza chat...")
                    # Prova a gestire il pannello contatto
                    if await WhatsAppContactFixer._handle_contact_info_panel(driver):
                        print("CHAT APERTA TRAMITE PANNELLO CONTATTO!")
                        return True
                    print("Provo click...")
            except Exception as e:
                print(f"Errore tastiera: {str(e)[:50]}")
            
            # Step 4b: FALLBACK - Click on result
            if await WhatsAppContactFixer._click_contact_robust(driver, matching_result):
                if await WhatsAppContactFixer._verify_chat_opened(driver, timeout=10):
                    print("CHAT APERTA CON CLICK!")
                    return True
                else:
                    print("Click non ha aperto chat, potrebbe essere un contatto senza chat...")
                    # Prova a gestire il pannello contatto
                    if await WhatsAppContactFixer._handle_contact_info_panel(driver):
                        print("CHAT APERTA TRAMITE PANNELLO CONTATTO!")
                        return True
                    # Ultimo tentativo: doppio click
                    try:
                        element = matching_result['element']
                        driver.execute_script("arguments[0].click(); arguments[0].click();", element)
                        await asyncio.sleep(0.8)
                        if await WhatsAppContactFixer._verify_chat_opened(driver, timeout=10):
                            print("CHAT APERTA CON DOPPIO CLICK!")
                            return True
                        else:
                            # Anche dopo doppio click, prova pannello contatto
                            if await WhatsAppContactFixer._handle_contact_info_panel(driver):
                                print("CHAT APERTA TRAMITE PANNELLO CONTATTO (dopo doppio click)!")
                                return True
                    except:
                        pass
            
            print("Tutti i metodi falliti, provo prossima variazione...")
            continue
        
        print("\nIMPOSSIBILE TROVARE E APRIRE IL CONTATTO")
        print("Suggerimenti:")
        print("   1. Verifica che il contatto esista in WhatsApp")
        print("   2. Prova a usare il numero di telefono invece del nome")
        print("   3. Verifica che WhatsApp Web sia completamente caricato")
        print("   4. Chiudi eventuali popup o notifiche")
        
        return False
    
    @staticmethod
    async def send_message_robust(driver, message: str, max_retries: int = 3) -> bool:
        """
        Robust method to send a message with multiple fallback strategies
        
        Args:
            driver: Selenium WebDriver
            message: Message text to send
            max_retries: Maximum number of retry attempts
            
        Returns:
            True if message was sent successfully
        """
        print(f"\nINVIO MESSAGGIO ROBUSTO")
        print("=" * 60)
        print(f"Messaggio: {message}")
        
        for attempt in range(max_retries):
            print(f"\nTentativo {attempt + 1}/{max_retries}")
            
            # Step 1: Find input box
            step_start = time.time()
            input_box = await WhatsAppContactFixer._find_input_box_robust(driver)
            print(f"  Find input: {time.time() - step_start:.2f}s")
            if not input_box:
                print("Input box non trovata")
                if attempt < max_retries - 1:
                    print("Attendo 1 secondo e riprovo...")
                    await asyncio.sleep(1)  # Ridotto da 3s
                    continue
                else:
                    return False
            
            # Step 2: Clear input box (ULTRA VELOCE)
            try:
                step_start = time.time()
                await asyncio.wait_for(
                    WhatsAppContactFixer._clear_input_box_robust(driver, input_box),
                    timeout=2  # Ridotto da 3s a 2s
                )
                print(f"  Clear: {time.time() - step_start:.2f}s")
            except asyncio.TimeoutError:
                print("Timeout pulizia (2s)")
                if attempt < max_retries - 1:
                    continue
                else:
                    return False
            
            # Step 3: Insert text (ULTRA VELOCE)
            try:
                step_start = time.time()
                result = await asyncio.wait_for(
                    WhatsAppContactFixer._insert_text_robust(driver, input_box, message),
                    timeout=5  # Ridotto da 8s a 5s
                )
                print(f"  Insert: {time.time() - step_start:.2f}s")
                if not result:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.5)  # Ridotto da 1s
                        continue
                    else:
                        return False
            except asyncio.TimeoutError:
                print("Timeout inserimento (5s)")
                if attempt < max_retries - 1:
                    continue
                else:
                    return False
            
            # Step 4: Send message (ULTRA VELOCE)
            try:
                result = await asyncio.wait_for(
                    WhatsAppContactFixer._send_message_final(driver, input_box),
                    timeout=3  # Ridotto da 5s a 3s
                )
                if result:
                    print("INVIATO!")
                    return True
                else:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.5)  # Ridotto da 1s
                        continue
            except asyncio.TimeoutError:
                print("Timeout invio (3s)")
                if attempt < max_retries - 1:
                    continue
                else:
                    return False
        
        print("\nIMPOSSIBILE INVIARE MESSAGGIO DOPO TUTTI I TENTATIVI")
        return False
    
    # ========== HELPER METHODS ==========
    
    @staticmethod
    async def _find_and_prepare_search_box(driver):
        """Find search box and prepare it for input"""
        try:
            # Close any open search first
            try:
                from selenium.webdriver.common.action_chains import ActionChains
                actions = ActionChains(driver)
                actions.send_keys(Keys.ESCAPE)
                actions.perform()
                await asyncio.sleep(0.5)
            except:
                pass
            
            # Find search box with multiple selectors (aggiornati per WhatsApp Web 2024)
            selectors = [
                "[data-testid='chat-list-search']",
                "div[contenteditable='true'][data-tab='3']",
                "div[title='Search input textbox']",
                "div[role='textbox'][data-tab='3']",
                "div.selectable-text[contenteditable='true'][data-tab='3']",
                "div[aria-label='Search input textbox']",
                "div[data-lexical-editor='true']",
                "p[class*='selectable-text']",
            ]
            
            search_box = None
            for selector in selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        print(f"  Trovati {len(elements)} elementi con selector: {selector[:50]}")
                    for elem in elements:
                        if elem.is_displayed() and elem.is_enabled():
                            search_box = elem
                            print(f"  Search box trovata con: {selector[:50]}")
                            break
                    if search_box:
                        break
                except Exception as e:
                    print(f"  Errore con selector {selector[:30]}: {str(e)[:30]}")
                    continue
            
            if not search_box:
                print("  Nessuna search box trovata con tutti i selettori")
                return None
            
            # Clear search box
            try:
                search_box.click()
                await asyncio.sleep(0.2)
                search_box.send_keys(Keys.CONTROL + "a")
                search_box.send_keys(Keys.BACKSPACE)
                await asyncio.sleep(0.3)
                
                # Verify it's empty
                current_text = search_box.text or search_box.get_attribute('innerText') or ''
                if current_text.strip():
                    # Try JavaScript clear
                    driver.execute_script("""
                        const el = arguments[0];
                        el.innerHTML = '';
                        el.textContent = '';
                    """, search_box)
                    await asyncio.sleep(0.2)
            except:
                pass
            
            return search_box
            
        except Exception as e:
            print(f"Errore preparazione search box: {e}")
            return None
    
    @staticmethod
    async def _find_best_matching_result(driver, original_name: str, search_term: str) -> Optional[Dict]:
        """Find the best matching search result - ULTRA VELOCE"""
        try:
            # NO SLEEP - inizia subito
            
            # USA SOLO il selettore che funziona (abbiamo già verificato che div[role='row'] funziona)
            results = []
            try:
                results = driver.find_elements(By.CSS_SELECTOR, "div[role='row']")
                if results:
                    print(f"  Trovati {len(results)} risultati")
            except:
                pass
            
            # Fallback veloce se non trova nulla
            if not results:
                try:
                    results = driver.find_elements(By.CSS_SELECTOR, "[data-testid='cell-frame-container']")
                except:
                    pass
            
            if not results:
                print("  Nessun risultato trovato con selettori standard")
                # Debug: stampa HTML della pagina per capire cosa c'è
                try:
                    page_text = driver.find_element(By.TAG_NAME, "body").text[:500]
                    print(f"  Contenuto pagina (primi 500 char): {page_text[:200]}...")
                    
                    # FALLBACK: Se vediamo il nome nella pagina, prova a cliccare direttamente
                    if search_term.lower() in page_text.lower():
                        print(f"  Trovato '{search_term}' nel testo, provo click diretto...")
                        # Cerca tutti gli elementi cliccabili che contengono il testo
                        all_elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{search_term}')]")
                        print(f"  Trovati {len(all_elements)} elementi con testo '{search_term}'")
                        
                        for elem in all_elements[:5]:  # Prova i primi 5
                            try:
                                if elem.is_displayed():
                                    # Trova il parent cliccabile (di solito 2-3 livelli sopra)
                                    clickable = elem
                                    for _ in range(3):
                                        parent = clickable.find_element(By.XPATH, "..")
                                        if parent:
                                            clickable = parent
                                    
                                    results = [clickable]
                                    print(f"  Trovato elemento cliccabile con fallback")
                                    break
                            except:
                                continue
                except:
                    pass
                
                if not results:
                    return None
            
            # Extract names and find best match - VELOCE
            best_match = None
            best_score = 0
            
            # Controlla SOLO i primi 5 risultati (più veloce)
            for result in results[:5]:
                try:
                    # Estrai nome VELOCE - solo 1 metodo
                    name = None
                    try:
                        # Prova prima con title (più veloce)
                        name_elem = result.find_element(By.CSS_SELECTOR, "span[title]")
                        name = name_elem.get_attribute('title')
                    except:
                        # Fallback: text
                        try:
                            name = result.text.split('\n')[0]  # Prima riga
                        except:
                            pass
                    
                    if not name:
                        continue
                    
                    # Calculate match score VELOCE
                    score = WhatsAppContactFixer._calculate_name_match_score(
                        name, original_name, search_term
                    )
                    
                    if score > best_score:
                        best_score = score
                        best_match = {
                            'element': result,
                            'name': name,
                            'score': score
                        }
                
                except:
                    continue
            
            if best_match and best_score > 0.5:  # Minimum 50% match
                return best_match
            
            return None
            
        except Exception as e:
            print(f"Errore ricerca risultati: {e}")
            return None
    
    @staticmethod
    def _calculate_name_match_score(found_name: str, original_name: str, search_term: str) -> float:
        """Calculate how well a found name matches - VELOCE"""
        found_lower = found_name.lower().strip()
        search_lower = search_term.lower().strip()
        
        # Exact match
        if search_lower in found_lower:
            return 1.0
        
        # Partial match (prima parola)
        if found_lower.startswith(search_lower) or search_lower in found_lower.split():
            return 0.9
        
        return 0.0
    
    @staticmethod
    async def _click_contact_robust(driver, contact_result: Dict) -> bool:
        """Click on contact with multiple strategies"""
        element = contact_result['element']
        name = contact_result['name']
        
        print(f"Click su '{name}'...")
        
        # Strategy 1: JavaScript click (PIÙ VELOCE - no attesa DOM)
        try:
            driver.execute_script("arguments[0].click();", element)
            await asyncio.sleep(0.5)  # Aumentato da 0.2s a 0.5s per dare tempo a WhatsApp
            return True
        except Exception as e:
            print(f"Click JavaScript fallito: {str(e)[:50]}")
        
        # Strategy 2: Regular click (fallback)
        try:
            element.click()
            await asyncio.sleep(0.5)  # Aumentato da 0.3s a 0.5s
            return True
        except Exception as e:
            print(f"Click normale fallito: {str(e)[:50]}")
        
        # Strategy 3: Action chains (ultimo resort)
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            actions = ActionChains(driver)
            actions.move_to_element(element)
            actions.click()
            actions.perform()
            await asyncio.sleep(0.5)  # Aumentato da 0.3s a 0.5s
            return True
        except Exception as e:
            print(f"Action chains fallito: {str(e)[:50]}")
        
        return False
    
    @staticmethod
    async def _handle_contact_info_panel(driver) -> bool:
        """
        Gestisce il caso in cui si apre il pannello info contatto invece della chat.
        Cerca il pulsante "Message" e lo clicca per aprire la chat.
        
        Returns:
            True se è riuscito ad aprire la chat dal pannello contatto
        """
        print("  Controllo se è aperto il pannello contatto...")
        
        try:
            # Aspetta un attimo per far caricare il pannello
            await asyncio.sleep(0.5)
            
            # Cerca il pulsante "Message" / "Messaggio" / "Invia messaggio"
            # WhatsApp usa vari selettori per questo pulsante
            message_button_selectors = [
                # Selettore con data-testid
                "[data-testid='btn-start-conversation']",
                "[data-testid='btn-start-new-conversation']",
                # Selettore con aria-label
                "div[role='button'][aria-label*='Message']",
                "div[role='button'][aria-label*='Messaggio']",
                "div[role='button'][aria-label*='messaggio']",
                # Selettore con testo
                "//div[@role='button' and contains(., 'Message')]",
                "//div[@role='button' and contains(., 'Messaggio')]",
                "//span[contains(text(), 'Message')]/ancestor::div[@role='button']",
                "//span[contains(text(), 'Messaggio')]/ancestor::div[@role='button']",
                # Fallback generico per pulsanti nell'area contatto
                "div[data-tab] div[role='button']",
            ]
            
            for selector in message_button_selectors:
                try:
                    # Prova XPath o CSS a seconda del selector
                    if selector.startswith("//"):
                        buttons = driver.find_elements(By.XPATH, selector)
                    else:
                        buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for button in buttons:
                        if button.is_displayed():
                            button_text = button.text.lower()
                            # Verifica che il pulsante sia quello giusto
                            if any(keyword in button_text for keyword in ['message', 'messaggio', 'invia']):
                                print(f"  Trovato pulsante: '{button.text}', clicco...")
                                # Clicca con JavaScript per maggiore affidabilità
                                driver.execute_script("arguments[0].click();", button)
                                await asyncio.sleep(1.0)
                                
                                # Verifica se la chat si è aperta
                                if await WhatsAppContactFixer._verify_chat_opened(driver, timeout=5):
                                    return True
                except Exception as e:
                    continue
            
            # Ultima strategia: cerca qualsiasi elemento cliccabile nella sidebar destra
            # che potrebbe essere il pulsante per iniziare la chat
            print("  Pulsante non trovato con selettori standard, provo strategia fallback...")
            try:
                # Cerca elementi cliccabili nell'area destra (pannello contatto)
                clickable_elements = driver.find_elements(By.CSS_SELECTOR, 
                    "div[data-tab] div[role='button'], div[data-tab] button")
                
                for elem in clickable_elements[:5]:  # Prova i primi 5
                    try:
                        if elem.is_displayed() and elem.is_enabled():
                            print(f"  Provo elemento: {elem.text[:30]}...")
                            driver.execute_script("arguments[0].click();", elem)
                            await asyncio.sleep(0.8)
                            
                            if await WhatsAppContactFixer._verify_chat_opened(driver, timeout=5):
                                return True
                    except:
                        continue
            except:
                pass
            
            print("  Pannello contatto: nessun pulsante funzionante trovato")
            return False
            
        except Exception as e:
            print(f"  Errore gestione pannello contatto: {str(e)[:80]}")
            return False
    
    @staticmethod
    async def _verify_chat_opened(driver, timeout: int = 10) -> bool:
        """Verify that a chat has been opened successfully - BILANCIATO"""
        print("Verifica apertura chat...")
        
        # 4 tentativi veloci (totale ~1.5s)
        for attempt in range(4):
            try:
                # Check input box O header
                inputs = driver.find_elements(By.CSS_SELECTOR, "footer div[contenteditable='true']")
                if inputs and any(i.is_displayed() for i in inputs):
                    print(f"Chat aperta (tentativo {attempt + 1})")
                    return True
                
                # Fallback: check header
                header = driver.find_elements(By.CSS_SELECTOR, "[data-testid='conversation-header']")
                if header and any(h.is_displayed() for h in header):
                    print(f"Chat aperta (tentativo {attempt + 1})")
                    return True
                
                await asyncio.sleep(0.4)  # 4 tentativi x 0.4s = 1.6s totale
                
            except:
                await asyncio.sleep(0.4)
        
        return False
    
    @staticmethod
    async def _find_input_box_robust(driver):
        """Find input box with multiple strategies"""
        selectors = [
            "[data-testid='conversation-compose-box-input']",
            "div[contenteditable='true'][data-tab='10']",
            "footer div[contenteditable='true']",
            "div[role='textbox'][contenteditable='true']",
        ]
        
        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    if elem.is_displayed() and elem.is_enabled():
                        return elem
            except:
                continue
        
        return None
    
    @staticmethod
    async def _clear_input_box_robust(driver, input_box):
        """Clear input box completely - ultra-optimized"""
        try:
            # Method 1: JavaScript aggressivo (più veloce e affidabile)
            driver.execute_script("""
                const el = arguments[0];
                // Rimuovi tutto il contenuto
                el.innerHTML = '';
                el.textContent = '';
                el.innerText = '';
                // Rimuovi tutti i child nodes
                while(el.firstChild) {
                    el.removeChild(el.firstChild);
                }
                // Forza focus
                el.focus();
                // Trigger events per WhatsApp
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            """, input_box)
            await asyncio.sleep(0.05)  # Ridotto a 50ms
            
            # Quick verify (non bloccare se fallisce)
            try:
                text = input_box.text or input_box.get_attribute('innerText') or ''
                if text.strip():
                    # Fallback veloce: solo backspace multipli
                    input_box.click()
                    for _ in range(3):
                        input_box.send_keys(Keys.BACKSPACE)
                    await asyncio.sleep(0.05)
            except:
                pass  # Ignora errori di verifica
        except Exception as e:
            print(f"  ⚠️  Errore pulizia: {str(e)[:50]}")
            pass
    
    @staticmethod
    async def _insert_text_robust(driver, input_box, message: str) -> bool:
        """Insert text robustly without duplication - optimized for speed"""
        try:
            # Rimuovi emoji prima di inserire (ChromeDriver non le supporta - solo caratteri BMP)
            from src.utils.text_utils import remove_emoji
            message = remove_emoji(message)
            
            # Click to focus
            input_box.click()
            
            # Insert tutto in una volta (PIÙ VELOCE)
            if len(message) < 300:
                # Messaggi corti: invia tutto insieme
                input_box.send_keys(message)
                await asyncio.sleep(0.1)
            else:
                # Messaggi lunghi: chunk grandi
                chunk_size = 300
                for i in range(0, len(message), chunk_size):
                    chunk = message[i:i+chunk_size]
                    input_box.send_keys(chunk)
                await asyncio.sleep(0.1)
            
            # Verify text inserted
            final_text = input_box.text or input_box.get_attribute('innerText') or ''
            if len(final_text.strip()) >= len(message) * 0.8:
                print(f"Testo inserito: {len(final_text)}/{len(message)} caratteri")
                return True
            else:
                print(f"Testo incompleto: {len(final_text)}/{len(message)} caratteri")
                return False
                
        except Exception as e:
            print(f"Errore inserimento: {e}")
            return False
    
    @staticmethod
    async def _send_message_final(driver, input_box) -> bool:
        """Send the message using multiple strategies"""
        try:
            # Strategy 1: ENTER key
            input_box.send_keys(Keys.ENTER)
            await asyncio.sleep(0.3)
            
            # Assumiamo sia stato inviato (no verifica per velocità)
            return True
            
        except Exception as e:
            # Fallback: Strategy 2 - Send button
            print(f"ENTER fallito ({e}), provo pulsante send...")
            send_selectors = [
                "[data-testid='send']",
                "button[aria-label='Send']",
                "button[aria-label='Invia']",
                "span[data-icon='send']"
            ]
            
            for selector in send_selectors:
                try:
                    send_btn = driver.find_element(By.CSS_SELECTOR, selector)
                    if send_btn.is_displayed():
                        send_btn.click()
                        await asyncio.sleep(0.5)
                        return True
                except:
                    continue
            
            print(f"Errore invio: {e}")
            return False

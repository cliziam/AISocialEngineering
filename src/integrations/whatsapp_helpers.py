"""
Helper functions per WhatsApp Client
Separa la logica di utilità dal client principale
"""

import asyncio
from typing import List, Optional
from pathlib import Path
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from src.constants import WhatsAppSelectors, NameVariations, Timeouts


class WhatsAppElementFinder:
    """Trova elementi WhatsApp usando selettori multipli con fallback"""

    def __init__(
            self,
            driver,
            wait_time: int = Timeouts.WHATSAPP_ELEMENT_WAIT):
        self.driver = driver
        self.wait_time = wait_time

    async def find_element_with_selectors(
        self,
        selectors: List[str],
        element_name: str = "elemento",
        check_visibility: bool = True
    ) -> Optional[WebElement]:
        """
        Prova a trovare un elemento usando una lista di selettori CSS

        Args:
            selectors: Lista di selettori CSS da provare
            element_name: Nome dell'elemento per i log
            check_visibility: Se True, verifica che l'elemento sia visibile

        Returns:
            WebElement trovato o None
        """
        for i, selector in enumerate(selectors, 1):
            try:
                print(f" Tentativo {i}/{len(selectors)}: {selector[:50]}...")

                element = WebDriverWait(self.driver, self.wait_time).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )

                # Verifica visibilità se richiesto
                if check_visibility:
                    if not (element.is_displayed() and element.is_enabled()):
                        print(f" Elemento trovato ma non interagibile")
                        element = None
                        continue

                print(f" Trovato {element_name} con selettore: {selector}")
                return element

            except Exception as e:
                print(f" Selettore {i} fallito")
                if i < len(selectors):
                    await asyncio.sleep(1)
                continue

        print(f" Impossibile trovare {element_name}")
        return None

    async def find_clickable_element(
        self,
        selectors: List[str],
        element_name: str = "elemento cliccabile"
    ) -> Optional[WebElement]:
        """
        Trova un elemento cliccabile

        Args:
            selectors: Lista di selettori CSS
            element_name: Nome dell'elemento per i log

        Returns:
            WebElement cliccabile o None
        """
        for i, selector in enumerate(selectors, 1):
            try:
                print(f" Tentativo {i}/{len(selectors)}: {selector[:50]}...")

                element = WebDriverWait(self.driver, self.wait_time).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )

                if element.is_displayed():
                    print(f" Trovato {element_name} con selettore: {selector}")
                    return element
                else:
                    element = None

            except Exception:
                print(f" Selettore {i} fallito")
                if i < len(selectors):
                    await asyncio.sleep(0.5)
                continue

        return None


class WhatsAppClicker:
    """Gestisce i click su elementi WhatsApp con multiple strategie"""

    def __init__(self, driver):
        self.driver = driver

    async def click_element(
        self,
        element: WebElement,
        element_name: str = "elemento"
    ) -> bool:
        """
        Clicca su un elemento usando multiple strategie

        Args:
            element: Elemento da cliccare
            element_name: Nome per logging

        Returns:
            True se successo, False altrimenti
        """
        # Strategia 1: Click normale
        try:
            element.click()
            await asyncio.sleep(1)
            return True
        except Exception as e:
            print(f" Click normale fallito: {str(e)[:100]}")

        # Strategia 2: JavaScript click
        try:
            print(" Tentativo con JavaScript click...")
            self.driver.execute_script("arguments[0].click();", element)
            await asyncio.sleep(1)
            return True
        except Exception as e:
            print(f" JavaScript click fallito: {str(e)[:100]}")

        # Strategia 3: ScrollIntoView + JavaScript click
        try:
            print(" Tentativo con scrollIntoView...")
            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
            await asyncio.sleep(1)
            self.driver.execute_script("arguments[0].click();", element)
            await asyncio.sleep(1)
            return True
        except Exception as e:
            print(f" Tutti i metodi di click falliti per {element_name}")
            return False


class WhatsAppTyper:
    """Gestisce la digitazione sicura di testo in WhatsApp"""

    def __init__(self, driver):
        self.driver = driver

    async def type_message(
        self,
        element: WebElement,
        message: str,
        char_delay: float = Timeouts.WHATSAPP_TYPE_DELAY
    ) -> bool:
        """
        Digita un messaggio carattere per carattere

        Args:
            element: Elemento input dove digitare
            message: Messaggio da digitare
            char_delay: Delay tra ogni carattere

        Returns:
            True se successo, False altrimenti
        """
        try:
            # Click sull'elemento
            element.click()
            await asyncio.sleep(1)

            # Focus con JavaScript
            self.driver.execute_script("arguments[0].focus();", element)
            await asyncio.sleep(0.5)

            # Digita carattere per carattere
            for char in message:
                element.send_keys(char)
                await asyncio.sleep(char_delay)

            print(f" Messaggio digitato: '{message[:50]}...'")
            await asyncio.sleep(1)
            return True

        except Exception as e:
            print(f" Errore nella digitazione: {e}")
            return False


class WhatsAppAuthChecker:
    """Verifica lo stato di autenticazione WhatsApp"""

    def __init__(self, driver):
        self.driver = driver

    def is_authenticated(self) -> bool:
        """Verifica se WhatsApp è autenticato"""
        try:
            # Controlla presenza chat list
            chat_elements = self.driver.find_elements(
                By.CSS_SELECTOR,
                WhatsAppSelectors.CHAT_LIST
            )
            if chat_elements:
                return True

            # Controlla assenza QR code
            qr_elements = self.driver.find_elements(
                By.CSS_SELECTOR,
                WhatsAppSelectors.QR_CODE
            )
            if not qr_elements:
                return True

            # Controlla presenza menu
            menu_elements = self.driver.find_elements(
                By.CSS_SELECTOR,
                WhatsAppSelectors.MENU
            )
            if menu_elements:
                return True

            return False

        except Exception:
            return False

    async def wait_for_auth(
            self,
            timeout: int = Timeouts.WHATSAPP_QR_TIMEOUT) -> bool:
        """
        Aspetta che l'utente scansioni il QR code

        Args:
            timeout: Timeout in secondi

        Returns:
            True se autenticato, False se timeout
        """
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, WhatsAppSelectors.CHAT_LIST)
                )
            )
            print(" Autenticazione completata!")
            return True

        except Exception as e:
            print(f" Timeout durante l'autenticazione: {e}")
            return False


class WhatsAppScreenshotHelper:
    """Gestisce gli screenshot per debug"""

    def __init__(self, driver, session_path: str):
        self.driver = driver
        self.session_path = Path(session_path)

    def save_screenshot(self, name: str) -> None:
        """
        Salva uno screenshot per debug

        Args:
            name: Nome descrittivo dello screenshot
        """
        try:
            from src.utils.helpers import get_timestamp

            screenshot_path = self.session_path / f"debug_{name}_{get_timestamp()}.png"
            self.driver.save_screenshot(str(screenshot_path))
            print(f" Screenshot salvato: {screenshot_path}")

        except Exception as e:
            print(f" Impossibile salvare screenshot: {e}")


class NameVariationGenerator:
    """Genera variazioni di nomi per la ricerca"""

    @staticmethod
    def generate(name: str) -> List[str]:
        """
        Genera tutte le variazioni possibili di un nome

        Args:
            name: Nome da cui generare variazioni

        Returns:
            Lista di variazioni ordinate per priorità
        """
        return NameVariations.generate_variations(name)

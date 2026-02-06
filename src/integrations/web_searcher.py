"""
Ricercatore web per informazioni online
Supporta multiple fonti e estrazione contenuto
"""

import requests
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urljoin, urlparse
import time
import random
from typing import List, Dict, Any, Optional, Tuple
from src.core.config_manager import ConfigManager
from src.utils.validators import validate_search_term, validate_url
from src.utils.helpers import get_user_agent, retry_on_failure

class WebSearcher:
    """Ricercatore web avanzato con supporto multi-fonte"""
    
    def __init__(self, config_manager: ConfigManager = None):
        self.config_manager = config_manager or ConfigManager()
        self.session = requests.Session()
        
        # Configurazione ricerca web
        web_config = self.config_manager.get_web_search_config()
        
        self.session.headers.update({
            'User-Agent': web_config.get('user_agent', get_user_agent())
        })
        
        self.rate_limit_delay = web_config.get('rate_limit_delay', 1)
        self.max_results = web_config.get('max_results', 10)
        self.timeout = web_config.get('timeout', 15)
        
        # Pool di User-Agent per rotazione
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        
        # Cache per risultati di ricerca (evita query duplicate)
        self._search_cache = {}
        self._cache_ttl = 3600  # 1 ora in secondi
        
        # Statistiche
        self.search_stats = {
            'total_searches': 0,
            'successful_searches': 0,
            'failed_searches': 0,
            'total_results': 0,
            'cache_hits': 0
        }
    
    def _get_random_user_agent(self) -> str:
        """Restituisce un User-Agent casuale dal pool"""
        return random.choice(self.user_agents)
        
    async def search_subject(self, subject: str, 
                           search_terms: List[str] = None,
                           max_results_per_term: int = 5) -> List[Dict[str, Any]]:
        """Cerca informazioni su un soggetto specifico"""
        
        # Sanitizza input
        from src.utils.validators import sanitize_search_term
        subject = sanitize_search_term(subject)
        
        if not validate_search_term(subject):
            return []
            
        if search_terms is None:
            search_terms = self._generate_search_terms(subject)
            
        all_results = []
        
        for i, term in enumerate(search_terms, 1):
            results = await self._search_term(term)
            all_results.extend(results[:max_results_per_term])
            
            # Delay ridotto tra ricerche (solo se necessario)
            if i < len(search_terms):
                delay = 0.5 + random.uniform(0, 0.5)  # Ridotto a ~1s
                await asyncio.sleep(delay)
            
        # Rimuovi duplicati e limita risultati
        unique_results = self._remove_duplicates(all_results)
        final_results = unique_results[:self.max_results]
        
        # Aggiorna statistiche
        self.search_stats['total_searches'] += len(search_terms)
        self.search_stats['total_results'] += len(final_results)
        
        # print(f"✅ {len(final_results)} risultati unici trovati")  # Debug rimosso
        return final_results
        
    def _generate_search_terms(self, subject: str) -> List[str]:
        """Genera termini di ricerca automaticamente con virgolette per ricerche esatte"""
        
        # Usa virgolette per ricerche esatte (Google syntax)
        # Le virgolette forzano Google a cercare la frase esatta
        base_terms = [
            f'"{subject}"',  # Ricerca esatta del nome
            f'"{subject}" LinkedIn',  # Nome esatto + LinkedIn
            f'"{subject}" site:linkedin.com',  # Nome esatto solo su LinkedIn
        ]
        
        # Se il nome ha più parole, aggiungi anche variazioni
        parts = subject.split()
        if len(parts) >= 2:
            # Aggiungi ricerca con nome e cognome separati
            first_name = parts[0]
            last_name = parts[-1]
            base_terms.append(f'"{first_name}" "{last_name}"')
        
        # FALLBACK: Aggiungi anche ricerca senza virgolette come ultima risorsa
        # (solo se la ricerca con virgolette non trova nulla)
        base_terms.append(subject)  # Senza virgolette
        base_terms.append(f'{subject} LinkedIn')  # Senza virgolette + LinkedIn
        
        return base_terms
        
    @retry_on_failure(max_retries=3, delay=1.0)
    async def _search_term(self, search_term: str) -> List[Dict[str, Any]]:
        """Esegue una ricerca per un termine specifico con caching"""
        
        if not validate_search_term(search_term):
            return []
        
        # Controlla cache
        cache_key = search_term.lower().strip()
        if cache_key in self._search_cache:
            cached_data = self._search_cache[cache_key]
            # Verifica se la cache è ancora valida
            if time.time() - cached_data['timestamp'] < self._cache_ttl:
                self.search_stats['cache_hits'] += 1
                return cached_data['results']
            else:
                # Cache scaduta, rimuovila
                del self._search_cache[cache_key]
            
        results = []
        
        # Prova multiple fonti (Google aggiunto per ricerche con virgolette)
        # Google è il migliore per ricerche esatte con virgolette
        # NOTA: Google potrebbe richiedere CAPTCHA, quindi DuckDuckGo è più affidabile
        search_engines = ['duckduckgo', 'bing', 'google']  # DuckDuckGo prima per affidabilità
        
        for engine in search_engines:
            try:
                # print(f"  🔍 Tentativo con {engine}...")  # Debug rimosso
                if engine == 'google':
                    engine_results = await self._search_google(search_term)
                elif engine == 'duckduckgo':
                    engine_results = await self._search_duckduckgo(search_term)
                elif engine == 'bing':
                    engine_results = await self._search_bing(search_term)
                else:
                    continue
                
                results.extend(engine_results)
                # print(f"  ✓ {engine}: {len(engine_results)} risultati")  # Debug rimosso
                
                # Se abbiamo abbastanza risultati, fermati
                if len(results) >= 5:
                    # print(f"  ✓ Raccolti {len(results)} risultati, sufficiente")  # Debug rimosso
                    break
                    
            except Exception as e:
                continue
        
        # Salva in cache
        if results:
            self._search_cache[cache_key] = {
                'results': results,
                'timestamp': time.time()
            }
                
        self.search_stats['successful_searches'] += 1
        return results
        
    async def _search_duckduckgo(self, search_term: str) -> List[Dict[str, Any]]:
        """Ricerca specifica su DuckDuckGo con supporto virgolette"""
        
        # quote_plus gestisce automaticamente le virgolette
        # Le virgolette vengono codificate come %22 nell'URL
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(search_term)}"
        
        # Log per debug
        # if '"' in search_term:
        #     print(f"  🔍 Ricerca esatta attivata (con virgolette)")  # Debug rimosso
        
        try:
            headers = {
                'User-Agent': self._get_random_user_agent(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Referer': 'https://duckduckgo.com/',
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=self.timeout) as response:
                    if response.status != 200:
                        return []
                    html = await response.text()
                    
                    # Controlla se c'è un CAPTCHA
                    if 'captcha' in html.lower() or 'recaptcha' in html.lower():
                        return []
                    
            soup = BeautifulSoup(html, 'html.parser')
            results = []
            
            # Prova diversi selettori
            result_divs = soup.find_all('div', class_='result')
            
            # Prova anche selettori alternativi
            if len(result_divs) == 0:
                result_divs = soup.find_all('div', class_='results_links')
            
            if len(result_divs) == 0:
                result_divs = soup.find_all('div', class_='web-result')
            
            for result in result_divs:
                try:
                    # Prova diversi selettori per titolo
                    title_elem = result.find('a', class_='result__a')
                    if not title_elem:
                        title_elem = result.find('a', class_='result-link')
                    if not title_elem:
                        title_elem = result.find('h2').find('a') if result.find('h2') else None
                    
                    # Prova diversi selettori per snippet
                    snippet_elem = result.find('a', class_='result__snippet')
                    if not snippet_elem:
                        snippet_elem = result.find('div', class_='result__snippet')
                    if not snippet_elem:
                        snippet_elem = result.find('div', class_='snippet')
                    
                    # URL
                    url_elem = result.find('a', class_='result__url')
                    if not url_elem:
                        url_elem = title_elem
                    
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''
                        url = url_elem.get('href', '') if url_elem else ''
                        
                        # Pulisci l'URL
                        if url.startswith('/l/?uddg='):
                            url = url.split('uddg=')[1]
                        if url.startswith('//duckduckgo.com/l/?uddg='):
                            url = url.split('uddg=')[1]
                            
                        results.append({
                            'title': title,
                            'snippet': snippet,
                            'url': url,
                            'source': 'duckduckgo',
                            'search_term': search_term,
                            'timestamp': time.time()
                        })
                        
                except (AttributeError, KeyError, TypeError) as e:
                    continue
            
            return results
            
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            return []
        except Exception as e:
            return []
            
    async def _search_google(self, search_term: str) -> List[Dict[str, Any]]:
        """Ricerca specifica su Google con supporto virgolette"""
        
        # Google supporta nativamente le virgolette per ricerche esatte
        url = f"https://www.google.com/search?q={quote_plus(search_term)}"
        
        try:
            headers = {
                'User-Agent': self._get_random_user_agent(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Referer': 'https://www.google.com/',
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=self.timeout) as response:
                    if response.status != 200:
                        return []
                    html = await response.text()
                    
                    # Controlla CAPTCHA
                    if 'captcha' in html.lower() or 'recaptcha' in html.lower():
                        return []
            
            soup = BeautifulSoup(html, 'html.parser')
            results = []
            
            # Selettori per risultati Google
            result_divs = soup.find_all('div', class_='g')
            
            for result in result_divs:
                try:
                    # Cerca il link
                    link_elem = result.find('a')
                    if not link_elem:
                        continue
                    
                    url = link_elem.get('href', '')
                    if not url or url.startswith('/search'):
                        continue
                    
                    # Cerca il titolo
                    title_elem = result.find('h3')
                    title = title_elem.get_text(strip=True) if title_elem else ''
                    
                    # Cerca lo snippet
                    snippet_elem = result.find('div', class_='VwiC3b')
                    if not snippet_elem:
                        snippet_elem = result.find('span', class_='aCOpRe')
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''
                    
                    if title and url:
                        results.append({
                            'title': title,
                            'snippet': snippet,
                            'url': url,
                            'source': 'google',
                            'search_term': search_term,
                            'timestamp': time.time()
                        })
                        
                except (AttributeError, KeyError, TypeError) as e:
                    continue
            
            return results
            
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            return []
        except Exception as e:
            return []
    
    async def _search_bing(self, search_term: str) -> List[Dict[str, Any]]:
        """Ricerca specifica su Bing con supporto virgolette"""
        
        # quote_plus gestisce automaticamente le virgolette
        # Le virgolette vengono codificate come %22 nell'URL
        url = f"https://www.bing.com/search?q={quote_plus(search_term)}"
        
        # Log per debug
        # if '"' in search_term:
        #     print(f"  🔍 Ricerca esatta attivata (con virgolette)")  # Debug rimosso
        
        try:
            headers = {
                'User-Agent': self._get_random_user_agent(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Referer': 'https://www.bing.com/',
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=self.timeout) as response:
                    if response.status != 200:
                        return []
                    html = await response.text()
                    
                    # Controlla se c'è un CAPTCHA
                    if 'captcha' in html.lower() or 'recaptcha' in html.lower():
                        return []
                    
            soup = BeautifulSoup(html, 'html.parser')
            results = []
            
            # Prova diversi selettori per risultati Bing
            result_items = soup.find_all('li', class_='b_algo')
            
            if len(result_items) == 0:
                result_items = soup.find_all('div', class_='b_algo')
            
            for result in result_items:
                try:
                    # Cerca il titolo
                    title_elem = None
                    h2 = result.find('h2')
                    if h2:
                        title_elem = h2.find('a')
                    
                    # Cerca lo snippet
                    snippet_elem = result.find('p')
                    if not snippet_elem:
                        snippet_elem = result.find('div', class_='b_caption')
                    
                    if title_elem:
                        results.append({
                            'title': title_elem.get_text(strip=True),
                            'snippet': snippet_elem.get_text(strip=True) if snippet_elem else '',
                            'url': title_elem.get('href', ''),
                            'source': 'bing',
                            'search_term': search_term,
                            'timestamp': time.time()
                        })
                        
                except (AttributeError, KeyError, TypeError) as e:
                    continue
            
            return results
            
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            return []
        except Exception as e:
            return []
            
    async def get_detailed_content(self, url: str, 
                                 max_content_length: int = 5000) -> Dict[str, Any]:
        """Ottiene il contenuto dettagliato da un URL"""
        
        if not validate_url(url):
            return {'error': 'URL non valido'}
            
        try:
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, 
                                     headers={'User-Agent': get_user_agent()},
                                     timeout=self.timeout) as response:
                    
                    if response.status != 200:
                        return {'error': f'HTTP {response.status}'}
                        
                    html = await response.text()
                    
            soup = BeautifulSoup(html, 'html.parser')
            
            # Rimuovi script e style
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
                
            # Estrae il testo principale
            text = soup.get_text()
            
            # Pulisce il testo
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            clean_text = ' '.join(chunk for chunk in chunks if chunk)
            
            # Estrae il titolo
            title = soup.find('title')
            title_text = title.get_text(strip=True) if title else "Nessun titolo"
            
            # Estrae meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            description = meta_desc.get('content', '') if meta_desc else ''
            
            # Estrae meta keywords
            meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
            keywords = meta_keywords.get('content', '') if meta_keywords else ''
            
            return {
                'title': title_text,
                'description': description,
                'keywords': keywords,
                'content': clean_text[:max_content_length],
                'url': url,
                'length': len(clean_text),
                'domain': urlparse(url).netloc,
                'timestamp': time.time()
            }
            
        except Exception as e:
            return {
                'title': 'Errore',
                'description': '',
                'content': f'Errore nel download: {e}',
                'url': url,
                'length': 0,
                'error': str(e)
            }
            
    def _remove_duplicates(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rimuove risultati duplicati basandosi sull'URL e titolo"""
        
        seen_urls = set()
        seen_titles = set()
        unique_results = []
        
        for result in results:
            url = result.get('url', '')
            title = result.get('title', '').lower()
            
            # Controlla duplicati per URL e titolo simile
            if url and url not in seen_urls:
                # Controlla anche titoli molto simili
                title_similar = any(self._titles_similar(title, seen_title) 
                                  for seen_title in seen_titles)
                
                if not title_similar:
                    seen_urls.add(url)
                    seen_titles.add(title)
                    unique_results.append(result)
                    
        return unique_results
        
    def _titles_similar(self, title1: str, title2: str, threshold: float = 0.8) -> bool:
        """Controlla se due titoli sono simili"""
        
        if not title1 or not title2:
            return False
            
        # Normalizza i titoli
        title1 = title1.lower().strip()
        title2 = title2.lower().strip()
        
        # Controlla se uno è contenuto nell'altro
        if title1 in title2 or title2 in title1:
            return True
            
        # Calcola similarità semplice basata su parole comuni
        words1 = set(title1.split())
        words2 = set(title2.split())
        
        if not words1 or not words2:
            return False
            
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        similarity = len(intersection) / len(union)
        return similarity >= threshold
        
    def format_search_results(self, results: List[Dict[str, Any]], 
                            include_metadata: bool = True) -> str:
        """Formatta i risultati di ricerca in un testo leggibile"""
        
        if not results:
            return "Nessun risultato trovato."
            
        formatted = "RISULTATI RICERCA\n"
        formatted += "=" * 50 + "\n\n"
        
        for i, result in enumerate(results, 1):
            formatted += f"{i}. {result.get('title', 'Nessun titolo')}\n"
            formatted += f"   {result.get('snippet', 'Nessuna descrizione')}\n"
            formatted += f"   URL: {result.get('url', 'N/A')}\n"
            
            if include_metadata:
                formatted += f"   Fonte: {result.get('source', 'N/A')}\n"
                if result.get('search_term'):
                    formatted += f"   Termine: {result['search_term']}\n"
                    
            formatted += "\n"
            
        if include_metadata:
            formatted += f"Trovati {len(results)} risultati\n"
            
        return formatted
        
    def get_search_stats(self) -> Dict[str, Any]:
        """Ottiene statistiche delle ricerche"""
        
        success_rate = 0
        if self.search_stats['total_searches'] > 0:
            success_rate = (self.search_stats['successful_searches'] / 
                          self.search_stats['total_searches']) * 100
            
        return {
            **self.search_stats,
            'success_rate': round(success_rate, 2),
            'avg_results_per_search': (
                self.search_stats['total_results'] / 
                max(1, self.search_stats['successful_searches'])
            )
        }
        
    def reset_stats(self):
        """Reset delle statistiche"""
        self.search_stats = {
            'total_searches': 0,
            'successful_searches': 0,
            'failed_searches': 0,
            'total_results': 0,
            'cache_hits': 0
        }
    
    def clear_cache(self):
        """Pulisce la cache dei risultati di ricerca"""
        self._search_cache.clear()
        
    async def test_connection(self) -> bool:
        """Testa la connessione ai motori di ricerca"""
        
        test_term = "test"
        
        try:
            results = await self._search_duckduckgo(test_term)
            return len(results) > 0
        except Exception as e:
            return False

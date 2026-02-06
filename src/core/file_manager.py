"""
Gestore file per salvataggio e backup dei dati
Gestisce file txt, JSON e backup automatici
"""

import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

class FileManager:
    """Gestore centralizzato per file e backup"""
    
    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        
        # Directory di default
        self.output_dir = Path(config_manager.get('output_dir', './data/output')) if config_manager else Path('./data/output')
        self.backup_dir = Path(config_manager.get('backup_dir', './data/backups')) if config_manager else Path('./data/backups')
        
        # Crea directory se non esistono
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # File di default
        self.default_output_file = self.output_dir / "paolo_del_checco_info.txt"
        
    def save_research_results(self, 
                            search_results: List[Dict[str, Any]], 
                            analysis: Dict[str, Any] = None,
                            summary: str = "",
                            subject: str = "paolo_del_checco",
                            format_type: str = "txt") -> str:
        """Salva i risultati di ricerca in formato specificato"""
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if format_type.lower() == "txt":
            return self._save_txt_format(search_results, analysis, summary, subject, timestamp)
        elif format_type.lower() == "json":
            return self._save_json_format(search_results, analysis, summary, subject, timestamp)
        elif format_type.lower() == "both":
            txt_file = self._save_txt_format(search_results, analysis, summary, subject, timestamp)
            json_file = self._save_json_format(search_results, analysis, summary, subject, timestamp)
            return f"{txt_file}, {json_file}"
        else:
            raise ValueError(f"Formato non supportato: {format_type}")
            
    def _save_txt_format(self, search_results: List[Dict[str, Any]], 
                        analysis: Dict[str, Any], summary: str, 
                        subject: str, timestamp: str) -> str:
        """Salva in formato txt leggibile"""
        
        # Genera nome file
        safe_subject = "".join(c for c in subject if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_subject = safe_subject.replace(' ', '_').lower()
        filename = self.output_dir / f"{safe_subject}_info_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        content = self._generate_txt_content(search_results, analysis, summary, subject, timestamp)
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
                
            print(f"[OK] Informazioni salvate in: {filename}")
            return str(filename)
            
        except Exception as e:
            print(f"[ERR] Errore nel salvataggio TXT: {e}")
            return ""
            
    def _save_json_format(self, search_results: List[Dict[str, Any]], 
                         analysis: Dict[str, Any], summary: str, 
                         subject: str, timestamp: str) -> str:
        """Salva in formato JSON strutturato"""
        
        # Genera nome file
        safe_subject = "".join(c for c in subject if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_subject = safe_subject.replace(' ', '_').lower()
        filename = self.output_dir / f"{safe_subject}_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        data = {
            'metadata': {
                'subject': subject,
                'generated_at': timestamp,
                'tool_version': '1.0',
                'total_results': len(search_results),
                'sources_count': len(set(r.get('source', 'unknown') for r in search_results)),
                'search_terms_count': len(set(r.get('search_term', '') for r in search_results))
            },
            'summary': summary,
            'analysis': analysis or {},
            'search_results': search_results
        }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            print(f"[OK] Dati JSON salvati in: {filename}")
            return str(filename)
            
        except Exception as e:
            print(f"[ERR] Errore nel salvataggio JSON: {e}")
            return ""
            
    def _generate_txt_content(self, search_results: List[Dict[str, Any]], 
                             analysis: Dict[str, Any], summary: str, 
                             subject: str, timestamp: str) -> str:
        """Genera il contenuto del file txt formattato"""
        
        # Header personalizzato
        subject_display = subject.replace('_', ' ').title()
        
        content = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        INFORMAZIONI SU {subject_display:<50} ║
║                            Generato il: {timestamp:<25} ║
╚══════════════════════════════════════════════════════════════════════════════╝

"""
        
        # Riassunto generale
        if summary:
            content += "RIASSUNTO GENERALE\n"
            content += "=" * 50 + "\n"
            content += summary + "\n\n"
            
        # Analisi AI - VERSIONE COMPLETA E DETTAGLIATA
        if analysis:
            content += "ANALISI AI DEL TARGET\n"
            content += "=" * 80 + "\n\n"
            
            # Nome
            if analysis.get('name'):
                content += f"NOME: {analysis.get('name')}\n\n"
            
            # Occupazione/Lavoro
            if analysis.get('work'):
                content += f"OCCUPAZIONE:\n"
                content += f"{analysis.get('work')}\n\n"
            
            # Posizione
            if analysis.get('location'):
                content += f"POSIZIONE: {analysis.get('location')}\n\n"
            
            # Riassunto generale
            if analysis.get('summary'):
                content += f"RIASSUNTO:\n"
                content += f"{analysis.get('summary')}\n\n"
            
            # Spiegazione dettagliata (nuovo campo)
            if analysis.get('explanation'):
                content += f"SPIEGAZIONE DETTAGLIATA:\n"
                content += f"{analysis.get('explanation')}\n\n"
            
            # Sentiment
            if analysis.get('sentiment'):
                content += f"SENTIMENT: {analysis.get('sentiment')}\n\n"
            
            # Skills/Competenze
            if analysis.get('skills'):
                content += "COMPETENZE:\n"
                skills = analysis['skills']
                if isinstance(skills, list):
                    for i, skill in enumerate(skills, 1):
                        content += f"  {i}. {skill}\n"
                else:
                    content += f"{skills}\n"
                content += "\n"
            
            # Punti chiave
            if analysis.get('key_points'):
                content += "PUNTI CHIAVE:\n"
                for i, point in enumerate(analysis['key_points'], 1):
                    content += f"  {i}. {point}\n"
                content += "\n"
            
            # Realizzazioni chiave (nuovo campo)
            if analysis.get('key_achievements'):
                content += "REALIZZAZIONI CHIAVE:\n"
                achievements = analysis['key_achievements']
                if isinstance(achievements, list):
                    for i, achievement in enumerate(achievements, 1):
                        content += f"  {i}. {achievement}\n"
                else:
                    content += f"{achievements}\n"
                content += "\n"
            
            # Interessi
            if analysis.get('interests'):
                content += "INTERESSI:\n"
                interests = analysis['interests']
                if isinstance(interests, list):
                    for interest in interests:
                        content += f"  - {interest}\n"
                else:
                    content += f"{interests}\n"
                content += "\n"
            
            # Educazione
            if analysis.get('education'):
                content += f"EDUCAZIONE:\n"
                content += f"{analysis.get('education')}\n\n"
            
            # Esperienze
            if analysis.get('experience'):
                content += f"ESPERIENZA:\n"
                content += f"{analysis.get('experience')}\n\n"
            
            # Progetti
            if analysis.get('projects'):
                content += "PROGETTI:\n"
                projects = analysis['projects']
                if isinstance(projects, list):
                    for project in projects:
                        content += f"  - {project}\n"
                else:
                    content += f"{projects}\n"
                content += "\n"
            
            # Social media
            if analysis.get('social_media'):
                content += "SOCIAL MEDIA:\n"
                social = analysis['social_media']
                if isinstance(social, dict):
                    for platform, url in social.items():
                        content += f"  {platform}: {url}\n"
                else:
                    content += f"{social}\n"
                content += "\n"
            
            # Contatti
            if analysis.get('contacts'):
                content += "CONTATTI:\n"
                contacts = analysis['contacts']
                if isinstance(contacts, dict):
                    for tipo, valore in contacts.items():
                        content += f"  {tipo}: {valore}\n"
                else:
                    content += f"{contacts}\n"
                content += "\n"
            
            # Entità menzionate
            if analysis.get('entities'):
                content += "ENTITA' MENZIONATE:\n"
                for entity in analysis['entities']:
                    content += f"  - {entity}\n"
                content += "\n"
            
            # Vulnerabilità/Note per Social Engineering (se presenti)
            if analysis.get('vulnerabilities'):
                content += "VULNERABILITA'/NOTE:\n"
                vulnerabilities = analysis['vulnerabilities']
                if isinstance(vulnerabilities, list):
                    for vuln in vulnerabilities:
                        content += f"  - {vuln}\n"
                else:
                    content += f"{vulnerabilities}\n"
                content += "\n"
            
            # Informazioni aggiuntive generiche
            other_keys = [k for k in analysis.keys() if k not in [
                'name', 'work', 'location', 'summary', 'sentiment', 'skills',
                'key_points', 'interests', 'education', 'experience', 'projects',
                'social_media', 'contacts', 'entities', 'vulnerabilities'
            ]]
            
            if other_keys:
                content += "INFORMAZIONI AGGIUNTIVE:\n"
                for key in other_keys:
                    value = analysis[key]
                    # Formatta il nome della chiave
                    display_key = key.replace('_', ' ').title()
                    
                    if isinstance(value, (list, dict)):
                        content += f"  {display_key}:\n"
                        if isinstance(value, list):
                            for item in value:
                                content += f"    - {item}\n"
                        else:
                            for k, v in value.items():
                                content += f"    {k}: {v}\n"
                    else:
                        content += f"  {display_key}: {value}\n"
                content += "\n"
                
        # Risultati di ricerca dettagliati
        content += "RISULTATI RICERCA DETTAGLIATI\n"
        content += "=" * 50 + "\n\n"
        
        if not search_results:
            content += "Nessun risultato trovato.\n"
        else:
            for i, result in enumerate(search_results, 1):
                content += f"{i}. {result.get('title', 'Nessun titolo')}\n"
                content += f"   URL: {result.get('url', 'N/A')}\n"
                content += f"   Fonte: {result.get('source', 'N/A')}\n"
                content += f"   Termine di ricerca: {result.get('search_term', 'N/A')}\n"
                content += f"   Anteprima: {result.get('snippet', 'N/A')}\n"
                
                # Contenuto dettagliato se disponibile
                if 'content' in result and result['content']:
                    content += f"   Contenuto: {result['content'][:500]}...\n"
                    
                content += "\n" + "-" * 80 + "\n\n"
                
        # Statistiche
        content += "STATISTICHE\n"
        content += "=" * 50 + "\n"
        content += f"Numero totale di risultati: {len(search_results)}\n"
        content += f"Fonti utilizzate: {len(set(r.get('source', 'unknown') for r in search_results))}\n"
        content += f"Termini di ricerca utilizzati: {len(set(r.get('search_term', '') for r in search_results))}\n"
        
        # Metadata
        content += "\nMETADATA\n"
        content += "=" * 50 + "\n"
        content += f"Data di generazione: {timestamp}\n"
        content += f"File generato da: Social Engineering Research Tool\n"
        content += f"Versione: 1.0\n"
        content += f"Soggetto: {subject_display}\n"
        
        return content
        
    def save_ai_analysis(self, analysis: Dict[str, Any], subject: str, 
                        search_results_count: int = 0) -> str:
        """
        Salva SOLO l'analisi AI del target in un file TXT dedicato e leggibile
        
        Args:
            analysis: Dizionario con l'analisi AI completa
            subject: Nome del soggetto analizzato
            search_results_count: Numero di risultati di ricerca analizzati
            
        Returns:
            Path del file salvato
        """
        # Genera nome file
        safe_subject = "".join(c for c in subject if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_subject = safe_subject.replace(' ', '_').lower()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = self.output_dir / f"{safe_subject}_ai_analysis_{timestamp}.txt"
        
        # Genera contenuto
        timestamp_readable = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subject_display = subject.replace('_', ' ').title()
        
        content = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    ANALISI AI - {subject_display:<50} ║
║                            Generato il: {timestamp_readable:<25} ║
╚══════════════════════════════════════════════════════════════════════════════╝

ANALISI INTELLIGENTE DEL TARGET
Questa analisi è stata generata automaticamente dal modello LLM analizzando
{search_results_count} fonti online pubbliche.

{"=" * 80}

"""
        
        if not analysis:
            content += "Nessuna analisi disponibile.\n"
        else:
            # Nome
            if analysis.get('name'):
                content += f"IDENTITA'\n"
                content += f"{'-' * 80}\n"
                content += f"Nome: {analysis.get('name')}\n\n"
            
            # Occupazione/Lavoro
            if analysis.get('work'):
                content += f"OCCUPAZIONE E RUOLO PROFESSIONALE\n"
                content += f"{'-' * 80}\n"
                content += f"{analysis.get('work')}\n\n"
            
            # Posizione
            if analysis.get('location'):
                content += f"LOCALIZZAZIONE\n"
                content += f"{'-' * 80}\n"
                content += f"{analysis.get('location')}\n\n"
            
            # Riassunto generale (SEZIONE PRINCIPALE)
            if analysis.get('summary'):
                content += f"PROFILO GENERALE\n"
                content += f"{'-' * 80}\n"
                content += f"{analysis.get('summary')}\n\n"
            
            # Skills/Competenze
            if analysis.get('skills'):
                content += f"COMPETENZE TECNICHE E PROFESSIONALI\n"
                content += f"{'-' * 80}\n"
                skills = analysis['skills']
                if isinstance(skills, list):
                    for i, skill in enumerate(skills, 1):
                        content += f"  {i}. {skill}\n"
                else:
                    content += f"{skills}\n"
                content += "\n"
            
            # Punti chiave
            if analysis.get('key_points'):
                content += f"INFORMAZIONI CHIAVE\n"
                content += f"{'-' * 80}\n"
                for i, point in enumerate(analysis['key_points'], 1):
                    content += f"  {i}. {point}\n"
                content += "\n"
            
            # Interessi
            if analysis.get('interests'):
                content += f"INTERESSI E PASSIONI\n"
                content += f"{'-' * 80}\n"
                interests = analysis['interests']
                if isinstance(interests, list):
                    for interest in interests:
                        content += f"  - {interest}\n"
                else:
                    content += f"{interests}\n"
                content += "\n"
            
            # Educazione
            if analysis.get('education'):
                content += f"FORMAZIONE ACCADEMICA\n"
                content += f"{'-' * 80}\n"
                content += f"{analysis.get('education')}\n\n"
            
            # Esperienze
            if analysis.get('experience'):
                content += f"ESPERIENZA PROFESSIONALE\n"
                content += f"{'-' * 80}\n"
                content += f"{analysis.get('experience')}\n\n"
            
            # Progetti
            if analysis.get('projects'):
                content += f"PROGETTI E REALIZZAZIONI\n"
                content += f"{'-' * 80}\n"
                projects = analysis['projects']
                if isinstance(projects, list):
                    for project in projects:
                        content += f"  - {project}\n"
                else:
                    content += f"{projects}\n"
                content += "\n"
            
            # Social media
            if analysis.get('social_media'):
                content += f"PRESENZA ONLINE E SOCIAL MEDIA\n"
                content += f"{'-' * 80}\n"
                social = analysis['social_media']
                if isinstance(social, dict):
                    for platform, url in social.items():
                        content += f"  {platform.title()}: {url}\n"
                else:
                    content += f"{social}\n"
                content += "\n"
            
            # Contatti
            if analysis.get('contacts'):
                content += f"INFORMAZIONI DI CONTATTO\n"
                content += f"{'-' * 80}\n"
                contacts = analysis['contacts']
                if isinstance(contacts, dict):
                    for tipo, valore in contacts.items():
                        content += f"  {tipo.title()}: {valore}\n"
                else:
                    content += f"{contacts}\n"
                content += "\n"
            
            # Entità menzionate
            if analysis.get('entities'):
                content += f"ORGANIZZAZIONI E ENTITA' ASSOCIATE\n"
                content += f"{'-' * 80}\n"
                for entity in analysis['entities']:
                    content += f"  - {entity}\n"
                content += "\n"
            
            # Sentiment
            if analysis.get('sentiment'):
                content += f"SENTIMENT E PERCEZIONE PUBBLICA\n"
                content += f"{'-' * 80}\n"
                content += f"{analysis.get('sentiment')}\n\n"
            
            # Vulnerabilità/Note per Social Engineering (se presenti)
            if analysis.get('vulnerabilities'):
                content += f"NOTE E CONSIDERAZIONI PER APPROCCIO\n"
                content += f"{'-' * 80}\n"
                vulnerabilities = analysis['vulnerabilities']
                if isinstance(vulnerabilities, list):
                    for vuln in vulnerabilities:
                        content += f"  - {vuln}\n"
                else:
                    content += f"{vulnerabilities}\n"
                content += "\n"
            
            # Informazioni aggiuntive generiche
            other_keys = [k for k in analysis.keys() if k not in [
                'name', 'work', 'location', 'summary', 'sentiment', 'skills',
                'key_points', 'interests', 'education', 'experience', 'projects',
                'social_media', 'contacts', 'entities', 'vulnerabilities'
            ]]
            
            if other_keys:
                content += f"ALTRE INFORMAZIONI RILEVATE\n"
                content += f"{'-' * 80}\n"
                for key in other_keys:
                    value = analysis[key]
                    # Formatta il nome della chiave
                    display_key = key.replace('_', ' ').title()
                    
                    if isinstance(value, (list, dict)):
                        content += f"\n{display_key}:\n"
                        if isinstance(value, list):
                            for item in value:
                                content += f"  - {item}\n"
                        else:
                            for k, v in value.items():
                                content += f"  {k}: {v}\n"
                    else:
                        content += f"{display_key}: {value}\n"
                content += "\n"
        
        # Footer
        content += f"\n{'=' * 80}\n"
        content += f"METADATA\n"
        content += f"{'-' * 80}\n"
        content += f"Soggetto analizzato: {subject_display}\n"
        content += f"Fonti analizzate: {search_results_count}\n"
        content += f"Data analisi: {timestamp_readable}\n"
        content += f"Generato da: Social Engineering Research Tool v1.0\n"
        content += f"Modello AI: Ollama LLM\n"
        content += f"\nNOTA: Queste informazioni provengono da fonti pubbliche online.\n"
        content += f"      Utilizzare solo per scopi legittimi e nel rispetto della privacy.\n"
        
        # Salva il file
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
                
            print(f"[FILE] Analisi AI salvata in: {filename}")
            return str(filename)
            
        except Exception as e:
            print(f"[ERR] Errore nel salvataggio analisi AI: {e}")
            return ""
    
    def save_custom_data(self, data: Dict[str, Any], filename: str = None, 
                        format_type: str = "json") -> str:
        """Salva dati personalizzati"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"custom_data_{timestamp}.{format_type}"
            
        filepath = self.output_dir / filename
        
        try:
            if format_type.lower() == "json":
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            elif format_type.lower() == "txt":
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(str(data))
            else:
                raise ValueError(f"Formato non supportato: {format_type}")
                
            print(f"[OK] Dati personalizzati salvati in: {filepath}")
            return str(filepath)
            
        except Exception as e:
            print(f"[ERR] Errore nel salvataggio dati personalizzati: {e}")
            return ""
            
    def load_data(self, filename: str, format_type: str = "auto") -> Dict[str, Any]:
        """Carica dati da file"""
        filepath = Path(filename)
        
        if not filepath.exists():
            print(f"[ERR] File {filename} non trovato")
            return {}
            
        # Auto-detect format se non specificato
        if format_type == "auto":
            format_type = filepath.suffix.lower().lstrip('.')
            
        try:
            if format_type == "json":
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            elif format_type == "txt":
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = {"content": f.read()}
            else:
                raise ValueError(f"Formato non supportato: {format_type}")
                
            print(f"[OK] Dati caricati da: {filepath}")
            return data
            
        except Exception as e:
            print(f"[ERR] Errore nel caricamento dati: {e}")
            return {}
            
    def create_backup(self, source_file: Union[str, Path], 
                     backup_name: str = None) -> str:
        """Crea un backup del file"""
        source_path = Path(source_file)
        
        if not source_path.exists():
            print(f"[ERR] File {source_file} non trovato per il backup")
            return ""
            
        # Genera nome backup
        if backup_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{source_path.stem}_backup_{timestamp}{source_path.suffix}"
            
        backup_path = self.backup_dir / backup_name
        
        try:
            shutil.copy2(source_path, backup_path)
            print(f"[OK] Backup creato: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            print(f"[ERR] Errore nella creazione backup: {e}")
            return ""
            
    def append_to_file(self, content: str, filename: Union[str, Path]) -> bool:
        """Aggiunge contenuto al file esistente"""
        filepath = Path(filename)
        
        try:
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(f"\n\n{content}\n")
                
            print(f"[OK] Contenuto aggiunto a: {filepath}")
            return True
            
        except Exception as e:
            print(f"[ERR] Errore nell'aggiunta al file: {e}")
            return False
            
    def get_file_info(self, filename: Union[str, Path]) -> Dict[str, Any]:
        """Ottiene informazioni dettagliate sul file"""
        filepath = Path(filename)
        
        if not filepath.exists():
            return {'exists': False, 'path': str(filepath)}
            
        stat = filepath.stat()
        
        return {
            'exists': True,
            'path': str(filepath.absolute()),
            'size_bytes': stat.st_size,
            'size_mb': round(stat.st_size / (1024 * 1024), 2),
            'size_kb': round(stat.st_size / 1024, 2),
            'created': datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
            'modified': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            'extension': filepath.suffix,
            'name': filepath.name,
            'stem': filepath.stem,
            'parent': str(filepath.parent)
        }
        
    def list_files(self, directory: Union[str, Path] = None, 
                  pattern: str = "*", sort_by: str = "modified") -> List[Dict[str, Any]]:
        """Lista i file in una directory con informazioni"""
        if directory is None:
            directory = self.output_dir
        else:
            directory = Path(directory)
            
        if not directory.exists():
            return []
            
        files = []
        
        for filepath in directory.glob(pattern):
            if filepath.is_file():
                file_info = self.get_file_info(filepath)
                files.append(file_info)
                
        # Ordina i file
        if sort_by == "modified":
            files.sort(key=lambda x: x.get('modified', ''), reverse=True)
        elif sort_by == "size":
            files.sort(key=lambda x: x.get('size_bytes', 0), reverse=True)
        elif sort_by == "name":
            files.sort(key=lambda x: x.get('name', ''))
            
        return files
        
    def cleanup_old_files(self, directory: Union[str, Path] = None, 
                         days_old: int = 30, pattern: str = "*") -> int:
        """Rimuove file vecchi dalla directory"""
        if directory is None:
            directory = self.output_dir
        else:
            directory = Path(directory)
            
        if not directory.exists():
            return 0
            
        cutoff_time = datetime.now().timestamp() - (days_old * 24 * 60 * 60)
        removed_count = 0
        
        for filepath in directory.glob(pattern):
            if filepath.is_file() and filepath.stat().st_mtime < cutoff_time:
                try:
                    filepath.unlink()
                    removed_count += 1
                    print(f"[DEL] Rimosso file vecchio: {filepath.name}")
                except Exception as e:
                    print(f"[ERR] Errore nella rimozione di {filepath.name}: {e}")
                    
        if removed_count > 0:
            print(f"[OK] Rimossi {removed_count} file vecchi (> {days_old} giorni)")
            
        return removed_count

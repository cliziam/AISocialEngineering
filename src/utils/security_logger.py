"""
Security logging utility per tracciare eventi di sicurezza
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional


class SecurityLogger:
    """Logger dedicato per eventi di sicurezza"""

    def __init__(self, log_dir: str = "./logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Setup logger
        self.logger = logging.getLogger('security')
        self.logger.setLevel(logging.INFO)

        # File handler per log di sicurezza
        log_file = self.log_dir / \
            f"security_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)

        # Formato dettagliato per sicurezza
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)

        # Evita duplicati
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)

    def log_injection_attempt(self, input_type: str, input_value: str,
                              attack_type: str, source: Optional[str] = None):
        """Log tentativo di injection rilevato"""
        self.logger.warning(
            f"INJECTION_ATTEMPT | Type: {attack_type} | Input: {input_type} | "
            f"Value: {input_value[:100]} | Source: {source or 'unknown'}"
        )

    def log_suspicious_activity(self, activity: str, details: str):
        """Log attività sospetta"""
        self.logger.warning(f"SUSPICIOUS_ACTIVITY | {activity} | {details}")

    def log_authentication_failure(self, service: str, reason: str):
        """Log fallimento autenticazione"""
        self.logger.warning(
            f"AUTH_FAILURE | Service: {service} | Reason: {reason}")

    def log_rate_limit_exceeded(self, service: str, limit: int):
        """Log superamento rate limit"""
        self.logger.warning(
            f"RATE_LIMIT_EXCEEDED | Service: {service} | Limit: {limit}")

    def log_data_access(self, resource: str, action: str, success: bool):
        """Log accesso a dati sensibili"""
        status = "SUCCESS" if success else "FAILURE"
        self.logger.info(
            f"DATA_ACCESS | {status} | Resource: {resource} | Action: {action}")

    def log_configuration_change(
            self,
            setting: str,
            old_value: str,
            new_value: str):
        """Log modifica configurazione"""
        self.logger.info(
            f"CONFIG_CHANGE | Setting: {setting} | "
            f"Old: {old_value} | New: {new_value}"
        )

    def log_file_operation(
            self,
            operation: str,
            file_path: str,
            success: bool):
        """Log operazione su file"""
        status = "SUCCESS" if success else "FAILURE"
        self.logger.info(
            f"FILE_OP | {status} | Op: {operation} | Path: {file_path}")

    def log_network_request(
            self,
            url: str,
            method: str,
            status_code: Optional[int] = None):
        """Log richiesta di rete"""
        self.logger.info(
            f"NETWORK_REQUEST | Method: {method} | URL: {url} | "
            f"Status: {status_code or 'N/A'}"
        )

    def log_error(self, error_type: str, message: str,
                  stack_trace: Optional[str] = None):
        """Log errore di sicurezza"""
        log_msg = f"SECURITY_ERROR | Type: {error_type} | Message: {message}"
        if stack_trace:
            log_msg += f" | Trace: {stack_trace[:200]}"
        self.logger.error(log_msg)


# Singleton instance
_security_logger = None


def get_security_logger(log_dir: str = "./logs") -> SecurityLogger:
    """Ottiene l'istanza singleton del security logger"""
    global _security_logger
    if _security_logger is None:
        _security_logger = SecurityLogger(log_dir)
    return _security_logger

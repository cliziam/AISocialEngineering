"""
Moduli core del sistema
Contiene la logica principale per hardware, file management e configurazione
"""

from .hardware_optimizer import HardwareOptimizer
from .file_manager import FileManager
from .config_manager import ConfigManager

__all__ = ['HardwareOptimizer', 'FileManager', 'ConfigManager']

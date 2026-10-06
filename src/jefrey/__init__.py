"""Jefrey - Assistente Pessoal de IA Avançado."""
__version__ = "0.10.0"

try:  # carimbo gravado pelo build_exe.bat (data e hora + commit); em desenvolvimento nao existe
    from src.jefrey.build_info import BUILD
except Exception:
    BUILD = "desenvolvimento"
__author__ = "Pedro"
__all__ = ["__version__", "BUILD"]
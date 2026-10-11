"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/backup.py."""
import sys

from src.jefrey.adapters.outbound import backup as _moved

sys.modules[__name__] = _moved

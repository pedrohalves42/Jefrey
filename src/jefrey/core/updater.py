"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/updater.py."""
import sys

from src.jefrey.adapters.outbound import updater as _moved

sys.modules[__name__] = _moved

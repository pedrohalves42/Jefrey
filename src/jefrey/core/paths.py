"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/paths.py."""
import sys

from src.jefrey.adapters.outbound import paths as _moved

sys.modules[__name__] = _moved

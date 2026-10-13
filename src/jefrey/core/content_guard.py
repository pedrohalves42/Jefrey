"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/content_guard.py."""
import sys

from src.jefrey.adapters.outbound import content_guard as _moved

sys.modules[__name__] = _moved

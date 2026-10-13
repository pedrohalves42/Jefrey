"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/skill_prefs.py."""
import sys

from src.jefrey.adapters.outbound import skill_prefs as _moved

sys.modules[__name__] = _moved

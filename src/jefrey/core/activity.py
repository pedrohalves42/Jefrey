"""Atalho de compatibilidade: este modulo agora mora em application/activity.py."""
import sys

from src.jefrey.application import activity as _moved

sys.modules[__name__] = _moved

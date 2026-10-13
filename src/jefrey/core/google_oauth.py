"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/google_oauth.py."""
import sys

from src.jefrey.adapters.outbound import google_oauth as _moved

sys.modules[__name__] = _moved

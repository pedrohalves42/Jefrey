"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/webread.py."""
import sys

from src.jefrey.adapters.outbound import webread as _moved

sys.modules[__name__] = _moved

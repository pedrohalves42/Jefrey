"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/structured_logging.py."""
import sys

from src.jefrey.adapters.outbound import structured_logging as _moved

sys.modules[__name__] = _moved

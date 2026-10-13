"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/db.py."""
import sys

from src.jefrey.adapters.outbound import db as _moved

sys.modules[__name__] = _moved

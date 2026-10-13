"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/models.py."""
import sys

from src.jefrey.adapters.outbound import models as _moved

sys.modules[__name__] = _moved

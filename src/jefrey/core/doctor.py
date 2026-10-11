"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/doctor.py."""
import sys

from src.jefrey.adapters.outbound import doctor as _moved

sys.modules[__name__] = _moved

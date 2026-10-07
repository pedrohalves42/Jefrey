"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/sysinfo.py."""
import sys

from src.jefrey.adapters.outbound import sysinfo as _moved

sys.modules[__name__] = _moved

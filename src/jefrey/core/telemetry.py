"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/telemetry.py."""
import sys

from src.jefrey.adapters.outbound import telemetry as _moved

sys.modules[__name__] = _moved

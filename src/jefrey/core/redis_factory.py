"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/redis_factory.py."""
import sys

from src.jefrey.adapters.outbound import redis_factory as _moved

sys.modules[__name__] = _moved

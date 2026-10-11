"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/local_redis.py."""
import sys

from src.jefrey.adapters.outbound import local_redis as _moved

sys.modules[__name__] = _moved

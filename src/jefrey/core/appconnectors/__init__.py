"""Atalho de compatibilidade: o pacote agora mora em adapters/outbound/appconnectors."""
import sys

from src.jefrey.adapters.outbound import appconnectors as _moved
from src.jefrey.adapters.outbound.appconnectors import blender as _blender

sys.modules[__name__ + ".blender"] = _blender
sys.modules[__name__] = _moved

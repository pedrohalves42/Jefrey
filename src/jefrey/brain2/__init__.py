"""Brain2 - segundo cerebro deliberativo (Sprint D, DIFF3).

Arquitetura: Cerebro 1 (reativo, <1.5s) -> Redis Stream jefrey:brain2:queue
             -> Cerebro 2 (deliberativo, consolidator/planner/reflector/learner)
             + Ollama qwen2.5:0.5b / nomic-embed-text 768d
"""

from .queue import Brain2Queue, get_brain2_queue
from .consolidator import Consolidator
from .planner import Planner
from .reflector import Reflector
from .learner import Learner
from .service import Brain2Service

__all__ = [
    "Brain2Queue",
    "get_brain2_queue",
    "Consolidator",
    "Planner",
    "Reflector",
    "Learner",
    "Brain2Service",
]

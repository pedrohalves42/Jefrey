"""Brain2Service - loop deliberativo: XREADGROUP + consolidator/planner/reflector/learner + WS brain2_insight.

DIFF3 esqueleto: roda como container separado jefrey-brain2; se Redis/Ollama cairem, degrada sem quebrar Cerebro 1.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, Optional

from .queue import STREAM_KEY, GROUP, CONSUMER_PREFIX
from .consolidator import Consolidator
from .planner import Planner
from .reflector import Reflector
from .learner import Learner

logger = logging.getLogger(__name__)


class Brain2Service:
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("JEFREY_REDIS__URL", "redis://:jefrey@localhost:6379/0")
        self.consolidator = Consolidator()
        self.planner = Planner()
        self.reflector = Reflector()
        self.learner = Learner()
        self._stop = False
        self.processed = 0
        self.errors = 0

    def stop(self):
        self._stop = True

    def _get_redis(self):
        try:
            import redis.asyncio as redis  # type: ignore

            return redis.from_url(self.redis_url, decode_responses=True)
        except Exception as e:
            logger.warning("brain2 redis unavailable: %s", e)
            return None

    async def _ensure_group(self, r):
        try:
            await r.xgroup_create(STREAM_KEY, GROUP, id="0", mkstream=True)
            logger.info("brain2 group %s created on %s", GROUP, STREAM_KEY)
        except Exception as e:
            # BUSYGROUP already exists
            if "BUSYGROUP" not in str(e):
                logger.debug("brain2 xgroup_create: %s", e)

    async def _publish_insight(self, r, user_id: str, payload: Dict[str, Any]):
        """Publica brain2_insight via WS broadcast (se api estiver no mesmo Redis) e via Stream de insights."""
        try:
            # Stream de insights por user_id (para frontend puxar via WS ou polling)
            await r.xadd(f"jefrey:brain2:insights:{user_id}", {"json": json.dumps(payload, ensure_ascii=False)}, maxlen=1000, approximate=True)
        except Exception as e:
            logger.debug("brain2 publish insight failed: %s", e)
        # Tentativa de push via API WS manager se rodando in-process (sera via Redis pubsub no futuro)
        try:
            from src.jefrey.api.ws import get_ws_manager  # type: ignore

            mgr = get_ws_manager()
            # broadcast so funciona se Brain2 rodar no mesmo processo da API (nao e o caso em container separado)
            # Mantido para compatibilidade quando Brain2 for sidecar
            await mgr.broadcast({"type": "brain2_insight", "user_id": user_id, **payload})
        except Exception:
            pass

    async def handle_one(self, r, msg_id: str, fields: Dict[str, Any]) -> None:
        user_id = fields.get("user_id", "guest")
        # fields vem como dict de strings do Redis
        event = dict(fields)
        # meta_json pode ser string
        try:
            if isinstance(event.get("meta_json"), str) and event["meta_json"]:
                event["meta"] = json.loads(event["meta_json"])
        except Exception:
            event["meta"] = {}
        # pipeline deliberativo (esqueleto; cada etapa loga e nao quebra as outras)
        try:
            c = await self.consolidator.consolidate(event)
        except Exception as e:
            logger.warning("consolidator failed: %s", e)
            c = {"status": "error", "error": str(e)}
        try:
            p = await self.planner.plan(event)
        except Exception as e:
            logger.warning("planner failed: %s", e)
            p = {"status": "error", "error": str(e)}
        try:
            rf = await self.reflector.review(event)
        except Exception as e:
            logger.warning("reflector failed: %s", e)
            rf = {"status": "error", "error": str(e)}
        try:
            lr = await self.learner.learn(event)
        except Exception as e:
            logger.warning("learner failed: %s", e)
            lr = {"status": "error", "error": str(e)}

        insight = {
            "msg_id": msg_id,
            "thread_id": event.get("thread_id", ""),
            "consolidator": c,
            "planner": p,
            "reflector": rf,
            "learner": lr,
            "ts": int(time.time()),
        }
        # publica insight isolado por user_id
        await self._publish_insight(r, user_id, insight)
        # ack
        try:
            await r.xack(STREAM_KEY, GROUP, msg_id)
        except Exception as e:
            logger.debug("xack failed %s: %s", msg_id, e)
        self.processed += 1
        logger.info("brain2 processed user=%s msg=%s n=%d", user_id, msg_id, self.processed)

    async def run_forever(self, poll_ms: int = 1000, batch: int = 10):
        """Loop principal: XREADGROUP bloqueante."""
        import uuid

        consumer = f"{CONSUMER_PREFIX}-{uuid.uuid4().hex[:6]}"
        logger.info("brain2 starting consumer=%s stream=%s group=%s", consumer, STREAM_KEY, GROUP)
        while not self._stop:
            r = self._get_redis()
            if r is None:
                logger.warning("brain2 no redis, retry in 5s")
                await asyncio.sleep(5)
                continue
            try:
                await self._ensure_group(r)
                # XREADGROUP bloqueante
                resp = await r.xreadgroup(GROUP, consumer, {STREAM_KEY: ">"}, count=batch, block=poll_ms)
                if not resp:
                    continue
                for _stream, messages in resp:
                    for msg_id, fields in messages:
                        try:
                            await self.handle_one(r, msg_id, fields)
                        except Exception as e:
                            self.errors += 1
                            logger.error("brain2 handle_one failed msg=%s: %s", msg_id, e, exc_info=True)
                            # ack mesmo em erro para nao travar fila (DLQ futuro)
                            try:
                                await r.xack(STREAM_KEY, GROUP, msg_id)
                            except Exception:
                                pass
            except asyncio.CancelledError:
                logger.info("brain2 cancelled")
                break
            except Exception as e:
                self.errors += 1
                logger.error("brain2 loop error: %s", e, exc_info=True)
                await asyncio.sleep(2)
            finally:
                try:
                    await r.aclose()  # type: ignore[attr-defined]
                except Exception:
                    try:
                        await r.close()  # type: ignore
                    except Exception:
                        pass


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [brain2] %(message)s")
    svc = Brain2Service()
    await svc.run_forever()


if __name__ == "__main__":
    asyncio.run(main())

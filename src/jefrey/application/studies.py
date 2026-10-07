"""Casos de uso dos estudos em segundo plano: o Jefrey escolhe assuntos pela memoria e pela curiosidade da pessoa e estuda para ajudar
com mais autoridade e pratica.

Ciclo por assunto (estilo "pesquisador"): planejar buscas -> buscar -> ler paginas (leitor protegido) -> escrever um guia
pratico com FONTES e data. Cada ciclo sobe o nivel do assunto. Gasto limitado por dia (padrao US$ 0,10), so com modelo de
nuvem, so quando a pessoa esta ausente e fora do horario de silencio. O texto das paginas e DADO: nunca vira instrucao.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Callable, Optional

from src.jefrey.domain.learning import has_secret
from src.jefrey.domain.reminders import local_tz
from src.jefrey.domain.recall import relevant_facts
from src.jefrey.domain.studies import (
    LEVEL_MAX, MAX_PAGES, _MIN_CALL_USD, _PLAN_PROMPT, _WRITE_PROMPT, StudyError, _norm, build_guide, clean_source_url, curiosity_topics,
    due_topic, estimate_usd, in_quiet_hours, interests_from_facts, level_label, parse_queries,
)
from src.jefrey.ports.registry import use

logger = logging.getLogger(__name__)


def interests_from_memory(user_id: str) -> list[str]:
    return interests_from_facts(use("studies_env").active_facts(user_id))


def curiosities(user_id: str, min_count: int = 2) -> list[str]:
    return curiosity_topics(use("studies_env").recent_user_messages(user_id, 120), min_count)


def auto_topics(user_id: str, store: Any = None) -> list[dict]:
    """Inclui os assuntos que a memoria e a curiosidade indicam (ate o limite). Devolve os novos."""
    store = store or use("studies_env").store()
    added: list[dict] = []
    for source, titles in (("memoria", interests_from_memory(user_id)), ("curiosidade", curiosities(user_id))):
        for title in titles:
            try:
                added.append(store.add_topic(user_id, title, source))
            except ValueError:
                continue
    return added


class _Budget:
    def __init__(self, store: Any, user_id: str, day: str, limit: float):
        self.store, self.user_id, self.day, self.limit = store, user_id, day, limit

    def remaining(self) -> float:
        return self.limit - self.store.spent_today(self.user_id, self.day)

    async def ask(self, client: Any, messages: list[dict], expect_out_chars: int) -> str:
        est = estimate_usd(sum(len(m["content"]) for m in messages), expect_out_chars)
        if self.remaining() < max(est, _MIN_CALL_USD):
            raise StudyError("O limite de gasto de hoje acabou. Eu continuo amanhã.")
        out = await client.chat(messages)
        self.store.charge(self.user_id, self.day, estimate_usd(sum(len(m["content"]) for m in messages), len(out or "")))
        return out or ""


def _is_cloud(client: Any) -> bool:
    return bool(getattr(getattr(client, "config", None), "is_cloud", False))


async def study_topic(user_id: str, topic_id: str, client: Any, *, store: Any = None, **kw) -> dict:
    """Um ciclo de estudo. Devolve o guia criado; levanta StudyError com texto pronto para a tela."""
    env = use("studies_env")
    store = store or env.store()
    topic = store.get_topic(user_id, topic_id)
    with env.busy(user_id, "estudando", topic["title"] if topic else ""):  # a tela mostra "estudando..." no avatar
        return await _study(user_id, topic_id, client, store=store, **kw)


async def _study(user_id: str, topic_id: str, client: Any, *, tz=None, search: Optional[Callable] = None,
                 fetch: Optional[Callable] = None, store: Any = None) -> dict:
    env = use("studies_env")
    search, fetch = search or env.web_search, fetch or env.fetch_page
    store = store or env.store()
    topic = store.get_topic(user_id, topic_id)
    if topic is None:
        raise StudyError("Não encontrei esse assunto.")
    if not _is_cloud(client):
        raise StudyError("Para estudar bem, eu preciso estar ligado à inteligência na nuvem. Veja em Conexões.")
    day = (datetime.now(tz) if tz else datetime.now()).date().isoformat()
    prefs = store.get_prefs(user_id)
    budget = _Budget(store, user_id, day, prefs["budget_usd"])
    try:
        queries = parse_queries(await budget.ask(client, [{"role": "system", "content": _PLAN_PROMPT},
                                                          {"role": "user", "content": f"Assunto: {topic['title']}"}], 200), topic["title"])
        seen_urls, seen_domains = store.read_urls(user_id, topic_id), set()
        cands: list[dict] = [{"url": u["url"], "title": u["title"], "snippet": "", "mine": True}
                             for u in store.list_sources(user_id, topic_id) + [x for x in store.list_sources(user_id) if x["topic_id"] is None]
                             if u["url"] not in seen_urls]
        for q in queries:
            for r in await search(q, 6):
                d = env.domain(r["url"])
                if r["url"] in seen_urls or d in seen_domains:
                    continue
                seen_domains.add(d)
                cands.append(r)
        pages: list[dict] = []
        mine_urls = {c["url"] for c in cands if c.get("mine")}
        for r in cands[: MAX_PAGES + 2 + len(mine_urls)]:
            if len(pages) >= MAX_PAGES + min(len(mine_urls), 2):
                break
            try:
                pg = await fetch(r["url"])
                pg["mine"] = r["url"] in mine_urls
                pages.append(pg)
            except env.read_error:
                continue
        if not pages:
            raise StudyError("Não consegui ler fontes agora. Tento de novo mais tarde.")
        sources = [{"title": p["title"], "url": p["url"], "date": p["fetched_at"], **({"mine": True} if p.get("mine") else {})} for p in pages]
        material = "\n".join(f"<fonte n={i}>\n{p['text'][:2500]}\n</fonte>" for i, p in enumerate(pages, 1))
        raw = await budget.ask(client, [{"role": "system", "content": _WRITE_PROMPT},
                                        {"role": "user", "content": f"Assunto: {topic['title']}\nNivel atual de conhecimento: {level_label(topic['level'])}\n{material}"}], 2200)
        guide = build_guide(raw, sources)
        if guide is None:
            raise StudyError("Não consegui montar um guia confiável desta vez. Tento de novo mais tarde.")
    except StudyError as e:
        store.mark(user_id, topic_id, error=str(e)[:200])
        raise
    except Exception as e:
        logger.warning("estudo falhou: %s", type(e).__name__)
        msg = "Algo deu errado no estudo. Tento de novo mais tarde."
        store.mark(user_id, topic_id, error=msg)
        raise StudyError(msg)
    level = min(LEVEL_MAX, topic["level"] + 1)
    gid = store.add_guide(user_id, topic_id, guide["title"], guide["summary"], guide["body"], guide["sources"], level)
    store.mark(user_id, topic_id, level=level)
    return {**guide, "id": gid, "level": level, "level_label": level_label(level), "topic_id": topic_id}


# ---------------- aprender por pedido (sem usar o chat) ----------------
async def learn_request(user_id: str, *, topic: str = "", url: str = "", text: str = "", store: Any = None,
                        fetch: Optional[Callable] = None) -> dict:
    """A pessoa pede para o Jefrey aprender algo: um assunto, um link ou um texto. Devolve o que foi feito (sem estudar ainda).

    - link: vira fonte (e assunto, com o titulo da pagina se a pessoa nao disse); o estudo le essa pagina primeiro;
    - assunto: entra na lista de estudos;
    - texto: guardado nas notas/memorias e dele saem fatos (nunca segredos).
    """
    env = use("studies_env")
    store = store or env.store()
    topic, url, text = (topic or "").strip(), (url or "").strip(), (text or "").strip()
    if not (topic or url or text):
        raise ValueError("Diga o assunto, cole um link ou um texto.")
    out: dict = {}
    if text and len(text) >= 20 and not url:
        if has_secret(text):
            raise ValueError("Esse texto parece ter senha, documento ou número de cartão. Eu não guardo isso.")
        out.update(saved_text=True, facts=env.save_note_and_learn(user_id, text))
        if not topic:
            return out
    if url:
        clean = clean_source_url(url)
        if clean is None:
            raise ValueError("Esse link não serve. Use um endereço de site que comece com http:// ou https://")
        title = topic
        if not title:
            try:
                page = await (fetch or env.fetch_page)(clean)
                title = re.sub(r"\s*[|\-–—].*$", "", page["title"]).strip()[:80] or env.domain(clean)
            except env.read_error:
                title = env.domain(clean)
        try:
            t = store.add_topic(user_id, title, "manual")
        except ValueError as e:
            if "já está" not in str(e):
                raise
            t = next(x for x in store.list_topics(user_id) if _norm(x["title"]) == _norm(title))
        store.add_source(user_id, clean, t["id"], title=title)
        out.update(topic=t, source=clean)
        return out
    if topic:
        try:
            out["topic"] = store.add_topic(user_id, topic, "manual")
        except ValueError as e:
            if "já está" not in str(e):
                raise
            out["topic"] = next(x for x in store.list_topics(user_id) if _norm(x["title"]) == _norm(topic))
    return out


# ---------------- quando estudar ----------------
def eligible(user_id: str, tz, idle_s: float, store: Any = None, min_idle_s: float = 300) -> bool:
    store = store or use("studies_env").store()
    prefs = store.get_prefs(user_id)
    if not prefs["enabled"] or prefs["budget_usd"] <= 0 or idle_s < min_idle_s:
        return False
    now = datetime.now(tz)
    if in_quiet_hours(now.hour, prefs["quiet_start"], prefs["quiet_end"]):
        return False
    return store.spent_today(user_id, now.date().isoformat()) < prefs["budget_usd"] - _MIN_CALL_USD


def candidate_users(store: Any = None) -> list[str]:
    """Pessoas que ja tem assuntos ou fatos aprendidos."""
    return use("studies_env").candidate_users(store)


_auto_day: dict[str, str] = {}


async def study_tick(get_client: Optional[Callable[[], Any]] = None, tz=None, idle: Optional[Callable[[str], float]] = None,
                     **kw) -> list[str]:
    """Uma rodada: para cada pessoa ausente e dentro do orcamento, estuda o assunto mais atrasado. Devolve ids estudados."""
    env = use("studies_env")
    tz = tz or local_tz()
    idle = idle or env.idle_seconds
    if get_client is None:
        get_client = env.llm_client
    store = env.store()
    studied: list[str] = []
    for uid in candidate_users(store):
        try:
            if not eligible(uid, tz, idle(uid), store):
                continue
            client = get_client()
            if not _is_cloud(client):
                continue
            today = datetime.now(tz).date().isoformat()
            if _auto_day.get(uid) != today:  # uma vez por dia: inclui assuntos novos da memoria/curiosidade
                _auto_day[uid] = today
                auto_topics(uid, store)
            topic = due_topic(store.list_topics(uid))
            if topic is None:
                continue
            await study_topic(uid, topic["id"], client, tz=tz, store=store, **kw)
            studied.append(topic["id"])
        except StudyError:
            continue
        except Exception as e:
            logger.warning("rodada de estudo falhou: %s", type(e).__name__)
    return studied


def guide_lines(user_id: str, question: str, limit: int = 2) -> list[str]:
    """Resumo dos guias que o Jefrey estudou e que tem a ver com a pergunta (para o prompt e para o 'Lembrei de')."""
    try:
        guides = use("studies_env").store().all_guides(user_id)
    except Exception:
        return []
    latest: dict[str, dict] = {}
    for g in guides:
        latest.setdefault(g["topic_id"], g)
    labels = {f"{g['title']}. {g['summary']}": g for g in latest.values()}
    hit = relevant_facts(question, list(labels), limit)
    return [f"Guia estudado: {g['title']} ({g['level_label']}). {g['summary']}" for g in (labels[h] for h in hit)]

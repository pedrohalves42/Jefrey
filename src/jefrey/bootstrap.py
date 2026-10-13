"""Raiz de composicao: o UNICO lugar que escolhe qual adaptador entra em cada porta e liga os casos de uso ao agendador."""
from __future__ import annotations

from src.jefrey.adapters.outbound.system_adapters import DbUserDirectory, GoogleCalendarAdapter, SystemClock, WindowsNotifier
from src.jefrey.application.event_alerts import EventAlertService


def wire() -> None:
    """Liga cada porta ao adaptador padrao (chamado sozinho na primeira vez que um caso de uso pede uma porta)."""
    from src.jefrey.adapters.outbound import agent_env, briefing_env, privacy_env, runtime_ports, social_env, studies_env, vision_env

    runtime_ports.register()
    agent_env.register()
    briefing_env.register()
    privacy_env.register()
    studies_env.register()
    social_env.register()
    vision_env.register()


def build_event_alerts() -> EventAlertService:
    return EventAlertService(GoogleCalendarAdapter(), WindowsNotifier(), DbUserDirectory(), SystemClock())


def build_interest_alerts():
    """Um aviso por dia com o que ha de novo nos assuntos que a pessoa escolheu em Hoje > Para voce."""
    import os
    from datetime import datetime
    from pathlib import Path

    from src.jefrey.adapters.outbound import today_sources as ts
    from src.jefrey.application import notify
    from src.jefrey.application.interest_alerts import InterestAlerts
    from src.jefrey.domain.reminders import local_tz
    from src.jefrey.domain.today import INTERESTS

    sources = ts.HttpPanelSources(None)

    async def headlines(topic: str) -> list:
        return await sources.feed(INTERESTS[topic][1])

    return InterestAlerts(
        interests=lambda uid: ts.load_prefs()["interests"], headlines=headlines,
        notify=lambda uid, title, text: notify.notify(uid, title, text),
        users=lambda: DbUserDirectory().known_users(), now=lambda: datetime.now(local_tz()),
        labels={k: v[0] for k, v in INTERESTS.items()},
        state_path=Path(os.getenv("JEFREY_CONFIG_DIR", "config")) / "interest_alerts.json",
    )


def register_jobs(scheduler) -> None:
    """Tarefas periodicas dos casos de uso novos (as antigas continuam registradas em api/main.py ate migrarem)."""
    alerts = build_event_alerts()
    scheduler.register("avisos-de-compromissos", 120, alerts.tick)
    scheduler.register("alerta-de-assuntos", 1800, build_interest_alerts().tick)


def warm_up() -> None:
    """Esquenta o que a primeira pergunta pagaria sozinha (carregar as ferramentas): a 1a resposta chegava ~2,8 s mais devagar."""
    import logging
    import threading

    def work() -> None:
        try:
            from src.jefrey.skills import load_skills

            load_skills()
        except Exception as e:
            logging.getLogger(__name__).debug("esquentar ferramentas: %s", type(e).__name__)

    threading.Thread(target=work, daemon=True, name="jefrey-warmup").start()


def refresh_public_assets() -> None:
    """Atualiza a copia da extensao do Chrome que fica em Documentos (o Chrome carrega dali) a cada abertura do programa."""
    import logging

    try:
        from src.jefrey.core.paths import public_extension_dir

        public_extension_dir()
    except Exception as e:
        logging.getLogger(__name__).debug("copia da extensao nao atualizada (%s)", type(e).__name__)

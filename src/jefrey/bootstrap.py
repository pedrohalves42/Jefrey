"""Raiz de composicao: o UNICO lugar que escolhe qual adaptador entra em cada porta e liga os casos de uso ao agendador."""
from __future__ import annotations

from src.jefrey.adapters.outbound.system_adapters import DbUserDirectory, GoogleCalendarAdapter, SystemClock, WindowsNotifier
from src.jefrey.application.event_alerts import EventAlertService


def wire() -> None:
    """Liga cada porta ao adaptador padrao (chamado sozinho na primeira vez que um caso de uso pede uma porta)."""
    from src.jefrey.adapters.outbound import agent_env, briefing_env, privacy_env, runtime_ports, social_env, studies_env

    runtime_ports.register()
    agent_env.register()
    briefing_env.register()
    privacy_env.register()
    studies_env.register()
    social_env.register()


def build_event_alerts() -> EventAlertService:
    return EventAlertService(GoogleCalendarAdapter(), WindowsNotifier(), DbUserDirectory(), SystemClock())


def register_jobs(scheduler) -> None:
    """Tarefas periodicas dos casos de uso novos (as antigas continuam registradas em api/main.py ate migrarem)."""
    alerts = build_event_alerts()
    scheduler.register("avisos-de-compromissos", 120, alerts.tick)


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

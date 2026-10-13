"""Atalho de compatibilidade dos estudos: regras em domain/studies.py, casos de uso em application/studies.py, banco em adapters/outbound/sql_studies.py."""
from src.jefrey.adapters.outbound import webread  # noqa: F401  (testes trocam webread.web_search/fetch_page)
from src.jefrey.adapters.outbound.sql_studies import StudyStore, _sources_table, _tables  # noqa: F401
from src.jefrey.application.studies import *  # noqa: F401,F403
from src.jefrey.application.studies import _Budget, _auto_day, _is_cloud, _study  # noqa: F401
from src.jefrey.domain.studies import *  # noqa: F401,F403
from src.jefrey.domain.studies import _CURIOUS, _FACT_PREFIX, _MIN_CALL_USD, _PLAN_PROMPT, _WRITE_PROMPT, _clean_list, _json, _norm, _price  # noqa: F401

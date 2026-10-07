"""Atalho de compatibilidade de "Seus dados" (LGPD): regras em domain/privacy.py, casos de uso em application/privacy.py, dados em adapters/outbound/."""
from src.jefrey.adapters.outbound.sql_consent import ConsentStore, documents  # noqa: F401
from src.jefrey.application.privacy import _safe, erase_all, export_all, summary  # noqa: F401
from src.jefrey.domain.privacy import TERMS_VERSION  # noqa: F401

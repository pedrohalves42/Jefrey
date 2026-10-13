"""Guarda contra regressoes que ja apareceram em relatorios de status: modelos duplicados, nomes de provedor errados, papel inexistente, lixo na raiz."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "jefrey"


def _fontes():
    return [p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts]


def test_cada_modelo_do_banco_e_definido_uma_vez_so():
    for nome in ("OAuthToken", "Approval"):
        onde = [p for p in _fontes() if re.search(rf"^class {nome}\(Base\)", p.read_text(encoding="utf-8"), re.M)]
        assert len(onde) == 1, f"{nome} definido em {[str(p.relative_to(SRC)) for p in onde]}"


def test_ferramentas_do_google_leem_o_mesmo_provedor_que_a_conexao_grava():
    from src.jefrey.adapters.outbound.google_oauth import SERVICES
    from src.jefrey.skills import calendar, drive, email

    gravado = {k: v["provider"] for k, v in SERVICES.items()}
    for mod, servico in ((calendar, "calendar"), (email, "email"), (drive, "drive")):
        skill = next(c for c in vars(mod).values() if isinstance(c, type) and c.__name__.endswith("Skill") and c.__module__ == mod.__name__)()
        assert skill._google.provider == gravado[servico], (mod.__name__, skill._google.provider, gravado[servico])


def test_politica_so_conhece_papeis_que_o_rbac_atribui():
    from src.jefrey.domain.policy import Role as PolicyRole
    from src.jefrey.domain.rbac import Role as RbacRole

    assert {r.value for r in PolicyRole} == {r.value for r in RbacRole}


def test_raiz_do_projeto_sem_arquivos_temporarios():
    lixo = [p.name for p in ROOT.iterdir() if p.is_file() and re.match(r"(_.*\.txt|fix_.*\.py|debug_.*\.py|temp_.*|validate.*\.txt|check.*\.txt)$", p.name)]
    assert not lixo, lixo


def test_testes_nao_carregam_chaves_do_google_com_cara_de_verdadeiras():
    ruim = []
    for p in (ROOT / "tests").rglob("*.py"):
        t = p.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"\b\d{9,}-[a-z0-9]{20,}\.apps\.googleusercontent\.com", t) or re.search(r"GOCSPX-[A-Za-z0-9_-]{25,}", t):
            ruim.append(p.name)
    assert not ruim, f"chave do Google com formato real em: {ruim}"

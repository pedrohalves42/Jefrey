"""Sessao 13 (parte 3): o pacote leva o que precisa e a documentacao de venda esta coerente."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_o_build_empacota_textos_legais_extensao_e_voz():
    bat = _read("packaging/build_exe.bat")
    assert "src\\jefrey\\legal" in bat and "src/jefrey/legal" in bat  # termos e privacidade vao dentro do programa
    assert "extensions\\whatsapp" in bat and "extensao-chrome" in bat  # extensao em pasta visivel
    assert "--collect-all faster_whisper" in bat and "--collect-all av" in bat and "--collect-all ddgs" in bat
    assert "/DAppVersion=%VERSION%" in bat  # o instalador usa a versao do programa


def test_assinatura_de_codigo_so_com_certificado_e_senha_nunca_no_arquivo():
    bat = _read("packaging/build_exe.bat")
    assert "JEFREY_SIGN_PFX" in bat and "JEFREY_SIGN_PASS" in bat and "signtool" in bat.lower()
    assert re.search(r"/p \"%JEFREY_SIGN_PASS%\"", bat)  # a senha vem do ambiente
    assert not re.search(r"/p \"[^%\"]+\"", bat)  # nenhuma senha escrita no script
    assert "/fd SHA256" in bat and "/tr http" in bat  # hash forte e carimbo de tempo


def test_instalador_por_usuario_sem_administrador_e_sem_apagar_dados():
    iss = _read("packaging/jefrey.iss")
    assert "PrivilegesRequired=lowest" in iss and "CloseApplications=yes" in iss
    assert "{localappdata}" in iss and "Jefrey.exe" in iss
    assert "NAO sao apagados ao desinstalar" in iss


def test_versao_unica_nos_tres_lugares():
    init = re.search(r'__version__ = "([^"]+)"', _read("src/jefrey/__init__.py")).group(1)
    toml = re.search(r'^version = "([^"]+)"', _read("pyproject.toml"), re.M).group(1)
    cfg = re.search(r'version: str = "([^"]+)"', _read("src/jefrey/core/config.py")).group(1)
    assert init == toml == cfg
    from src.jefrey.core.updater import parse_version
    assert parse_version(init) >= (0, 9, 0)


def test_textos_legais_tem_marcas_de_revisao_e_nao_prometem_o_que_nao_existe():
    for nome in ("termos.md", "privacidade.md"):
        t = _read(f"src/jefrey/legal/{nome}")
        assert "REVISAR COM ADVOGADO" in t and "[NOME DA EMPRESA]" in t
    p = _read("src/jefrey/legal/privacidade.md")
    assert "Não coletamos estatísticas de uso" in p and "Hugging Face" in p and "DuckDuckGo" in p  # o que sai esta dito
    assert "venda" not in p.lower().replace("não vendemos seus dados", "")  # so a promessa de nao vender


def test_a_documentacao_de_venda_lista_o_que_depende_do_dono():
    d = _read("docs/DISTRIBUICAO.md")
    for item in ("Certificado de assinatura", "Par de chaves", "Servidor de atualizações", "Textos legais", "Licença do código", "verificação", "Chrome Web Store", "PC limpo"):
        assert item in d
    assert "não cobre o Brasil" in d
    site = _read("site/index.html")
    assert "[PREÇO]" in site and "[LINK-DO-INSTALADOR]" in site and 'lang="pt-BR"' in site  # pendencias marcadas, nada inventado


def test_licencas_de_terceiros_sem_copyleft_forte():
    t = _read("docs/LICENCAS_TERCEIROS.md")
    assert "Copyleft forte (decidir antes de vender):** nenhuma encontrada" in t


def test_nenhuma_chave_privada_no_repositorio_e_ela_esta_no_gitignore():
    ignore = _read(".gitignore")
    for padrao in ("update_private_key*", "*.pfx", "*.p12"):
        assert padrao in ignore
    assert not list(ROOT.glob("update_private_key*")) and not list(ROOT.glob("*.pfx"))
    updater = _read("src/jefrey/core/updater.py")
    assert "private_bytes" not in updater and "Ed25519PrivateKey" not in updater  # o programa so VERIFICA; nunca assina

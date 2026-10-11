import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ISS = (ROOT / "packaging" / "jefrey.iss").read_text(encoding="utf-8")
BAT = (ROOT / "packaging" / "build_exe.bat").read_text(encoding="utf-8")


def test_instala_sem_administrador_e_por_usuario():
    assert "PrivilegesRequired=lowest" in ISS and "{localappdata}\Programs\Jefrey" in ISS


def test_pergunta_antes_de_apagar_dados_e_o_padrao_e_manter():
    assert "CurUninstallStepChanged" in ISS and "usPostUninstall" in ISS
    assert "MB_DEFBUTTON1" in ISS and "MB_YESNO" in ISS  # botao padrao = Sim = manter
    corpo = ISS[ISS.index("CurUninstallStepChanged"):]
    assert "= IDNO then" in corpo and "DelTree" in corpo  # so apaga se a pessoa disse Nao
    assert corpo.count("DelTree") == 1 and "localappdata}\Jefrey'" in corpo  # apaga so a pasta de dados do Jefrey


def test_atualizacao_fecha_e_reabre_o_programa():
    assert "CloseApplications=yes" in ISS and "RestartApplications=yes" in ISS


def test_extensao_vai_junto_e_o_build_copia_antes():
    assert "dist\Jefrey\*" in ISS and "recursesubdirs" in ISS
    assert "extensao-chrome" in BAT and "xcopy" in BAT


def test_build_embute_padroes_e_voz_sem_levar_segredos_do_repositorio():
    assert "defaults" in BAT and "collect-all piper" in BAT
    assert not re.search(r"copy[^\n]*\.env", BAT) and "private" not in BAT.lower().replace("update_private", "")


def test_abre_o_jefrey_ao_terminar_sem_travar_instalacao_silenciosa():
    assert "postinstall skipifsilent" in ISS

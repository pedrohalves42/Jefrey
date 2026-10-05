import pytest

from src.jefrey.core import uiautomation as UA


class Falso:
    """Backend de mentira: guarda o que seria digitado/enviado, sem tocar no computador."""

    def __init__(self, fg=(10, "Documento1 - Bloco de Notas", "notepad")):
        self.fg = fg
        self.digitado: list[str] = []
        self.teclas: list[tuple[int, ...]] = []
        self.focado: list[int] = []
        self.janelas = [fg, (20, "Planilha - Excel", "EXCEL"), (30, "Jefrey - Chrome", "chrome"), (40, "Pasta", "explorer")]

    def foreground(self):
        return self.fg

    def windows(self):
        return self.janelas

    def set_foreground(self, hwnd):
        self.focado.append(hwnd)
        self.fg = next(w for w in self.janelas if w[0] == hwnd)
        return True

    def send_text(self, text):
        self.digitado.append(text)

    def send_keys(self, vks):
        self.teclas.append(tuple(vks))


@pytest.fixture()
def b(monkeypatch):
    f = Falso()
    monkeypatch.setattr(UA, "_B", f)
    return f


def test_digita_so_na_janela_confirmada(b):
    UA.type_text("olá, mundo", expect_hwnd=10)
    assert b.digitado == ["olá, mundo"]


def test_nao_digita_se_a_janela_mudou(b):
    b.fg = (20, "Planilha - Excel", "EXCEL")  # a pessoa trocou de janela no meio
    with pytest.raises(UA.UIError, match="mudou"):
        UA.type_text("segredo", expect_hwnd=10)
    assert b.digitado == []


@pytest.mark.parametrize("fg", [(40, "Pasta", "explorer"), (30, "Jefrey - Chrome", "chrome"), (50, "Gerenciador de Tarefas", "Taskmgr")])
def test_nao_digita_em_janela_protegida(b, fg):
    b.janelas.append(fg)
    b.fg = fg
    with pytest.raises(UA.UIError, match="protegid"):
        UA.type_text("x", expect_hwnd=fg[0])
    assert b.digitado == []


def test_texto_grande_ou_vazio_e_recusado(b):
    with pytest.raises(UA.UIError, match="500"):
        UA.type_text("a" * 501, expect_hwnd=10)
    with pytest.raises(UA.UIError, match="digitar"):
        UA.type_text("   ", expect_hwnd=10)
    assert b.digitado == []


def test_texto_com_comandos_e_so_texto(b):
    UA.type_text("rm -rf / && del *.*", expect_hwnd=10)  # nunca e executado: apenas digitado como letras
    assert b.digitado == ["rm -rf / && del *.*"]


def test_caracteres_de_controle_sao_removidos(b):
    UA.type_text("a\x00b\x1bc\td", expect_hwnd=10)
    assert b.digitado == ["abc d"]  # tab vira espaco; controle some


@pytest.mark.parametrize("combo", ["ctrl+c", "CTRL + V", "ctrl+s", "alt+tab", "enter", "esc"])
def test_atalhos_da_lista_funcionam(b, combo):
    UA.hotkey(combo, expect_hwnd=10)
    assert len(b.teclas) == 1


@pytest.mark.parametrize("combo", ["ctrl+alt+del", "win+r", "alt+f4", "ctrl+shift+esc", "f12", "ctrl+w", ""])
def test_atalho_fora_da_lista_e_recusado(b, combo):
    with pytest.raises(UA.UIError, match="atalho"):
        UA.hotkey(combo, expect_hwnd=10)
    assert b.teclas == []


def test_foco_na_janela_pedida_e_confirmacao(b):
    hwnd = UA.focus("excel")
    assert hwnd == 20 and b.focado == [20]
    assert UA.foreground()[0] == 20


def test_foco_recusa_janela_protegida_e_ambigua(b):
    with pytest.raises(UA.UIError, match="Não vi"):
        UA.focus("explorer")
    b.janelas.append((60, "Outro - Excel", "EXCEL2"))
    with pytest.raises(UA.UIError, match="mais de um"):
        UA.focus("excel")

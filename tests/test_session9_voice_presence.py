"""Sessao 9: atalho global, palavra de ativacao (com taxa de falso disparo medida) e bandeja."""
import io

import pytest
from fastapi.testclient import TestClient

from src.jefrey.core import activity as ACT
from src.jefrey.core import wake as W
from src.jefrey.core import wakeword as WW
from src.jefrey.native import hotkey as HK
from src.jefrey.native import launcher as LA


# ---------------- atalho ----------------
@pytest.mark.parametrize("spec,esperado", [
    ("ctrl+alt+j", (0x0002 | 0x0001, ord("J"))), ("Ctrl+Shift+9", (0x0002 | 0x0004, ord("9"))), ("win+j", (0x0008, ord("J"))),
    ("control+alt+x", (0x0003, ord("X"))),
])
def test_atalhos_validos(spec, esperado):
    assert HK.parse_hotkey(spec) == esperado


@pytest.mark.parametrize("spec", ["", "j", "ctrl+", "ctrl+alt", "ctrl+f1", "foo+j", "ctrl+alt+jj", "alt+ç", "+++", "ctrl+alt+ "])
def test_atalhos_invalidos_sao_recusados(spec):
    assert HK.parse_hotkey(spec) is None


def test_atalho_invalido_nao_registra_nada():
    assert HK.start_hotkey(lambda: None, "j") is None


def test_focar_janela_inexistente_nao_quebra():
    assert HK.focus_window("ZzzJanelaQueNaoExiste123") is False


# ---------------- sinal de acorde ----------------
def test_pedido_de_acorde_chega_uma_vez_so():
    W.reset()
    assert W.poll(now=100.0) is False
    W.request(now=101.0)
    assert W.poll(now=102.0) is True and W.poll(now=103.0) is False


def test_pedido_antigo_expira():
    W.reset()
    W.request(now=100.0)
    assert W.poll(now=100.0 + W.PENDING_TTL_S + 1) is False
    assert W.poll(now=200.0) is False  # e nao fica pendente para sempre


def test_tela_viva_so_se_perguntou_ha_pouco():
    W.reset()
    assert W.ui_alive(now=10.0) is False
    W.poll(now=10.0)
    assert W.ui_alive(now=10.0 + W.UI_ALIVE_S - 1) is True and W.ui_alive(now=10.0 + W.UI_ALIVE_S + 1) is False


# ---------------- palavra de ativacao ----------------
POSITIVAS = [
    ("Jefrey", ""), ("Jefrey, que horas são?", "que horas são?"), ("jefrey que dia é hoje", "que dia é hoje"), ("Ei Jefrey, me lembra de beber água", "me lembra de beber água"),
    ("Oi, Jefrey! Tudo bem?", "Tudo bem?"), ("Jeffrey, abre a agenda", "abre a agenda"), ("Jefri, qual o clima", "qual o clima"),
    ("Jefre toca uma música", "toca uma música"), ("E aí Jefrey, e o dólar?", "e o dólar?"), ("Opa, Jefrey", ""),
    ("jeferi me ajuda", "me ajuda"), ("Hey Jefrey tudo certo", "tudo certo"), ("Fala, Jefrey: quais são os meus lembretes?", "quais são os meus lembretes?"),
    ("JEFREY.", ""), ("Jéfrey, boa noite", "boa noite"),
]


@pytest.mark.parametrize("fala,resto", POSITIVAS)
def test_reconhece_quando_a_fala_comeca_chamando(fala, resto):
    assert WW.find_wake(fala) == resto


NEGATIVAS = [
    "oi tudo bem com você", "bom dia pessoal", "que horas são", "o jantar está pronto", "Jefferson, venha jantar", "a Jéssica ligou ontem",
    "Geraldo não vem hoje", "o ferry sai às oito", "Jeff está atrasado", "Jerônimo mora ali", "vamos ao shopping amanhã", "preciso comprar pão",
    "a novela começa agora", "me passa o controle", "desliga a televisão", "o Jefrey é um assistente legal que a gente comprou",  # nome no meio da frase
    "tenho consulta na terça", "você viu o jogo", "Eufrásio chegou", "a Geferina mora longe", "Seu Joaquim já saiu", "feliz aniversário",
    "o jornal diz que vai chover", "quero um café sem açúcar", "deixa que eu abro", "hoje é dia de feira", "Jefté vai buscar o menino",
    "Rafael, atende o telefone", "cuidado com o degrau", "já passou da hora de dormir", "alô, quem fala", "Jenifer está na cozinha",
    "ei, cadê as chaves", "oi", "", "   ", "e aí, tudo bem", "a internet caiu de novo", "Jorge, vem cá", "Jefrey", "Jefr",
]


def test_taxa_de_falso_disparo_medida_na_amostra():
    esperados_positivos = {"Jefrey"}  # o unico item da lista negativa que e positivo de verdade (so o nome)
    falsos = [f for f in NEGATIVAS if WW.find_wake(f) is not None and f not in esperados_positivos]
    taxa = len(falsos) / (len(NEGATIVAS) - len(esperados_positivos))
    assert falsos == [] and taxa == 0.0, falsos


def test_reconhecimento_nas_variacoes_do_whisper():
    achou = sum(WW.find_wake(f) is not None for f, _ in POSITIVAS)
    assert achou == len(POSITIVAS)  # 100% da amostra de variacoes comuns


def test_so_devolve_o_que_vem_depois_do_nome():
    assert WW.find_wake("Jefrey, minha senha é 1234 e o cartão 4111") == "minha senha é 1234 e o cartão 4111"  # quem usa decide; nada e guardado aqui
    assert WW.find_wake("a gente falou do Jefrey ontem") is None


# ---------------- API ----------------
@pytest.fixture()
def api():
    from src.jefrey.api import auth_middleware
    from src.jefrey.api.main import app
    auth_middleware._rl_buckets.clear()
    c = TestClient(app)
    tok = c.post("/auth/dev-token", json={"user_id": "apiwake"}).json()["access_token"]
    return c, {"Authorization": f"Bearer {tok}"}


def _audio(n=2000):
    return {"audio": ("fala.webm", io.BytesIO(b"x" * n), "audio/webm")}


def test_api_exige_login(api):
    c, h = api
    assert c.get("/system/wake").status_code == 401
    assert c.post("/stt/wake", files=_audio()).status_code == 401


def test_api_sinal_de_acorde(api):
    c, h = api
    W.reset()
    assert c.get("/system/wake", headers=h).json() == {"wake": False}
    W.request()
    assert c.get("/system/wake", headers=h).json() == {"wake": True}
    assert c.get("/system/wake", headers=h).json() == {"wake": False}
    assert W.ui_alive() is True  # a propria pergunta mostra que ha uma tela aberta


class MotorFalso:
    def __init__(self, texto):
        self.texto, self.dicas = texto, []

    def transcribe(self, data, prompt=None):
        self.dicas.append(prompt)
        if isinstance(self.texto, Exception):
            raise self.texto
        return self.texto


def _com_motor(monkeypatch, motor, pronto=True):
    import src.jefrey.core.stt_engine as SE
    import src.jefrey.core.voice_ready as VR
    monkeypatch.setattr(SE, "get_stt_engine", lambda: motor)
    monkeypatch.setattr(VR, "status", lambda: {"ready": pronto, "running": False, "error": None, "model": "base"})


def test_api_wake_devolve_so_o_necessario(api, monkeypatch):
    c, h = api
    motor = MotorFalso("Jefrey, que horas são?")
    _com_motor(monkeypatch, motor)
    r = c.post("/stt/wake", headers=h, files=_audio()).json()
    assert r == {"wake": True, "rest": "que horas são?", "ready": True} and motor.dicas == ["Jefrey, assistente pessoal."]
    motor.texto = "a novela começa agora e minha senha é 1234"
    r = c.post("/stt/wake", headers=h, files=_audio()).json()
    assert r == {"wake": False, "rest": "", "ready": True}  # nada do que foi dito vaza na resposta
    assert "novela" not in str(r) and "1234" not in str(r)


def test_api_wake_silencio_audio_enorme_e_modelo_nao_pronto(api, monkeypatch):
    c, h = api
    _com_motor(monkeypatch, MotorFalso(ValueError("Transcription returned empty text")))
    assert c.post("/stt/wake", headers=h, files=_audio()).json()["wake"] is False
    assert c.post("/stt/wake", headers=h, files=_audio(50)).json()["wake"] is False  # curto demais
    _com_motor(monkeypatch, MotorFalso("Jefrey"))
    assert c.post("/stt/wake", headers=h, files=_audio(1_600_000)).json()["wake"] is False  # grande demais: nem transcreve
    _com_motor(monkeypatch, MotorFalso("Jefrey"), pronto=False)
    assert c.post("/stt/wake", headers=h, files=_audio()).json() == {"wake": False, "rest": "", "ready": False}
    _com_motor(monkeypatch, MotorFalso(RuntimeError("c:\\segredo")))
    assert c.post("/stt/wake", headers=h, files=_audio()).json()["wake"] is False


def test_motor_sem_dica_de_vocabulario_tambem_funciona(api, monkeypatch):
    c, h = api

    class SemDica:
        def transcribe(self, data):
            return "Jefrey, abre a agenda"
    _com_motor(monkeypatch, SemDica())
    assert c.post("/stt/wake", headers=h, files=_audio()).json()["rest"] == "abre a agenda"


# ---------------- bandeja ----------------
def test_texto_da_bandeja_segue_o_que_ele_faz():
    assert LA.tray_title({"studying": False, "learning": False, "topic": None}) == "Jefrey"
    assert LA.tray_title({"studying": True, "learning": False, "topic": "horta"}) == "Jefrey: estudando horta"
    assert LA.tray_title({"studying": True, "learning": False, "topic": None}) == "Jefrey: estudando"
    assert LA.tray_title({"studying": False, "learning": True, "topic": None}) == "Jefrey: aprendendo com a conversa"


def test_atividade_somada_de_todas_as_pessoas():
    assert ACT.any_busy() == {"studying": False, "learning": False, "topic": None}
    with ACT.busy("ana", "estudando", "horta"):
        assert ACT.any_busy() == {"studying": True, "learning": False, "topic": "horta"}
    assert ACT.any_busy()["studying"] is False

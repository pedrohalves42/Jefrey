"""Pareamento do celular: codigo de uso unico, 5 min, bloqueio por erros, so rede local, aparelho revogavel."""
from src.jefrey.domain.pairing import CODE_TTL_S, LOCK_S, MAX_DEVICES, PairingBook, host_is_ip_literal, is_private_ip


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def book(clock, tokens=None):
    seq = iter(tokens or [f"tok{i}" for i in range(50)])
    codes = iter(f"{i:08d}" for i in range(1, 99))
    return PairingBook(now=clock, code_gen=lambda: next(codes), token_gen=lambda: next(seq))


def test_codigo_vale_uma_vez():
    c = Clock(); b = book(c)
    code, ttl = b.issue_code("pedro")
    assert ttl == CODE_TTL_S
    assert b.redeem(code) is not None
    assert b.redeem(code) is None


def test_codigo_vencido_e_recusado():
    c = Clock(); b = book(c)
    code, _ = b.issue_code("pedro")
    c.t += CODE_TTL_S + 1
    assert b.redeem(code) is None


def test_codigo_novo_invalida_o_anterior():
    c = Clock(); b = book(c)
    velho, _ = b.issue_code("pedro")
    novo, _ = b.issue_code("pedro")
    assert b.redeem(velho) is None
    assert b.redeem(novo) is not None


def test_erros_seguidos_bloqueiam_ate_o_certo():
    c = Clock(); b = book(c)
    code, _ = b.issue_code("pedro")
    for _ in range(5):
        assert b.redeem("99999999") is None
    assert b.redeem(code) is None  # bloqueado: nem o certo entra
    c.t += LOCK_S + 1  # o codigo velho venceu junto com o bloqueio: precisa de um novo
    assert b.redeem(code) is None
    assert b.redeem(b.issue_code("pedro")[0]) is not None


def test_sessao_vale_e_revoga():
    c = Clock(); b = book(c)
    tok = b.redeem(b.issue_code("pedro")[0], "Celular do Pedro")
    d = b.check(tok)
    assert d and d.user_id == "pedro" and d.name == "Celular do Pedro"
    assert b.check("outro") is None
    assert b.revoke(d.id) is True
    assert b.check(tok) is None


def test_guarda_so_hash():
    c = Clock(); b = book(c, ["segredo-do-token"])
    code, _ = b.issue_code("pedro")
    b.redeem(code)
    assert "segredo-do-token" not in repr(b.__dict__) and code not in repr(b.__dict__)


def test_limite_de_aparelhos():
    c = Clock(); b = book(c)
    for _ in range(MAX_DEVICES):
        assert b.redeem(b.issue_code("pedro")[0]) is not None
    assert b.redeem(b.issue_code("pedro")[0]) is None


def test_so_rede_local():
    for ok in ("192.168.0.7", "10.1.2.3", "172.16.5.5", "172.31.1.1", "127.0.0.1", "::1", "::ffff:192.168.1.9"):
        assert is_private_ip(ok), ok
    for ruim in ("8.8.8.8", "172.32.0.1", "169.254.1.1", "0.0.0.0", "2001:db8::1", "abc", ""):
        assert not is_private_ip(ruim), ruim


def test_host_precisa_ser_ip():
    assert host_is_ip_literal("192.168.0.7:8765") and host_is_ip_literal("[::1]:8765")
    assert not host_is_ip_literal("evil.example.com:8765")
    assert not host_is_ip_literal("192.168.0.7.evil.com")

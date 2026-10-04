from src.jefrey.core.hardware import TIERS, read_memory_gb, recommend_model


def test_escolhe_o_maior_que_cabe():
    assert recommend_model(32).model == "qwen2.5:14b"
    assert recommend_model(8).model == "qwen2.5:7b"
    assert recommend_model(3.5).model == "qwen2.5:3b"
    assert recommend_model(2.5).model == "qwen3:1.7b"
    assert recommend_model(1.2).model == "qwen2.5:0.5b"


def test_nunca_abaixo_do_menor():
    assert recommend_model(0).model == "qwen2.5:0.5b"
    assert recommend_model(0.1).model == "qwen2.5:0.5b"


def test_tiers_ordenados_do_maior_ao_menor():
    sizes = [t.size_gb for t in TIERS]
    assert sizes == sorted(sizes, reverse=True)


def test_leitura_de_memoria_plausivel():
    total, avail = read_memory_gb()
    assert total > 0 and 0 < avail <= total


def test_so_modelos_de_3b_ou_mais_tem_ferramentas_completas():
    for t in TIERS:
        assert t.tools == ("completo" if t.size_gb >= 1.9 and "0.5b" not in t.model else t.tools)
    assert next(t for t in TIERS if t.model == "qwen3:1.7b").tools == "basico"
    assert next(t for t in TIERS if t.model == "qwen2.5:3b").tools == "completo"
    assert next(t for t in TIERS if t.model == "qwen2.5:0.5b").tools == "nenhum"

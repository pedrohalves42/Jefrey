from src.jefrey.core.hardware import TIERS, read_memory_gb, recommend_model


def test_escolhe_o_maior_que_cabe():
    assert recommend_model(32).model == "qwen2.5:14b"
    assert recommend_model(8).model == "qwen2.5:7b"
    assert recommend_model(3.5).model == "qwen2.5:3b"
    assert recommend_model(2.5).model == "qwen2.5:1.5b"


def test_nunca_abaixo_do_menor():
    assert recommend_model(0).model == "qwen2.5:0.5b"
    assert recommend_model(0.1).model == "qwen2.5:0.5b"


def test_tiers_ordenados_do_maior_ao_menor():
    sizes = [t.size_gb for t in TIERS]
    assert sizes == sorted(sizes, reverse=True)


def test_leitura_de_memoria_plausivel():
    total, avail = read_memory_gb()
    assert total > 0 and 0 < avail <= total

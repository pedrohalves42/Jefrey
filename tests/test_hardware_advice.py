"""Sugestao de modelo local: so com placa de video capaz; sem placa, recomenda nuvem com o motivo."""
from src.jefrey.core.hardware import GpuInfo, detect_gpu, local_advice


def smi(text):
    return lambda: text


def test_detecta_nvidia_e_escolhe_a_maior():
    g = detect_gpu(run_smi=smi("NVIDIA GeForce GTX 1050, 4096\nNVIDIA GeForce RTX 4070, 12282\n"), system="Windows", machine="AMD64")
    assert g and g.kind == "nvidia" and g.name == "NVIDIA GeForce RTX 4070" and 11.9 < g.vram_gb < 12.1


def test_nome_com_virgula():
    g = detect_gpu(run_smi=smi("NVIDIA RTX A2000, 12GB edition, 12288"), system="Windows", machine="AMD64")
    assert g and g.name == "NVIDIA RTX A2000, 12GB edition"


def test_sem_nvidia_smi_ou_saida_lixo():
    def falta():
        raise FileNotFoundError("nvidia-smi")
    assert detect_gpu(run_smi=falta, system="Windows", machine="AMD64") is None
    assert detect_gpu(run_smi=smi(""), system="Windows", machine="AMD64") is None
    assert detect_gpu(run_smi=smi("erro qualquer\nsem numero, abc"), system="Windows", machine="AMD64") is None


def test_apple_silicon_usa_parte_da_memoria_unificada():
    g = detect_gpu(system="Darwin", machine="arm64", total_ram_gb=16.0)
    assert g and g.kind == "apple" and g.vram_gb == 10.4


def test_mac_intel_nao_conta_como_gpu():
    assert detect_gpu(run_smi=smi(""), system="Darwin", machine="x86_64") is None


def test_sem_placa_recomenda_nuvem_e_explica():
    a = local_advice(None, 16.0)
    assert a["suggest_local"] is False and a["model"] is None and "nuvem" in a["reason"].lower() and "35 segundos" in a["reason"]


def test_faixas_de_placa():
    assert local_advice(GpuInfo("x", 6.0, "nvidia"), 16)["suggest_local"] is False
    assert local_advice(GpuInfo("x", 8.0, "nvidia"), 16)["model"] == "gemma4:e2b"
    assert local_advice(GpuInfo("x", 12.0, "nvidia"), 16)["model"] == "gemma4:e4b"
    assert local_advice(GpuInfo("x", 24.0, "nvidia"), 32)["model"] == "gemma4:26b"


def test_sugestao_se_declara_estimativa():
    a = local_advice(GpuInfo("x", 12.0, "nvidia"), 16)
    assert a["measured"] is False and "estimativa" in a["reason"]

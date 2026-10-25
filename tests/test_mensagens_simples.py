import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "jefrey" / "api"
# integracao avancada (Docker + n8n), fora das telas do dia a dia: mensagens tecnicas ficam, mas sem variaveis nem segredos
AVANCADO = {"connections.py"}
PROIBIDO = re.compile(r"\.env\b|JEFREY_[A-Z_]+|localhost|127\.0\.0\.1|Traceback|stack trace|secret_key|\bn8n\b|webhook", re.I)


def _textos(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    elif isinstance(node, ast.JoinedStr):
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                yield v.value
    elif isinstance(node, ast.BinOp):
        yield from _textos(node.left)
        yield from _textos(node.right)


def test_nenhuma_mensagem_de_erro_para_a_pessoa_tem_jargao_tecnico():
    """`detail=` de HTTPException chega a tela: nada de .env, variavel de ambiente, localhost, n8n..."""
    ruins = []
    for p in sorted(ROOT.rglob("*.py")):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                for kw in n.keywords:
                    if kw.arg == "detail":
                        for s in _textos(kw.value):
                            if PROIBIDO.search(s) and not (p.name in AVANCADO and re.search(r"n8n|webhook", s, re.I) and not re.search(r"\.env|JEFREY_|secret", s, re.I)):
                                ruins.append(f"{p.name}:{n.lineno}: {s[:70]}")
    assert ruins == []

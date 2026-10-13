"""Plugins: um arquivo .py em `config/plugins/` vira habilidade, mas SO depois da pessoa aprovar aquele arquivo.

A aprovacao vale para o conteudo (SHA-256). Arquivo novo nao carrega; arquivo alterado depois da aprovacao volta a ser
bloqueado ate nova aprovacao. As ferramentas de um plugin entram no catalogo como risco ALTO: cada uso pede aprovacao.
Quem aprova e a pessoa, pela tela; o texto do plugin nunca se aprova sozinho.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import re
import sys
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

_NAME = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
MAX_BYTES = 200_000


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class PluginStore:
    def __init__(self, folder: Path, approvals: Path, tool_names: Callable[[], set[str]] = lambda: set(),
                 mark_high_risk: Callable[[set[str], str], None] = lambda names, plugin: None):
        self._dir, self._approvals = Path(folder), Path(approvals)
        self._tool_names, self._mark_high_risk = tool_names, mark_high_risk
        self._loaded: dict[str, str] = {}

    def _approved(self) -> dict[str, str]:
        try:
            data = json.loads(self._approvals.read_text(encoding="utf-8"))
            return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, data: dict[str, str]) -> None:
        self._approvals.parent.mkdir(parents=True, exist_ok=True)
        self._approvals.write_text(json.dumps(data), encoding="utf-8")

    def _files(self) -> list[Path]:
        if not self._dir.is_dir():
            return []
        return sorted(p for p in self._dir.glob("*.py") if _NAME.match(p.stem) and p.is_file() and p.stat().st_size <= MAX_BYTES)

    def scan(self) -> list[dict]:
        """Cada plugin com o hash atual e o estado: 'novo', 'aprovado' ou 'alterado' (mudou depois da aprovacao)."""
        ok = self._approved()
        out = []
        for p in self._files():
            h = sha256_of(p)
            state = "novo" if p.stem not in ok else ("aprovado" if ok[p.stem] == h else "alterado")
            out.append({"name": p.stem, "sha256": h, "state": state})
        return out

    def approve(self, name: str, sha256: str) -> bool:
        """Aprova SO se o hash que a pessoa viu e o do arquivo agora (se mudou no meio, nao aprova)."""
        for item in self.scan():
            if item["name"] == name and item["sha256"] == sha256:
                data = self._approved()
                data[name] = sha256
                self._save(data)
                return True
        return False

    def revoke(self, name: str) -> bool:
        data = self._approved()
        if name not in data:
            return False
        del data[name]
        self._save(data)
        return True

    def load_approved(self) -> list[str]:
        """Importa os plugins aprovados e sem alteracao. Devolve os nomes carregados; erro em um nao derruba os outros."""
        loaded = []
        for item in self.scan():
            if item["state"] != "aprovado":
                continue
            if self._loaded.get(item["name"]) == item["sha256"]:
                continue  # ja carregado nesta execucao: nao roda duas vezes
            before = self._tool_names()
            try:
                # confere o hash de novo logo antes de executar (nada muda entre a checagem e a carga)
                path = self._dir / f"{item['name']}.py"
                if sha256_of(path) != item["sha256"]:
                    continue
                spec = importlib.util.spec_from_file_location(f"jefrey_plugin_{item['name']}", path)
                if spec is None or spec.loader is None:
                    continue
                mod = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = mod
                spec.loader.exec_module(mod)
            except Exception as e:
                logger.warning("plugin %s nao carregou (%s)", item["name"], type(e).__name__)
                continue
            self._mark_high_risk(self._tool_names() - before, item["name"])
            self._loaded[item["name"]] = item["sha256"]
            loaded.append(item["name"])
        return loaded

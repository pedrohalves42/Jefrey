"""Le os registros do Jefrey (todos os arquivos rodiziados) e resume o que deu errado: erros e avisos agrupados por tipo, com quantas vezes e quando.

Uso:  python scripts/log_audit.py [pasta_dos_registros] [horas]
Nada de segredo: o proprio registro ja e filtrado; aqui so se agrupam mensagens (numeros e ids viram marcadores).
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

NOISE = ("uvicorn.access",)  # linhas de acesso normais; so interessam os codigos 4xx/5xx abaixo


def default_dir() -> Path:
    return Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "Jefrey" / "logs"


def norm(msg: str) -> str:
    msg = re.sub(r"[0-9a-f]{8,}", "<id>", msg)
    msg = re.sub(r"\d+(?:\.\d+)?", "<n>", msg)
    msg = re.sub(r"(user|thread|path)=\S+", r"\1=<x>", msg)
    return msg[:170]


def parse(line: str):
    m = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d+ (\w+) ([\w.]+): (.*)", line)
    if m:
        return m.group(1), m.group(2), m.group(3), m.group(4)
    if line.startswith("{"):
        try:
            d = json.loads(line)
            return str(d.get("asctime", ""))[:19], str(d.get("levelname", "")), str(d.get("name", "")), str(d.get("message", ""))
        except ValueError:
            return None
    return None


def main() -> int:
    d = Path(sys.argv[1]) if len(sys.argv) > 1 else default_dir()
    hours = float(sys.argv[2]) if len(sys.argv) > 2 else 24 * 3
    since = datetime.now() - timedelta(hours=hours)
    groups: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    http_bad: Counter = Counter()
    total = 0
    for f in sorted(d.glob("jefrey.log*")):
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            p = parse(line)
            if not p:
                continue
            ts, level, name, msg = p
            try:
                if datetime.fromisoformat(ts) < since:
                    continue
            except ValueError:
                continue
            total += 1
            if name.startswith("uvicorn.access"):
                m = re.search(r'"(\w+) (\S+) HTTP/[\d.]+" (\d{3})', msg)
                if m and m.group(3)[0] in "45":
                    path = re.sub(r"/[0-9a-f]{16,}", "/<id>", m.group(2).split("?")[0])
                    http_bad[(m.group(3), m.group(1), path)] += 1
                continue
            if level in ("WARNING", "ERROR", "CRITICAL"):
                groups[(level, name, norm(msg))].append(ts)
    print(f"{total} linhas lidas nos ultimos {hours:g} h em {d}\n")
    print("== ERROS ==")
    for (lv, name, msg), ts in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        if lv != "WARNING":
            print(f"{len(ts):>5}x {lv:<8}{name}: {msg}   (de {ts[0]} a {ts[-1]})")
    print("\n== AVISOS ==")
    for (lv, name, msg), ts in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        if lv == "WARNING":
            print(f"{len(ts):>5}x {name}: {msg}   (ultimo {ts[-1]})")
    print("\n== PEDIDOS COM CODIGO 4xx/5xx ==")
    for (code, method, path), n in http_bad.most_common(25):
        print(f"{n:>5}x {code} {method} {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

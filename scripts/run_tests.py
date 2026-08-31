"""run_tests - Suite Integrada Jefrey 6.4 (AXIOM/CIPHER)."""
from __future__ import annotations
import argparse
import datetime
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import TypedDict
from xml.sax.saxutils import escape as xml_escape

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

STEPS = [
    ("setup --check", [sys.executable, "scripts/setup.py", "--check"], 25),
    ("verify_env",    [sys.executable, "scripts/verify_env.py"],       15),
    ("smoke_test",    [sys.executable, "-m", "scripts.smoke_test"],    90),
    ("verify_p1",     [sys.executable, "scripts/verify_p1.py"],        60),
    ("verify_p2",     [sys.executable, "scripts/verify_p2.py"],        60),
]

SECRET_RE = re.compile(r"(SECRET_KEY|PASSWORD|API_KEY|TOKEN)[=:\s]+\S+", re.IGNORECASE)

def mask(s: str) -> str:
    """Masca segredos sem quebrar em ':' vs '='."""
    def _repl(m: re.Match[str]) -> str:
        raw = m.group(0)
        # preserva chave até delimitador, mascara valor
        if "=" in raw:
            return raw.split("=", 1)[0] + "=****"
        if ":" in raw:
            return raw.split(":", 1)[0] + ":****"
        return raw[:12] + "=****"
    return SECRET_RE.sub(_repl, s)

class StepResult(TypedDict):
    name: str
    ok: bool
    code: int
    out: str
    dt: float
    skipped: bool
    cmd: str

def run_step(name: str, cmd: list[str], timeout: int) -> StepResult:
    t0 = time.monotonic()
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=str(ROOT),
            env=env,
        )
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        ok = proc.returncode == 0
        # AXIOM fail-loud: se subprocess retornou 0 mas stdout contem FAIL/Traceback, marcar falha
        if ok:
            # ignora resumo "0 FAIL" - conta FAILs reais
            if "Traceback" in out and "Traceback (most recent call" not in out:
                # traceback real do filho (nao thread reader)
                pass
            # heuristica: se filho logou FAIL mas retornou 0 (ex: smoke assertion mascarada)
            fails = len(re.findall(r"\bFAIL\b", out))
            zero_fails = len(re.findall(r"0\s+FAIL", out))
            if fails > zero_fails and "FAIL" in out:
                # smoke_test imprime "[red]FAIL" ou "FAIL <nome>"
                # mas PASS contem "0 FAIL" no resumo da suite filha; se fails>zero_fails => falha real
                # verifica se ha linha com status FAIL no Rich table do filho
                if re.search(r"FAIL", out):
                    # so falha se nao for apenas o header "Status" contendo FAIL como coluna
                    # conta linhas com FAIL que nao sao "0 FAIL"
                    ok = False
            if "Traceback" in out and "AssertionError" in out:
                ok = False
        dt = time.monotonic() - t0
        return {"name": name, "cmd": " ".join(cmd), "ok": ok, "code": proc.returncode, "out": out, "dt": dt, "skipped": False}
    except subprocess.TimeoutExpired as e:
        dt = time.monotonic() - t0
        # text=True => stdout/stderr sao str | None, nao bytes (fix G4)
        stdout_s = e.stdout if isinstance(e.stdout, str) else (e.stdout.decode("utf-8", errors="replace") if isinstance(e.stdout, (bytes, bytearray)) else str(e.stdout or ""))
        stderr_s = e.stderr if isinstance(e.stderr, str) else (e.stderr.decode("utf-8", errors="replace") if isinstance(e.stderr, (bytes, bytearray)) else "")
        out = (stdout_s or "") + "\n" + (stderr_s or "") + f"\nTIMEOUT after {timeout}s"
        return {"name": name, "cmd": " ".join(cmd), "ok": False, "code": 124, "out": out, "dt": dt, "skipped": False}
    except FileNotFoundError as e:
        return {"name": name, "cmd": " ".join(cmd), "ok": False, "code": 127, "out": str(e), "dt": 0.0, "skipped": False}

def main() -> int:
    ap = argparse.ArgumentParser(description="Jefrey Suite Integrada 6.4")
    ap.add_argument("--quick", action="store_true", help="Apenas setup+smoke (<35s)")
    ap.add_argument("--ci", action="store_true", help="Gera reports/junit.xml")
    ap.add_argument("--verbose", action="store_true", help="Mostra stdout de cada step")
    args = ap.parse_args()

    steps = STEPS
    if args.quick:
        steps = [s for s in steps if s[0] in ("setup --check", "smoke_test")]

    console.print(Panel(f"[bold]Jefrey Suite Integrada 6.4[/bold]\nAXIOM + CIPHER  |  {'--quick' if args.quick else 'completo'}  |  {'--ci' if args.ci else ''}", border_style="blue"))

    results: list[StepResult] = []
    for name, cmd, timeout in steps:
        # skip if file not exists (verify_p*) - robusto a "-m" (G4)
        if any("verify_p" in c for c in cmd) and not any((ROOT / c).exists() for c in cmd if c.startswith("scripts/")):
            # verifica especificamente o alvo verify_p
            target_exists = any((ROOT / part).exists() for part in cmd if "verify_p" in part)
            # fallback: checa todos scripts/verify_p* existencia via prefix
            has_verify = any("verify_p" in c for c in cmd)
            if has_verify and not target_exists:
                # tenta resolver verify_p*.py explicitamente
                verify_file = next((c for c in cmd if "verify_p" in c), "")
                if verify_file and not (ROOT / verify_file).exists() and not (ROOT / f"scripts/{verify_file.split('/')[-1]}").exists():
                    # verifica se algum verify_p* existe no fs para decidir skip
                    # modo simples: se arquivo nao existe, skip
                    maybe = ROOT / verify_file
                    if not maybe.exists():
                        console.print(f"[dim]SKIP {name} (not found: {verify_file})[/dim]")
                        results.append({"name": name, "cmd": " ".join(cmd), "ok": True, "code": 0, "out": "", "dt": 0.0, "skipped": True})
                        continue
        console.print(f"[cyan]> {name}[/cyan]  [dim]{' '.join(cmd)}  timeout={timeout}s[/dim]")
        r = run_step(name, cmd, timeout)
        results.append(r)
        if args.verbose:
            console.print(f"[dim]{mask(r['out'][-2000:])}[/dim]", markup=False)
        if r["ok"]:
            console.print(f"[green]  PASS {name}  {r['dt']:.1f}s[/green]")
        else:
            console.print(f"[red]  FAIL {name}  code={r['code']}  {r['dt']:.1f}s[/red]")
            console.print(mask(r["out"][-1500:]), markup=False)
        # fail-fast on CIPHER gate
        if name == "setup --check" and not r["ok"]:
            console.print("[red]Gate CIPHER falhou -- abortando suite[/red]")
            break

    # Rich table
    table = Table(title="Suite 6.4 -- Resultado")
    table.add_column("Step", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Tempo", justify="right")
    for r in results:
        if r.get("skipped"):
            table.add_row(r["name"], "[dim]SKIP[/dim]", "-")
        elif r["ok"]:
            table.add_row(r["name"], "[green]PASS[/green]", f"{r['dt']:.1f}s")
        else:
            table.add_row(r["name"], "[red]FAIL[/red]", f"{r['dt']:.1f}s")
    console.print(table)

    total = sum(r["dt"] for r in results)
    passed = sum(1 for r in results if r.get("ok") and not r.get("skipped"))
    failed = sum(1 for r in results if not r.get("ok"))
    skipped = sum(1 for r in results if r.get("skipped"))
    console.print(Panel(f"{'[green]' if failed==0 else '[red]'} {passed} PASS  {failed} FAIL  {skipped} SKIP  --  {total:.1f}s total", border_style="green" if failed==0 else "red"))

    # Reports
    reports = ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    md = reports / f"test_run_{ts}.md"
    lines = [f"# Jefrey Test Run {ts}", f"Mode: {'quick' if args.quick else 'full'}  CI: {args.ci}", "", "| Step | Status | Tempo | Detalhe |", "|---|---|---|---|"]
    for r in results:
        status = "SKIP" if r.get("skipped") else ("PASS" if r["ok"] else "FAIL")
        detail = "" if r.get("skipped") else mask(r["out"][-300:].replace("\n"," ").replace("|","/").strip()[:120])
        lines.append(f"| {r['name']} | {status} | {r['dt']:.1f}s | {detail} |")
    lines.append("")
    lines.append(f"**Total: {passed} PASS / {failed} FAIL / {skipped} SKIP -- {total:.1f}s**")
    md.write_text("\n".join(lines), encoding="utf-8")
    console.print(f"[dim]Relatorio: {md}[/dim]")

    # JUnit
    if args.ci:
        junit = reports / "junit.xml"
        cases = []
        for r in results:
            if r.get("skipped"):
                cases.append(f'  <testcase name="{xml_escape(r["name"])}" classname="jefrey"><skipped/></testcase>')
            elif r["ok"]:
                cases.append(f'  <testcase name="{xml_escape(r["name"])}" classname="jefrey" time="{r["dt"]:.1f}"/>')
            else:
                esc = xml_escape(mask(r["out"][-2000:]))[:4000]
                cases.append(f'  <testcase name="{xml_escape(r["name"])}" classname="jefrey" time="{r["dt"]:.1f}"><failure message="FAIL {xml_escape(r["name"])}">{esc}</failure></testcase>')
        junit.write_text("\n".join(['<?xml version="1.0" encoding="UTF-8"?>', f'<testsuite name="jefrey" tests="{len(results)}" failures="{failed}" skipped="{skipped}">'] + cases + ['</testsuite>']), encoding="utf-8")
        console.print(f"[dim]JUnit: {junit}[/dim]")

    (reports / ".gitkeep").touch(exist_ok=True)

    return 0 if failed == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())

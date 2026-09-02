"""Setup Inicial - Jefrey (Etapa 6.3 - AXIOM/CIPHER)."""
from __future__ import annotations
import argparse
import secrets
import shutil
import subprocess
import sys
from pathlib import Path
import re

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
from rich.panel import Panel

console = Console()

DIRS = [
    "data/chroma_db",
    "data/workflows",
    "config/credentials",
    "config/tokens",
    "config/prompts/skills",
    "logs",
    "data",
]

def create_directories() -> None:
    for d in DIRS:
        Path(d).mkdir(parents=True, exist_ok=True)
    for d in ("config/credentials", "config/tokens"):
        try:
            Path(d).chmod(0o700)
        except Exception:
            pass
    console.print("[green]OK[/green] Diretorios criados")

def _gen_hex32() -> str:
    return secrets.token_hex(32)

def _gen_db_pw() -> str:
    return secrets.token_urlsafe(16)

def ensure_env(force: bool = False, non_interactive: bool = False, is_dev: bool = False) -> Path:
    env_path = Path(".env")
    example_path = Path(".env.example")
    if not example_path.exists():
        console.print("[red]ERRO: .env.example nao encontrado[/red]")
        sys.exit(1)
    if env_path.exists() and not force:
        console.print("[yellow].env ja existe - preservando (use --force para regenerar)[/yellow]")
        content = env_path.read_text(encoding="utf-8")
        changed = False
        if "CHANGE_ME_GENERATE_HEX32" in content:
            content = content.replace("CHANGE_ME_GENERATE_HEX32", _gen_hex32())
            changed = True
        if "JEFREY_DATABASE__PASSWORD=CHANGE_ME_STRONG" in content:
            content = content.replace("JEFREY_DATABASE__PASSWORD=CHANGE_ME_STRONG", f"JEFREY_DATABASE__PASSWORD={_gen_db_pw()}")
            changed = True
        if "GRAFANA_PASSWORD=CHANGE_ME" in content:
            content = content.replace("GRAFANA_PASSWORD=CHANGE_ME", f"GRAFANA_PASSWORD={_gen_db_pw()}")
            changed = True
        # corrige secret vazio
        if "JEFREY_API__SECRET_KEY=\n" in content:
            content = content.replace("JEFREY_API__SECRET_KEY=\n", f"JEFREY_API__SECRET_KEY={_gen_hex32()}\n")
            changed = True
        if changed:
            env_path.write_text(content, encoding="utf-8")
            try:
                env_path.chmod(0o600)
            except Exception:
                pass
            console.print("[green]OK[/green] .env atualizado (placeholders preenchidos)")
        return env_path
    if env_path.exists() and force:
        import datetime
        backup = Path(f".env.bak.{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}")
        shutil.copy(env_path, backup)
        console.print(f"[dim]Backup: {backup}[/dim]")
    shutil.copy(example_path, env_path)
    content = env_path.read_text(encoding="utf-8")
    if "CHANGE_ME_GENERATE_HEX32" in content:
        content = content.replace("CHANGE_ME_GENERATE_HEX32", _gen_hex32())
    if "JEFREY_DATABASE__PASSWORD=CHANGE_ME_STRONG" in content:
        content = content.replace("JEFREY_DATABASE__PASSWORD=CHANGE_ME_STRONG", f"JEFREY_DATABASE__PASSWORD={_gen_db_pw()}")
    if "GRAFANA_PASSWORD=CHANGE_ME" in content:
        content = content.replace("GRAFANA_PASSWORD=CHANGE_ME", f"GRAFANA_PASSWORD={_gen_db_pw()}")
    # --dev overlay (Kleppmann single source: DEV local usa ollama/768 sem quebrar postgres)
    if is_dev:
        content = re.sub(r"^JEFREY_LLM__PROVIDER=.*", "JEFREY_LLM__PROVIDER=ollama", content, flags=re.MULTILINE)
        content = re.sub(r"^JEFREY_LLM__MODEL=.*", "JEFREY_LLM__MODEL=llama3.1:8b", content, flags=re.MULTILINE)
        content = re.sub(r"^JEFREY_LLM__BASE_URL=.*", "JEFREY_LLM__BASE_URL=http://localhost:11434", content, flags=re.MULTILINE)
        content = re.sub(r"^JEFREY_MEMORY__LONG_TERM__EMBEDDING_MODEL=.*", "JEFREY_MEMORY__LONG_TERM__EMBEDDING_MODEL=nomic-embed-text", content, flags=re.MULTILINE)
        content = re.sub(r"^JEFREY_MEMORY__LONG_TERM__EMBEDDING_DIM=.*", "JEFREY_MEMORY__LONG_TERM__EMBEDDING_DIM=768", content, flags=re.MULTILINE)
        content = re.sub(r"^JEFREY_DATABASE__PASSWORD=.*", "JEFREY_DATABASE__PASSWORD=jefrey", content, flags=re.MULTILINE)
        content = re.sub(r"^JEFREY_DATABASE__URL=.*", "JEFREY_DATABASE__URL=postgresql+psycopg://jefrey:jefrey@localhost:5432/jefrey", content, flags=re.MULTILINE)
    env_path.write_text(content, encoding="utf-8")
    try:
        env_path.chmod(0o600)
    except Exception:
        pass
    console.print("[green]OK[/green] .env criado a partir de .env.example (segredos gerados)")
    if not non_interactive:
        console.print("[yellow]Edite .env e preencha TAVILY_API_KEY / OPENAI_API_KEY se necessario[/yellow]")
    return env_path

def validate_env() -> int:
    try:
        from src.jefrey.core.config import reload_settings
        s = reload_settings()
        warnings: list[str] = []
        if hasattr(s, "api") and hasattr(s.api, "validate_for_production"):
            warnings.extend(s.api.validate_for_production())
        # DEV: senha "jefrey" permitida quando JEFREY_DEBUG=true (docker local); em prod (DEBUG=false) exige senha forte
        if (not s.database.password or "CHANGE_ME" in s.database.password) or (s.database.password == "jefrey" and not s.debug):
            warnings.append("JEFREY_DATABASE__PASSWORD ainda eh default/inseguro (permitido apenas com JEFREY_DEBUG=true)")
        if not s.api.secret_key or len(s.api.secret_key) < 32:
            warnings.append("JEFREY_API__SECRET_KEY vazio ou curto (<32)")
        if s.mcp.service_role not in s.mcp.allowed_roles:
            warnings.append(f"JEFREY_MCP__SERVICE_ROLE={s.mcp.service_role} nao esta em ALLOWED_ROLES={s.mcp.allowed_roles}")
        if warnings:
            console.print(Panel("\n".join(f"- {w}" for w in warnings), title="[red]Validacao falhou[/red]", border_style="red"))
            return 1
        console.print("[green]OK[/green] Validacao config.py passou (CIPHER-019/002/001 OK)")
        return 0
    except Exception as e:
        console.print(f"[red]ERRO validacao: {e}[/red]")
        import traceback
        traceback.print_exc()
        return 1

def main() -> None:
    parser = argparse.ArgumentParser(description="Jefrey Setup 6.3 - AXIOM/CIPHER")
    parser.add_argument("--non-interactive", action="store_true", help="Sem prompts (CI/Docker)")
    parser.add_argument("--force", action="store_true", help="Sobrescreve .env (com backup)")
    parser.add_argument("--check", action="store_true", help="Apenas valida .env existente")
    parser.add_argument("--dev", action="store_true", help="Perfil DEV local: ollama/nomic-embed-text/768/jefrey (compose postgres)")
    parser.add_argument("--prod", action="store_true", help="Perfil PROD: openai/1536/senha forte")
    parser.add_argument("--install-deps", action="store_true", help="Instala requirements")
    args = parser.parse_args()
    if args.check:
        create_directories()
        sys.exit(validate_env())
    console.print(Panel("[bold blue]Jefrey - Setup 6.3[/bold blue]\nAXIOM + CIPHER + 10 Livros Base", border_style="blue"))
    create_directories()
    if args.non_interactive:
        ensure_env(force=args.force, non_interactive=True, is_dev=args.dev)
        sys.exit(validate_env())
    else:
        from rich.prompt import Confirm
        env_path = Path(".env")
        if env_path.exists() and not args.force:
            if Confirm.ask(".env ja existe. Regenerar com segredos?", default=False):
                ensure_env(force=True, is_dev=args.dev)
            else:
                ensure_env(force=False, is_dev=args.dev)
        else:
            ensure_env(force=args.force, is_dev=args.dev)
        if Confirm.ask("Instalar dependencias?", default=False):
            req = Path("requirements.txt")
            if req.exists():
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(req)], check=False)
        if Confirm.ask("Validar config agora?", default=True):
            validate_env()
        if Confirm.ask("Executar smoke_test?", default=False):
            subprocess.run([sys.executable, "-m", "scripts.smoke_test"], check=False)
        console.print(Panel("[green]Setup concluido![/green]\nEdite .env (TAVILY/OPENAI) e rode: jefrey chat", border_style="green"))

if __name__ == "__main__":
    main()

"""Setup Inicial - Jefrey."""
from __future__ import annotations
import asyncio
import os
import shutil
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

console = Console()


def create_directories():
    """Cria estrutura de diretórios necessária."""
    dirs = [
        "data/chroma_db",
        "data/workflows",
        "config/credentials",
        "config/tokens",
        "config/prompts/skills",
        "logs",
    ]
    
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
    
    console.print("[green]✅ Diretórios criados[/green]")


def create_env_file():
    """Cria arquivo .env a partir do .env.example se não existir."""
    env_path = Path(".env")
    example_path = Path(".env.example")
    
    if env_path.exists():
        if not Confirm.ask(".env já existe. Sobrescrever?"):
            console.print("[yellow]Mantendo .env existente[/yellow]")
            return
    
    if example_path.exists():
        shutil.copy(example_path, env_path)
        console.print("[green]✅ .env criado a partir de .env.example[/green]")
        console.print("[yellow]⚠️  Edite .env e adicione suas chaves de API[/yellow]")
    else:
        console.print("[red]❌ .env.example não encontrado[/red]")


def create_settings_yaml():
    """Cria settings.yaml se não existir."""
    settings_path = Path("config/settings.yaml")
    
    if settings_path.exists():
        if not Confirm.ask("config/settings.yaml já existe. Sobrescrever?"):
            console.print("[yellow]Mantendo settings.yaml existente[/yellow]")
            return
    
    # O arquivo já deve existir pois criamos antes
    console.print("[green]✅ config/settings.yaml já existe[/green]")


def setup_google_calendar():
    """Guia para configurar Google Calendar OAuth."""
    console.print(Panel("""
[bold]🔧 Setup Google Calendar OAuth[/bold]

[cyan]Passo a passo:[/cyan]

1. Acesse: https://console.cloud.google.com/
2. Crie um projeto ou selecione existente
3. Menu → APIs & Services → Library
4. Busque "Google Calendar API" → Enable
5. Menu → APIs & Services → Credentials
6. Create Credentials → OAuth Client ID
   - Application type: Desktop app
   - Name: Jefrey Calendar
7. Download JSON
8. Salve como: [bold]config/credentials/google_calendar.json[/bold]
9. Edite .env:
   [dim]JEFREY_INTEGRATIONS__GOOGLE_CALENDAR__ENABLED=true[/dim]
   [dim]JEFREY_INTEGRATIONS__GOOGLE_CALENDAR__CREDENTIALS_FILE=config/credentials/google_calendar.json[/dim]

Após salvar o JSON, execute novamente este setup para testar a conexão.
""", title="Google Calendar Setup", border_style="blue"))
    
    creds_file = Path("config/credentials/google_calendar.json")
    if creds_file.exists():
        if Confirm.ask("Arquivo de credenciais encontrado. Testar conexão OAuth agora?"):
            test_google_calendar()


def test_google_calendar():
    """Testa conexão Google Calendar."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        console.print("[red]❌ Dependências não instaladas. Execute:[/red]")
        console.print("[dim]pip install google-api-python-client google-auth-oauthlib[/dim]")
        return
    
    SCOPES = ["https://www.googleapis.com/auth/calendar"]
    creds_file = Path("config/credentials/google_calendar.json")
    token_file = Path("config/tokens/google_calendar_token.json")
    
    try:
        creds = None
        if token_file.exists():
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
                creds = flow.run_local_server(port=0)
            
            token_file.parent.mkdir(parents=True, exist_ok=True)
            with open(token_file, "w") as f:
                f.write(creds.to_json())
        
        service = build("calendar", "v3", credentials=creds)
        # Teste simples
        result = service.calendarList().list(maxResults=1).execute()
        
        console.print("[green]✅ Google Calendar conectado com sucesso![/green]")
        console.print(f"Calendários disponíveis: {len(result.get('items', []))}")
        
    except Exception as e:
        console.print(f"[red]❌ Erro na conexão: {e}[/red]")


def setup_gmail():
    """Guia para configurar Gmail OAuth."""
    console.print(Panel("""
[bold]🔧 Setup Gmail OAuth[/bold]

[cyan]Passo a passo:[/cyan]

1. Acesse: https://console.cloud.google.com/
2. APIs & Services → Library → "Gmail API" → Enable
3. Credentials → Create Credentials → OAuth Client ID
   - Application type: Desktop app
   - Name: Jefrey Gmail
4. Download JSON
5. Salve como: [bold]config/credentials/gmail.json[/bold]
6. Edite .env:
   [dim]JEFREY_INTEGRATIONS__GMAIL__ENABLED=true[/dim]
   [dim]JEFREY_INTEGRATIONS__GMAIL__CREDENTIALS_FILE=config/credentials/gmail.json[/dim]
""", title="Gmail Setup", border_style="blue"))
    
    creds_file = Path("config/credentials/gmail.json")
    if creds_file.exists():
        if Confirm.ask("Arquivo de credenciais encontrado. Testar conexão OAuth agora?"):
            test_gmail()


def test_gmail():
    """Testa conexão Gmail."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        console.print("[red]❌ Dependências não instaladas[/red]")
        return
    
    SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
    creds_file = Path("config/credentials/gmail.json")
    token_file = Path("config/tokens/gmail_token.json")
    
    try:
        creds = None
        if token_file.exists():
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
                creds = flow.run_local_server(port=0)
            
            token_file.parent.mkdir(parents=True, exist_ok=True)
            with open(token_file, "w") as f:
                f.write(creds.to_json())
        
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        
        console.print("[green]✅ Gmail conectado com sucesso![/green]")
        console.print(f"E-mail: {profile.get('emailAddress')}")
        
    except Exception as e:
        console.print(f"[red]❌ Erro na conexão: {e}[/red]")


def install_dependencies():
    """Instala dependências via pip."""
    if Confirm.ask("Instalar dependências de produção (requirements.txt)?"):
        console.print("[yellow]Instalando...[/yellow]")
        os.system(f"{sys.executable} -m pip install -r requirements.txt")
        console.print("[green]✅ Dependências de produção instaladas[/green]")
    
    if Confirm.ask("Instalar dependências de desenvolvimento (requirements-dev.txt)?"):
        console.print("[yellow]Instalando...[/yellow]")
        os.system(f"{sys.executable} -m pip install -r requirements-dev.txt")
        console.print("[green]✅ Dependências de desenvolvimento instaladas[/green]")


def run_smoke_test():
    """Executa smoke test."""
    if Confirm.ask("Executar smoke test agora?"):
        console.print("[yellow]Executando testes...[/yellow]")
        result = os.system(f"{sys.executable} -m scripts.smoke_test")
        if result == 0:
            console.print("[green]✅ Todos os testes passaram![/green]")
        else:
            console.print("[red]❌ Alguns testes falharam[/red]")


async def main():
    """Setup principal interativo."""
    console.print(Panel("""
[bold blue]🤖 Jefrey - Setup Inicial[/bold blue]

Este script vai configurar seu ambiente Jefrey.
""", border_style="blue"))
    
    # 1. Diretórios
    create_directories()
    
    # 2. Arquivos de config
    create_env_file()
    create_settings_yaml()
    
    # 3. Dependências
    install_dependencies()
    
    # 4. OAuth (opcional)
    console.print("\n[bold]🔐 Configuração OAuth (Opcional)[/bold]")
    
    if Confirm.ask("Configurar Google Calendar?"):
        setup_google_calendar()
    
    if Confirm.ask("Configurar Gmail?"):
        setup_gmail()
    
    # 5. Smoke test
    run_smoke_test()
    
    # Final
    console.print(Panel("""
[bold green]🎉 Setup Concluído![/bold green]

[cyan]Próximos passos:[/cyan]

1. Edite [bold].env[/bold] com suas chaves:
   - OPENAI_API_KEY (ou configure outro provider)
   - TAVILY_API_KEY (para busca web)

2. Inicie o Jefrey:
   [dim]jefrey chat[/dim]
   ou
   [dim]python -m src.jefrey.interfaces.cli chat[/dim]

3. Teste comandos:
   - "Salva nota: título 'Teste', conteúdo 'Funcionando!'"
   - "Busca na web: notícias IA hoje"
   - "/skills" para ver ferramentas disponíveis

[bold]Documentação:[/bold] README.md
""", border_style="green"))


if __name__ == "__main__":
    asyncio.run(main())
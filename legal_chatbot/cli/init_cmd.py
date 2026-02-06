"""Init command implementation"""

from rich.console import Console
from rich.panel import Panel

from legal_chatbot.db.sqlite import init_db
from legal_chatbot.db.chroma import init_chroma

console = Console()


def init_command():
    """Initialize database and vector store"""
    console.print(Panel.fit(
        "[bold blue]Initializing Legal Chatbot[/bold blue]",
        border_style="blue"
    ))

    # Initialize SQLite
    console.print("\n[yellow]1. Initializing SQLite database...[/yellow]")
    try:
        init_db()
        console.print("[green]   [OK] SQLite database initialized[/green]")
    except Exception as e:
        console.print(f"[red]   [FAIL] Failed to initialize SQLite: {e}[/red]")
        return

    # Initialize storage
    console.print("\n[yellow]2. Initializing vector store...[/yellow]")
    try:
        init_chroma()
        console.print("[green]   [OK] Vector store initialized[/green]")
    except Exception as e:
        console.print(f"[red]   [FAIL] Failed to initialize vector store: {e}[/red]")
        return

    console.print(Panel.fit(
        "[bold green][OK] Initialization complete![/bold green]\n\n"
        "Next steps:\n"
        "1. Add sample data: [cyan]python -m legal_chatbot add-sample[/cyan]\n"
        "2. Start chatting: [cyan]python -m legal_chatbot chat \"Your question\"[/cyan]",
        border_style="green"
    ))

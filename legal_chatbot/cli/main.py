"""Main CLI application"""

import asyncio
import json
import sys
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich.markdown import Markdown

from legal_chatbot.cli.init_cmd import init_command
from legal_chatbot.cli.chat_cmd import chat_command

app = typer.Typer(
    name="legal-chatbot",
    help="Vietnamese Legal Chatbot with RAG-based Q&A",
    add_completion=False,
)

console = Console(force_terminal=True)


@app.command("init")
def init():
    """Initialize database and vector store"""
    init_command()


@app.command("chat")
def chat(
    query: str = typer.Argument(..., help="Your legal question"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Ask a legal question and get an answer with citations"""
    chat_command(query, json_output)


@app.command("crawl")
def crawl(
    source: str = typer.Option("thuvienphapluat", "--source", "-s", help="Data source"),
    limit: int = typer.Option(3, "--limit", "-l", help="Number of documents to crawl"),
    output_dir: str = typer.Option("./data/raw", "--output", "-o", help="Output directory"),
):
    """Crawl legal documents from source"""
    from legal_chatbot.services.crawler import CrawlerService, CrawlConfig

    console.print(f"[blue]Crawling {limit} documents from {source}...[/blue]")

    config = CrawlConfig(source=source, limit=limit, output_dir=output_dir)
    crawler = CrawlerService(config)

    async def run_crawl():
        count = 0
        async for doc in crawler.crawl(limit=limit):
            filepath = crawler.save_document(doc)
            console.print(f"  [green][OK][/green] {doc.title[:50]}...")
            count += 1
        return count

    try:
        count = asyncio.run(run_crawl())
        console.print(f"\n[green][OK] Crawled {count} documents to {output_dir}[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@app.command("index")
def index(
    input_path: str = typer.Option("./data/raw", "--input", "-i", help="Path to raw documents"),
    status: bool = typer.Option(False, "--status", help="Show index status only"),
):
    """Index documents into the knowledge base"""
    from legal_chatbot.services.indexer import IndexerService, IndexConfig

    if status:
        indexer = IndexerService()
        stats = indexer.get_index_stats()
        console.print(f"Total articles indexed: {stats['total_articles']}")
        console.print(f"Total documents: {stats['documents']}")
        return

    console.print(f"[blue]Indexing documents from {input_path}...[/blue]")

    config = IndexConfig(input_dir=input_path)
    indexer = IndexerService(config)

    try:
        result = indexer.index_from_directory()
        console.print(f"\n[green][OK] Indexed {result.articles_indexed} articles from {result.documents_processed} documents[/green]")

        if result.errors:
            console.print("\n[yellow]Warnings:[/yellow]")
            for error in result.errors:
                console.print(f"  - {error}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@app.command("templates")
def templates():
    """List available contract templates"""
    from legal_chatbot.services.generator import GeneratorService

    generator = GeneratorService()
    template_list = generator.list_templates()

    if not template_list:
        console.print("[yellow]No templates available[/yellow]")
        return

    table = Table(title="Available Contract Templates")
    table.add_column("Type", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Description")
    table.add_column("Fields", justify="right")

    for template in template_list:
        table.add_row(
            template.template_type.value,
            template.name,
            template.description[:40] + "..." if len(template.description) > 40 else template.description,
            str(len(template.required_fields)),
        )

    console.print(table)
    console.print("\nUse [cyan]python -m legal_chatbot template <type> --fields[/cyan] to see required fields")


@app.command("template")
def template_detail(
    template_type: str = typer.Argument(..., help="Template type (rental, sale, service)"),
    fields: bool = typer.Option(False, "--fields", "-f", help="Show required fields"),
):
    """Show template details"""
    from legal_chatbot.services.generator import GeneratorService

    generator = GeneratorService()
    template = generator.get_template(template_type)

    if not template:
        console.print(f"[red]Template '{template_type}' not found[/red]")
        console.print("Available templates: rental, sale, service")
        return

    console.print(Panel(
        f"[bold]{template.name}[/bold]\n\n{template.description}",
        title=f"Template: {template_type}",
        border_style="blue",
    ))

    if fields:
        table = Table(title="Required Fields")
        table.add_column("Field", style="cyan")
        table.add_column("Label", style="green")
        table.add_column("Type")
        table.add_column("Required")

        for field in template.required_fields:
            table.add_row(
                field.name,
                field.label,
                field.field_type,
                "Yes" if field.required else "No",
            )

        console.print(table)


@app.command("generate")
def generate(
    template_type: str = typer.Option(..., "--template", "-t", help="Template type (rental, sale, service)"),
    output: str = typer.Option("contract.pdf", "--output", "-o", help="Output file path"),
    data: str = typer.Option(None, "--data", "-d", help="JSON data for fields"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive mode"),
):
    """Generate a contract from template"""
    from legal_chatbot.services.generator import GeneratorService

    generator = GeneratorService()
    template = generator.get_template(template_type)

    if not template:
        console.print(f"[red]Template '{template_type}' not found[/red]")
        return

    # Get field data
    field_data = {}

    if data:
        try:
            field_data = json.loads(data)
        except json.JSONDecodeError:
            console.print("[red]Invalid JSON data[/red]")
            return

    elif interactive:
        console.print(f"\n[blue]Generating: {template.name}[/blue]")
        console.print("Enter values for each field (press Enter for default):\n")

        for field in template.required_fields:
            default = field.default_value or ""
            prompt = f"{field.label}"
            if default:
                prompt += f" [{default}]"
            prompt += ": "

            value = input(prompt).strip()
            if not value and default:
                value = default

            if value:
                field_data[field.name] = value

    else:
        # Use empty/placeholder data for demo
        console.print("[yellow]No data provided. Using placeholder values.[/yellow]")
        console.print("Use --interactive or --data to provide actual values.\n")
        for field in template.required_fields:
            field_data[field.name] = field.default_value or "________________"

    # Validate and generate
    errors = generator.validate_data(template_type, field_data)
    if errors:
        console.print("[yellow]Validation warnings (using placeholder values):[/yellow]")
        for error in errors:
            console.print(f"  - {error}")

    try:
        result = generator.generate(template_type, field_data, output)
        console.print(f"\n[green][OK] Contract generated: {output}[/green]")
        console.print("[dim]Note: This is a reference document only, not legal advice.[/dim]")
    except Exception as e:
        console.print(f"[red]Error generating contract: {e}[/red]")


@app.command("interactive")
def interactive_chat():
    """Start interactive chat session with contract creation and editing"""
    from legal_chatbot.services.interactive_chat import get_interactive_chat_service

    console.print(Panel.fit(
        "[bold blue]Xin chao![/bold blue]\n\n"
        "Minh la tro ly phap ly cua ban. Minh co the:\n"
        "  • Tra loi cau hoi ve phap luat Viet Nam\n"
        "  • Tao hop dong (thue nha, mua ban, dich vu, lao dong)\n"
        "  • Xuat hop dong ra PDF\n\n"
        "[dim]Goi y: \"tao hop dong thue nha\", \"xem hop dong\", \"xuat pdf\"[/dim]\n"
        "[dim]Noi 'exit' de thoat[/dim]",
        title="Legal Chatbot",
        border_style="blue"
    ))

    service = get_interactive_chat_service()
    session = service.start_session()

    console.print()

    while True:
        try:
            user_input = Prompt.ask("[bold green]Ban[/bold green]")

            if not user_input.strip():
                continue

            if user_input.lower() in ['exit', 'quit', 'thoat', 'q']:
                console.print("\n[blue]Tam biet! Hen gap lai.[/blue]")
                break

            # Show loading indicator
            with console.status("[blue]Dang xu ly...[/blue]"):
                response = asyncio.run(service.chat(user_input))

            # Display response - cleaner, more human
            console.print()
            console.print(Panel(
                response.message,
                title="[bold blue]Bot[/bold blue]",
                border_style="blue",
                padding=(0, 1)
            ))
            console.print()

        except KeyboardInterrupt:
            console.print("\n\n[blue]Tam biet![/blue]")
            break
        except Exception as e:
            console.print(f"\n[red]Loi: {e}[/red]\n")


@app.command("research")
def research(
    topic: str = typer.Argument(..., help="Legal topic to research"),
    max_sources: int = typer.Option(3, "--sources", "-s", help="Maximum sources to crawl"),
):
    """Research a legal topic from thuvienphapluat.vn"""
    from legal_chatbot.services.research import ResearchService

    console.print(f"[blue]Researching: {topic}[/blue]")
    console.print(f"[dim]Max sources: {max_sources}[/dim]\n")

    async def run_research():
        service = ResearchService()
        return await service.research(topic, max_sources)

    with console.status("[blue]Dang crawl va phan tich...[/blue]"):
        try:
            result = asyncio.run(run_research())
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            return

    # Display results
    console.print(Panel(
        result.analyzed_content or "Khong tim thay thong tin",
        title="[bold]Ket qua nghien cuu[/bold]",
        border_style="green"
    ))

    if result.legal_articles:
        console.print(f"\n[cyan]Tim thay {len(result.legal_articles)} dieu luat lien quan[/cyan]")
        for i, article in enumerate(result.legal_articles[:5], 1):
            console.print(f"  {i}. Dieu {article['article_number']}: {article['content'][:100]}...")

    if result.suggested_contract_type:
        console.print(f"\n[yellow]Goi y: Co the tao hop dong loai '{result.suggested_contract_type}'[/yellow]")

    console.print(f"\n[dim]Sources crawled: {len(result.crawled_sources)}[/dim]")


@app.command("pipeline")
def pipeline_command(
    action: str = typer.Argument(..., help="Action: crawl, status, categories, browse, fix-data"),
    category: str = typer.Option(None, "--category", "-c", help="Category name (e.g., dat_dai)"),
    doc: str = typer.Option(None, "--doc", "-d", help="Document number for browse (e.g., 31/2024/QH15)"),
    limit: int = typer.Option(20, "--limit", "-l", help="Max documents to crawl"),
):
    """Run data pipeline to crawl and index legal documents"""
    from legal_chatbot.services.pipeline import PipelineService, CATEGORIES, URL_CATEGORY_MAP
    from legal_chatbot.db.supabase import get_database

    if action == "categories":
        table = Table(title="Available Categories")
        table.add_column("Name", style="cyan")
        table.add_column("Display Name", style="green")
        table.add_column("Description")
        table.add_column("URLs", justify="right")
        for cat in CATEGORIES.values():
            table.add_row(
                cat.name, cat.display_name,
                cat.description[:50] + "..." if len(cat.description) > 50 else cat.description,
                str(len(cat.document_urls)),
            )
        console.print(table)
        return

    if action == "browse":
        db = get_database()

        if doc and category:
            # Level 3: Browse articles in a specific document
            # Find document by document_number
            client = db._read() if hasattr(db, "_read") else None
            if not client:
                console.print("[red]Browse requires Supabase mode[/red]")
                return
            doc_result = (
                client.table("legal_documents")
                .select("id, title, document_number, document_type")
                .ilike("document_number", f"%{doc}%")
                .limit(1)
                .execute()
            )
            if not doc_result.data:
                console.print(f"[red]Document '{doc}' not found[/red]")
                return
            doc_row = doc_result.data[0]
            console.print(f"\n[bold]{doc_row['title']}[/bold]")
            console.print(f"[dim]{doc_row['document_number']} ({doc_row['document_type']})[/dim]\n")

            articles = db.browse_articles(doc_row["id"])
            if not articles:
                console.print("[yellow]No articles found[/yellow]")
                return

            current_chapter = None
            for art in articles:
                chapter = art.get("chapter") or "Khong co chuong"
                if chapter != current_chapter:
                    current_chapter = chapter
                    console.print(f"\n[bold cyan]{chapter}[/bold cyan]")
                title = art.get("title") or ""
                content_preview = (art.get("content") or "")[:80].replace("\n", " ")
                console.print(f"  Dieu {art['article_number']}. {title}")
                if content_preview and not title:
                    console.print(f"    [dim]{content_preview}...[/dim]")

        elif category:
            # Level 2: Browse documents in a category
            docs = db.browse_documents(category)
            if not docs:
                console.print(f"[yellow]No documents in category '{category}'[/yellow]")
                console.print("Run [cyan]pipeline fix-data[/cyan] to sync categories first.")
                return

            cat_display = CATEGORIES[category].display_name if category in CATEGORIES else category
            table = Table(title=f"Documents in {cat_display}")
            table.add_column("#", justify="right", style="dim")
            table.add_column("Document Number", style="cyan")
            table.add_column("Type", style="green")
            table.add_column("Title")
            table.add_column("Articles", justify="right", style="yellow")
            for i, d in enumerate(docs, 1):
                table.add_row(
                    str(i),
                    d["document_number"],
                    d["document_type"],
                    d["title"][:60] + "..." if len(d.get("title", "")) > 60 else d.get("title", ""),
                    str(d["article_count"]),
                )
            console.print(table)
            console.print(f"\n[dim]Drill down: pipeline browse -c {category} -d \"<document_number>\"[/dim]")

        else:
            # Level 1: Browse all categories
            cats = db.browse_categories()
            if not cats:
                console.print("[yellow]No categories in DB[/yellow]")
                console.print("Run [cyan]pipeline fix-data[/cyan] to sync categories.")
                return

            table = Table(title="Legal Categories Overview")
            table.add_column("Name", style="cyan")
            table.add_column("Display Name", style="green")
            table.add_column("Description")
            table.add_column("Documents", justify="right", style="yellow")
            table.add_column("Articles", justify="right", style="yellow")
            for cat in cats:
                table.add_row(
                    cat["name"],
                    cat["display_name"],
                    cat.get("description", "")[:40],
                    str(cat["document_count"]),
                    str(cat["article_count"]),
                )
            console.print(table)
            console.print(f"\n[dim]Drill down: pipeline browse -c <category_name>[/dim]")
        return

    if action == "fix-data":
        db = get_database()
        pipeline = PipelineService(db=db)

        # Step 1: Fix category_id on existing documents (auto-detect from title)
        console.print("[blue]Step 1: Auto-detecting categories from document titles...[/blue]")
        if not hasattr(db, "_write"):
            console.print("[red]fix-data requires Supabase mode[/red]")
            return

        client = db._write()
        docs = client.table("legal_documents").select("id, title, source_url, category_id").execute()
        fixed = 0
        for d in docs.data:
            if d.get("category_id"):
                continue  # Already has category
            title = d.get("title") or ""
            if title:
                cat_id = pipeline.category_from_document_title(title)
                if cat_id:
                    client.table("legal_documents").update(
                        {"category_id": cat_id}
                    ).eq("id", d["id"]).execute()
                    fixed += 1
                    console.print(f"  Fixed: {title[:50]}...")
        console.print(f"  Fixed {fixed} documents")

        # Step 2: Show summary
        console.print("\n[green]Fix-data completed![/green]")
        status = db.get_status()
        console.print(f"  Categories: {status.get('categories', 0)}")
        console.print(f"  Documents: {status.get('documents', 0)}")
        console.print(f"  Articles: {status.get('articles', 0)}")
        console.print(f"\n[dim]Run 'pipeline browse' to see the organized structure[/dim]")
        return

    if action == "crawl":
        if not category:
            console.print("[red]--category is required for crawl[/red]")
            console.print("Use [cyan]python -m legal_chatbot pipeline categories[/cyan] to see available.")
            return

        db = get_database()
        pipeline = PipelineService(db=db)

        force_crawl = "--force" in sys.argv
        console.print(f"[blue]Pipeline: {category}{'  (force)' if force_crawl else ''}[/blue]")

        async def run_pipeline():
            return await pipeline.run(category, limit=limit, force=force_crawl)

        with console.status("[blue]Running pipeline...[/blue]"):
            run = asyncio.run(run_pipeline())

        if run.status.value == "completed":
            console.print(f"[green]Pipeline completed![/green]")
            console.print(f"  Documents: {run.documents_new} new / {run.documents_found} found / {run.documents_skipped} skipped")
            console.print(f"  Articles: {run.articles_indexed}")
            console.print(f"  Embeddings: {run.embeddings_generated}")
            if run.duration_seconds:
                console.print(f"  Duration: {run.duration_seconds:.1f}s")
        else:
            console.print(f"[red]Pipeline failed: {run.error_message}[/red]")
        return

    if action == "status":
        # Show pipeline + worker status
        db = get_database()
        status = db.get_status()
        console.print(f"[cyan]DB:[/cyan] {status.get('documents', 0)} docs, {status.get('articles', 0)} articles")

        # Show category stats with worker info
        if hasattr(db, "get_all_categories_with_stats"):
            cats = db.get_all_categories_with_stats()
            table = Table(title="Category Pipeline Status")
            table.add_column("Category", style="cyan")
            table.add_column("Display", style="green")
            table.add_column("Docs", justify="right")
            table.add_column("Articles", justify="right")
            table.add_column("Schedule", style="yellow")
            table.add_column("Worker", style="dim")
            table.add_column("Last Run", style="dim")
            for c in cats:
                table.add_row(
                    c["name"],
                    c["display_name"],
                    str(c.get("document_count", 0)),
                    str(c.get("article_count", 0)),
                    c.get("worker_schedule", "-"),
                    c.get("worker_status", "-"),
                    str(c.get("last_worker_run_at", "-"))[:19] if c.get("last_worker_run_at") else "-",
                )
            console.print(table)
        return

    if action == "worker":
        # Worker subcommands: start, stop, status, schedule
        worker_action = category or ""  # Reuse --category for worker action
        if not worker_action:
            # Check if there's a positional argument after "worker"
            try:
                idx = sys.argv.index("worker")
                if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith("-"):
                    worker_action = sys.argv[idx + 1]
            except (ValueError, IndexError):
                pass

        if not worker_action:
            console.print("[yellow]Usage: pipeline worker <start|stop|status|schedule>[/yellow]")
            return

        from legal_chatbot.services.worker import get_worker
        worker = get_worker()

        if worker_action == "start":
            console.print("[blue]Starting background worker...[/blue]")
            asyncio.run(worker.start())
            status = worker.get_status()
            if status.is_running:
                console.print(f"[green]Worker started! {len(status.jobs)} jobs scheduled.[/green]")
                for job in status.jobs:
                    console.print(f"  {job.category}: {job.trigger}")
                console.print("\n[dim]Worker will run in background. Press Ctrl+C to stop.[/dim]")
                # Keep running
                try:
                    asyncio.get_event_loop().run_forever()
                except KeyboardInterrupt:
                    worker.stop()
                    console.print("[yellow]Worker stopped.[/yellow]")
            else:
                console.print("[red]Worker failed to start[/red]")

        elif worker_action == "stop":
            worker.stop()
            console.print("[green]Worker stopped.[/green]")

        elif worker_action == "status":
            status = worker.get_status()
            console.print(f"[cyan]Worker running:[/cyan] {'Yes' if status.is_running else 'No'}")
            if status.jobs:
                table = Table(title="Scheduled Jobs")
                table.add_column("Category", style="cyan")
                table.add_column("Name")
                table.add_column("Trigger", style="yellow")
                table.add_column("Next Run", style="green")
                table.add_column("Status", style="dim")
                for job in status.jobs:
                    table.add_row(
                        job.category,
                        job.name,
                        job.trigger,
                        str(job.next_run)[:19] if job.next_run else "-",
                        job.status,
                    )
                console.print(table)

        elif worker_action == "schedule":
            # Show schedule from DB
            db = get_database()
            cats = db.get_all_categories_with_stats()
            table = Table(title="Worker Schedule")
            table.add_column("Category", style="cyan")
            table.add_column("Schedule", style="yellow")
            table.add_column("Time", style="green")
            table.add_column("Status", style="dim")
            table.add_column("Last Run", style="dim")
            table.add_column("Last Status", style="dim")
            for c in cats:
                table.add_row(
                    c["name"],
                    c.get("worker_schedule", "weekly"),
                    c.get("worker_time", "02:00"),
                    c.get("worker_status", "active"),
                    str(c.get("last_worker_run_at", "-"))[:19] if c.get("last_worker_run_at") else "-",
                    c.get("last_worker_status", "-") or "-",
                )
            console.print(table)

        else:
            console.print(f"[red]Unknown worker action: {worker_action}[/red]")
            console.print("Available: start, stop, status, schedule")
        return

    console.print(f"[red]Unknown action: {action}[/red]")
    console.print("Available: crawl, categories, browse, fix-data, status, worker")


@app.command("db")
def db_command(
    action: str = typer.Argument(..., help="Action: migrate, status, sync"),
):
    """Manage database connection and schema"""
    from legal_chatbot.db.supabase import get_database
    from legal_chatbot.utils.config import get_settings
    from pathlib import Path

    settings = get_settings()

    if action == "migrate":
        if settings.db_mode == "supabase":
            migration_002 = (
                Path(__file__).parent.parent / "db" / "migrations" / "002_supabase.sql"
            )
            migration_003 = (
                Path(__file__).parent.parent / "db" / "migrations" / "003_worker.sql"
            )
            migration_004 = (
                Path(__file__).parent.parent / "db" / "migrations" / "004_cached_articles.sql"
            )
            console.print("[blue]SQL migration files:[/blue]")
            console.print(f"  1. {migration_002}")
            console.print(f"  2. {migration_003}")
            console.print(f"  3. {migration_004}")
            console.print(
                "\n[yellow]Run these SQL files in Supabase SQL Editor (in order).[/yellow]"
            )
            console.print(
                "Then run [cyan]python -m legal_chatbot db status[/cyan] to verify."
            )
        else:
            from legal_chatbot.db.sqlite import init_db

            init_db()
            console.print("[green]SQLite database initialized.[/green]")

    elif action == "status":
        db = get_database()
        status = db.get_status()
        table = Table(title=f"Database Status ({status['mode']})")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")
        for k, v in status.items():
            table.add_row(str(k), str(v))
        console.print(table)

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Available actions: migrate, status")


@app.command("audit")
def audit_command(
    action: str = typer.Argument(..., help="Action: list, show, verify"),
    audit_id: str = typer.Argument(None, help="Audit ID (for show/verify)"),
    limit: int = typer.Option(20, "--limit", "-l", help="Number of audits to list"),
    audit_type: str = typer.Option("all", "--type", "-t", help="Filter: research, contract, all"),
):
    """View and verify audit trails for research and contracts"""
    from legal_chatbot.db.supabase import get_database
    from legal_chatbot.services.audit import AuditService

    db = get_database()
    audit_service = AuditService(db)

    if action == "list":
        audits = audit_service.list_audits(limit=limit, audit_type=audit_type)
        if not audits:
            console.print("[yellow]No audits found[/yellow]")
            return

        table = Table(title="Recent Audits")
        table.add_column("ID", style="cyan", max_width=10)
        table.add_column("Type", style="magenta")
        table.add_column("Summary", style="green")
        table.add_column("Date")
        for a in audits:
            table.add_row(
                a["id"][:8] + "...",
                a["type"],
                a["summary"][:50],
                str(a.get("created_at", ""))[:19],
            )
        console.print(table)

    elif action == "show":
        if not audit_id:
            console.print("[red]Audit ID required for show[/red]")
            return

        audit = audit_service.get_research_audit(audit_id)
        if audit:
            console.print(Panel(
                f"[bold]Type:[/bold] research\n"
                f"[bold]Query:[/bold] {audit.query}\n"
                f"[bold]Response:[/bold] {audit.response[:300]}...\n"
                f"[bold]Sources:[/bold] {len(audit.sources)}\n"
                f"[bold]Law versions:[/bold] {len(audit.law_versions)}\n"
                f"[bold]Created:[/bold] {audit.created_at}",
                title=f"Audit: {audit_id[:8]}...",
                border_style="blue",
            ))
            if audit.sources:
                console.print("\n[cyan]Sources:[/cyan]")
                for s in audit.sources:
                    console.print(f"  - Dieu {s.article_number} ({s.document_title}) [similarity: {s.similarity:.3f}]")
            if audit.law_versions:
                console.print("\n[cyan]Law Versions:[/cyan]")
                for lv in audit.law_versions:
                    console.print(f"  - {lv.title} ({lv.document_number}) — {lv.status}")
        else:
            audit = audit_service.get_contract_audit(audit_id)
            if audit:
                console.print(Panel(
                    f"[bold]Type:[/bold] contract\n"
                    f"[bold]Contract type:[/bold] {audit.contract_type}\n"
                    f"[bold]PDF:[/bold] {audit.pdf_storage_path}\n"
                    f"[bold]Law versions:[/bold] {len(audit.law_versions)}\n"
                    f"[bold]Created:[/bold] {audit.created_at}",
                    title=f"Audit: {audit_id[:8]}...",
                    border_style="blue",
                ))
            else:
                console.print(f"[red]Audit not found: {audit_id}[/red]")

    elif action == "verify":
        if not audit_id:
            console.print("[red]Audit ID required for verify[/red]")
            return

        result = audit_service.verify_audit(audit_id)

        if result.get("error"):
            console.print(f"[red]{result['error']}[/red]")
            return

        status_icon = "[green]✓[/green]" if result["is_current"] else "[red]✗[/red]"
        console.print(Panel(
            f"[bold]Audit:[/bold] {audit_id[:8]}... ({result.get('audit_type', 'unknown')})\n"
            f"[bold]Laws checked:[/bold] {result['law_versions_checked']}\n"
            f"[bold]Status:[/bold] {status_icon} {'All law versions current' if result['is_current'] else 'Some laws outdated'}\n"
            f"[bold]Verified:[/bold] {result['verified_at'][:19]}",
            title="Audit Verification",
            border_style="green" if result["is_current"] else "red",
        ))

        if result["outdated_laws"]:
            console.print("\n[red]Outdated laws:[/red]")
            for law in result["outdated_laws"]:
                console.print(
                    f"  - {law['document_number']}: {law['old_status']} → {law['new_status']}"
                )
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Available: list, show, verify")


@app.command("sync-articles")
def sync_articles(
    input_file: str = typer.Argument(..., help="JSON file with articles to sync"),
):
    """Sync new/updated legal articles into the database with embeddings.

    JSON format:
    {
      "document_id": "blds_2015",
      "document_title": "Bộ luật Dân sự 2015",
      "document_number": "91/2015/QH13",
      "articles": [
        {"article_number": 430, "title": "...", "content": "..."}
      ]
    }
    """
    from legal_chatbot.utils.config import get_settings

    settings = get_settings()
    if settings.db_mode != "supabase":
        console.print("[red]sync-articles requires db_mode=supabase[/red]")
        return

    from pathlib import Path
    import hashlib
    import uuid

    path = Path(input_file)
    if not path.exists():
        console.print(f"[red]File not found: {input_file}[/red]")
        return

    data = json.loads(path.read_text(encoding="utf-8"))
    doc_id = data.get("document_id", "")
    doc_title = data.get("document_title", "")
    articles_raw = data.get("articles", [])

    if not articles_raw:
        console.print("[yellow]No articles in file[/yellow]")
        return

    from legal_chatbot.services.embedding import EmbeddingService
    from legal_chatbot.services.pipeline import PipelineService
    from legal_chatbot.db.supabase import get_database

    db = get_database()
    embedding_service = EmbeddingService()

    # Determine category from document title (not contract_type)
    pipeline = PipelineService(db=db)
    category_id = pipeline.category_from_document_title(doc_title)
    if category_id:
        console.print(f"[dim]Category detected from title: '{doc_title}'[/dim]")
    else:
        console.print(f"[yellow]Could not detect category from title: '{doc_title}'[/yellow]")

    # Upsert document first
    doc_data = {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, doc_id or doc_title)),
        "title": doc_title,
        "document_number": data.get("document_number", ""),
        "document_type": data.get("document_type", "luat"),
        "issuing_authority": data.get("issuing_authority", ""),
        "status": data.get("status", "active"),
    }
    if category_id:
        doc_data["category_id"] = category_id
    with console.status("[blue]Syncing document..."):
        db.upsert_document(doc_data)

    # Prepare articles with embeddings
    console.print(f"[blue]Generating embeddings for {len(articles_raw)} articles...[/blue]")
    texts = [a.get("content", "") for a in articles_raw]
    embeddings = embedding_service.embed_batch(texts)

    rows = []
    for article, emb in zip(articles_raw, embeddings):
        art_id = str(uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{doc_id}_dieu_{article.get('article_number', 0)}"
        ))
        rows.append({
            "id": art_id,
            "document_id": doc_data["id"],
            "article_number": article.get("article_number", 0),
            "title": article.get("title", ""),
            "content": article.get("content", ""),
            "chapter": article.get("chapter", ""),
            "document_title": doc_title,
            "document_type": doc_data["document_type"],
            "embedding": emb,
        })

    with console.status("[blue]Upserting articles..."):
        count = db.upsert_articles(rows)

    console.print(f"[green]Synced {count} articles from '{doc_title}' into DB[/green]")


@app.command("search")
def search_articles(
    query: str = typer.Argument(..., help="Search query in Vietnamese"),
    top_k: int = typer.Option(10, "--top-k", "-k", help="Number of results"),
):
    """Search for relevant legal articles in the database (vector search)"""
    from legal_chatbot.utils.config import get_settings

    settings = get_settings()
    if settings.db_mode != "supabase":
        console.print("[red]Search requires db_mode=supabase[/red]")
        return

    from legal_chatbot.services.embedding import EmbeddingService
    from legal_chatbot.db.supabase import get_database

    db = get_database()
    embedding_service = EmbeddingService()

    with console.status("[blue]Searching...[/blue]"):
        query_embedding = embedding_service.embed_single(query)
        articles = db.search_articles(query_embedding=query_embedding, top_k=top_k)

    if not articles:
        console.print("[yellow]No matching articles found[/yellow]")
        return

    # Output as JSON for programmatic use
    results = []
    for a in articles:
        results.append({
            "article_number": a.get("article_number"),
            "title": a.get("title", ""),
            "document_title": a.get("document_title", ""),
            "content": a.get("content", ""),
            "similarity": round(a.get("similarity", 0), 4),
        })

    console.print(json.dumps(results, ensure_ascii=False, indent=2))


@app.command("db-articles")
def db_articles(
    category: str = typer.Argument(None, help="Category name (e.g. dat_dai, lao_dong)"),
    keyword: str = typer.Option(None, "--keyword", "-q", help="Filter by keyword in content/title"),
    limit: int = typer.Option(30, "--limit", "-l", help="Max articles to return"),
):
    """List articles from DB by category or keyword (no embedding model needed).

    Fast, instant query — no embedding model, no LLM. Just reads from Supabase.
    Use this for browsing articles or researching a topic by category.
    """
    from legal_chatbot.utils.config import get_settings

    settings = get_settings()
    if settings.db_mode != "supabase":
        console.print("[red]db-articles requires db_mode=supabase[/red]")
        return

    from legal_chatbot.db.supabase import get_database

    db = get_database()
    client = db._read()

    # If no category, list available categories with article counts
    if category is None and keyword is None:
        cats = client.table("legal_categories").select("name, display_name, article_count").order("name").execute()
        if not cats.data:
            console.print(json.dumps({"categories": [], "message": "Chua co du lieu phap luat nao."}, ensure_ascii=False))
            return
        console.print(json.dumps({
            "categories": [
                {"name": c["name"], "display_name": c["display_name"], "article_count": c.get("article_count", 0)}
                for c in cats.data if c.get("article_count", 0) > 0
            ]
        }, ensure_ascii=False, indent=2))
        return

    # Build query
    # Use PostgREST embedded join to get document_title from legal_documents
    query = client.table("articles").select(
        "article_number, title, content, document_id, legal_documents(title, document_number)"
    )

    # Filter by category
    if category:
        # Resolve category_id
        cat_result = client.table("legal_categories").select("id").eq("name", category).limit(1).execute()
        if not cat_result.data:
            console.print(json.dumps({"error": f"Category '{category}' not found", "articles": []}, ensure_ascii=False))
            return
        cat_id = cat_result.data[0]["id"]

        # Get document IDs in this category
        docs = client.table("legal_documents").select("id").eq("category_id", cat_id).execute()
        if not docs.data:
            console.print(json.dumps({"error": f"No documents in category '{category}'", "articles": []}, ensure_ascii=False))
            return
        doc_ids = [d["id"] for d in docs.data]
        query = query.in_("document_id", doc_ids)

    # Filter by keyword
    if keyword:
        query = query.or_(f"content.ilike.%{keyword}%,title.ilike.%{keyword}%")

    query = query.order("article_number").limit(limit)
    result = query.execute()

    if not result.data:
        console.print(json.dumps({"articles": [], "message": f"Khong tim thay articles cho '{category or keyword}'"}, ensure_ascii=False))
        return

    # Extract document_title from embedded join
    articles = []
    for a in result.data:
        doc_info = a.get("legal_documents") or {}
        articles.append({
            "article_number": a.get("article_number"),
            "title": a.get("title", ""),
            "document_title": doc_info.get("title", ""),
            "content": a.get("content", ""),
        })

    console.print(json.dumps({
        "category": category,
        "keyword": keyword,
        "total": len(articles),
        "articles": articles,
    }, ensure_ascii=False, indent=2))


@app.command("contract-lookup")
def contract_lookup(
    contract_type: str = typer.Argument(None, help="Contract type (e.g. cho_thue_dat)"),
    list_all: bool = typer.Option(False, "--list", "-l", help="List available templates from DB"),
):
    """Look up a contract template with pre-cached articles from DB.

    No embedding model needed — just reads cached data from Supabase.
    Templates are cached during pipeline crawl (Phase 5).

    Use --list to see all available templates that have been crawled.
    """
    from legal_chatbot.utils.config import get_settings

    settings = get_settings()
    if settings.db_mode != "supabase":
        console.print("[red]contract-lookup requires db_mode=supabase[/red]")
        return

    from legal_chatbot.db.supabase import get_database

    db = get_database()
    client = db._read()

    # --list mode: show available templates from DB
    if list_all or contract_type is None:
        all_tmpls = (
            client.table("contract_templates")
            .select("contract_type, display_name, cached_at, cached_articles")
            .order("contract_type")
            .execute()
        )
        if not all_tmpls.data:
            console.print(json.dumps({"available": [], "message": "Chua co du lieu hop dong nao."}, ensure_ascii=False))
            return

        available = []
        for t in all_tmpls.data:
            cached = t.get("cached_articles") or []
            available.append({
                "contract_type": t["contract_type"],
                "display_name": t["display_name"],
                "articles_count": len(cached),
                "cached": bool(t.get("cached_at")),
            })

        console.print(json.dumps({"available": available}, ensure_ascii=False, indent=2))
        return

    tmpl = (
        client.table("contract_templates")
        .select("*")
        .eq("contract_type", contract_type)
        .limit(1)
        .execute()
    )

    if not tmpl.data:
        console.print(f"[red]Template '{contract_type}' not found[/red]")
        # Show available
        all_tmpls = client.table("contract_templates").select("contract_type, display_name, cached_at").execute()
        if all_tmpls.data:
            console.print("\nAvailable templates:")
            for t in all_tmpls.data:
                cached = "cached" if t.get("cached_at") else "no cache"
                console.print(f"  - {t['contract_type']}: {t['display_name']} ({cached})")
        else:
            console.print("[yellow]No templates found.[/yellow]")
        return

    template = tmpl.data[0]
    cached_articles = template.get("cached_articles") or []
    cached_at = template.get("cached_at")

    if not cached_articles:
        console.print(f"[yellow]Template '{contract_type}' has no cached articles.[/yellow]")
        return

    # Output the full template + cached articles as JSON
    output = {
        "contract_type": template["contract_type"],
        "display_name": template["display_name"],
        "description": template.get("description", ""),
        "required_laws": template.get("required_laws", []),
        "min_articles": template.get("min_articles", 5),
        "search_queries": template.get("search_queries", []),
        "cached_at": cached_at,
        "articles_count": len(cached_articles),
        "articles": cached_articles,
    }

    console.print(json.dumps(output, ensure_ascii=False, indent=2))


@app.command("contract-search")
def contract_search(
    contract_type: str = typer.Argument(..., help="Contract type (e.g. cho_thue_dat, mua_ban_dat)"),
    top_k: int = typer.Option(10, "--top-k", "-k", help="Results per query"),
):
    """Search all relevant law articles for a contract type using its template.

    Loads the contract template from Supabase, runs all search_queries in a single
    process (embedding model loaded once), deduplicates, and outputs JSON.
    """
    from legal_chatbot.utils.config import get_settings

    settings = get_settings()
    if settings.db_mode != "supabase":
        console.print("[red]contract-search requires db_mode=supabase[/red]")
        return

    from legal_chatbot.services.embedding import EmbeddingService
    from legal_chatbot.db.supabase import get_database

    db = get_database()

    # Load template from Supabase
    client = db._read()
    tmpl_result = (
        client.table("contract_templates")
        .select("*")
        .eq("contract_type", contract_type)
        .limit(1)
        .execute()
    )

    if not tmpl_result.data:
        console.print(f"[red]Template '{contract_type}' not found in Supabase[/red]")
        # Show available
        all_tmpls = client.table("contract_templates").select("contract_type, display_name").execute()
        if all_tmpls.data:
            console.print("\nAvailable templates:")
            for t in all_tmpls.data:
                console.print(f"  - {t['contract_type']}: {t['display_name']}")
        return

    tmpl = tmpl_result.data[0]
    queries = tmpl.get("search_queries", [])
    if not queries:
        console.print("[yellow]Template has no search_queries[/yellow]")
        return

    console.print(f"[blue]{tmpl['display_name']}[/blue]")
    console.print(f"[dim]Running {len(queries)} queries (model loads once)...[/dim]")

    # Load embedding model ONCE
    embedding_service = EmbeddingService()

    # Run all queries, merge + dedup results
    seen_ids = set()
    all_results = []

    for i, query in enumerate(queries, 1):
        console.print(f"  [{i}/{len(queries)}] {query[:50]}...")
        query_embedding = embedding_service.embed_single(query)
        articles = db.search_articles(query_embedding=query_embedding, top_k=top_k)

        for a in articles:
            art_key = (a.get("article_number"), a.get("document_title", ""))
            if art_key not in seen_ids:
                seen_ids.add(art_key)
                all_results.append({
                    "article_number": a.get("article_number"),
                    "title": a.get("title", ""),
                    "document_title": a.get("document_title", ""),
                    "content": a.get("content", ""),
                    "similarity": round(a.get("similarity", 0), 4),
                    "query": query,
                })

    # Sort by similarity descending
    all_results.sort(key=lambda x: x["similarity"], reverse=True)

    console.print(f"\n[green]Found {len(all_results)} unique articles[/green]")
    console.print(f"[dim]Min articles required: {tmpl.get('min_articles', 5)}[/dim]")
    console.print(json.dumps(all_results, ensure_ascii=False, indent=2))


@app.command("save-contract")
def save_contract(
    contract_file: str = typer.Argument(..., help="Path to contract JSON file"),
):
    """Save contract to Supabase: articles + documents + audit.

    Similar to legal.pipeline, saves:
    1. legal_documents - parent law documents from legal_references
    2. articles - law articles with embeddings (for future vector search)
    3. contract_audits - the contract audit record
    """
    from legal_chatbot.utils.config import get_settings

    settings = get_settings()
    if settings.db_mode != "supabase":
        console.print("[red]save-contract requires db_mode=supabase[/red]")
        return

    from pathlib import Path

    path = Path(contract_file)
    if not path.exists():
        console.print(f"[red]File not found: {contract_file}[/red]")
        return

    contract = json.loads(path.read_text(encoding="utf-8"))

    import uuid
    import re
    from legal_chatbot.db.supabase import get_database
    from legal_chatbot.services.audit import AuditService
    from legal_chatbot.services.embedding import EmbeddingService
    from legal_chatbot.services.pipeline import PipelineService
    from legal_chatbot.models.audit import ContractAudit, ArticleSource, LawVersion

    db = get_database()
    audit_service = AuditService(db)

    # Sync seed categories
    pipeline = PipelineService(db=db)
    pipeline.sync_categories()

    # --- 1. Save legal_documents + articles (like pipeline) ---
    legal_refs = contract.get("legal_references", [])
    articles_synced = 0

    if legal_refs:
        embedding_service = EmbeddingService()

        # Group refs by law document
        docs_map = {}
        for ref in legal_refs:
            law_name = ref.get("law", ref.get("document_title", ""))
            if law_name not in docs_map:
                docs_map[law_name] = {
                    "title": law_name,
                    "document_number": ref.get("document_number", ""),
                    "articles": [],
                }
            # Extract article number from string like "Điều 463"
            article_str = ref.get("article", "")
            article_num = 0
            match = re.search(r"\d+", article_str)
            if match:
                article_num = int(match.group())
            docs_map[law_name]["articles"].append({
                "article_number": article_num,
                "title": article_str,
                "content": ref.get("description", article_str),
            })

        for law_name, doc_info in docs_map.items():
            # Determine category from each document's title (not contract_type)
            category_id = pipeline.category_from_document_title(law_name)
            if category_id:
                console.print(f"[dim]  {law_name} → category detected[/dim]")

            # Upsert document with per-document category_id
            doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, law_name))
            doc_data = {
                "id": doc_id,
                "title": doc_info["title"],
                "document_number": doc_info["document_number"],
                "document_type": "luat",
                "status": "active",
            }
            if category_id:
                doc_data["category_id"] = category_id
            with console.status(f"[blue]Syncing document: {law_name}..."):
                # Use returned id (may differ if doc already exists)
                doc_id = db.upsert_document(doc_data)

            # Prepare article dicts for embedding (match articles table schema)
            article_dicts = []
            for a in doc_info["articles"]:
                art_id = str(uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{doc_id}_dieu_{a['article_number']}"
                ))
                article_dicts.append({
                    "id": art_id,
                    "document_id": doc_id,
                    "article_number": a["article_number"],
                    "title": a["title"],
                    "content": a["content"],
                    "chapter": "",
                })

            # Embed and store (like pipeline)
            if article_dicts:
                with console.status(f"[blue]Embedding {len(article_dicts)} articles..."):
                    count = embedding_service.embed_and_store(db, article_dicts)
                    articles_synced += count

    # --- 2. Build audit models ---
    audit_refs = []
    for ref in legal_refs:
        audit_refs.append(ArticleSource(
            article_id=ref.get("article_id", ""),
            article_number=ref.get("article_number", 0),
            document_title=ref.get("law", ref.get("document_title", "")),
            similarity=ref.get("similarity", 1.0),
        ))

    law_versions = []
    for lv in contract.get("law_versions", []):
        law_versions.append(LawVersion(
            document_id=lv.get("document_id", ""),
            document_number=lv.get("document_number", ""),
            title=lv.get("title", ""),
            effective_date=lv.get("effective_date"),
            status=lv.get("status", "active"),
        ))

    # --- 3. Save contract audit ---
    audit = ContractAudit(
        contract_type=contract.get("contract_type", "unknown"),
        input_data=contract.get("fields", {}),
        generated_content=json.dumps(contract.get("articles", []), ensure_ascii=False),
        legal_references=audit_refs,
        law_versions=law_versions,
        pdf_storage_path=str(path),
    )

    with console.status("[blue]Saving contract audit..."):
        audit_id = audit_service.save_contract_audit(audit)

    console.print(f"[green]Contract saved to Supabase![/green]")
    console.print(f"  Audit ID: {audit_id}")
    console.print(f"  Type: {contract.get('contract_type', 'unknown')}")
    console.print(f"  Contract articles: {len(contract.get('articles', []))}")
    console.print(f"  Law articles synced: {articles_synced}")
    console.print(f"  Documents synced: {len(docs_map) if legal_refs else 0}")
    console.print(f"\nVerify with: python -m legal_chatbot audit show {audit_id}")


@app.command("add-sample")
def add_sample():
    """Add sample legal data for testing"""
    from legal_chatbot.db.sqlite import init_db, insert_document, insert_article
    from legal_chatbot.db.chroma import add_articles

    console.print("[blue]Adding sample legal data...[/blue]")

    # Initialize DB
    init_db()

    # Sample data - Luat Nha o 2014
    doc = {
        'id': 'luat_nha_o_2014',
        'document_type': 'luat',
        'document_number': '65/2014/QH13',
        'title': 'Luat Nha o 2014',
        'issuing_authority': 'Quoc hoi',
        'status': 'active',
    }
    insert_document(doc)

    # Sample articles
    sample_articles = [
        {
            'id': 'luat_nha_o_2014_dieu_121',
            'document_id': 'luat_nha_o_2014',
            'article_number': 121,
            'title': 'Dieu kien cua nha o tham gia giao dich',
            'content': '''Dieu 121. Dieu kien cua nha o tham gia giao dich

1. Nha o tham gia giao dich phai co du dieu kien sau day:
a) Co giay chung nhan quyen su dung dat, quyen so huu nha o va tai san khac gan lien voi dat theo quy dinh cua phap luat ve dat dai, tru truong hop quy dinh tai khoan 2 Dieu nay;
b) Khong thuoc dien dang co tranh chap, khieu nai, khieu kien ve quyen so huu; dang bi ke bien de thi hanh an hoac de chap hanh quyet dinh hanh chinh cua co quan nha nuoc co tham quyen;
c) Khong thuoc dien da co quyet dinh thu hoi dat, co thong bao giai toa, pha do nha o cua co quan co tham quyen.

2. Giao dich ve mua ban, thue mua nha o hinh thanh trong tuong lai thi nha o phai co du dieu kien theo quy dinh tai Dieu 55 cua Luat nay.''',
            'chapter': 'Chuong VIII: GIAO DICH VE NHA O',
            'document_title': 'Luat Nha o 2014',
            'document_type': 'luat',
        },
        {
            'id': 'luat_nha_o_2014_dieu_122',
            'document_id': 'luat_nha_o_2014',
            'article_number': 122,
            'title': 'Dieu kien cua cac ben tham gia giao dich ve nha o',
            'content': '''Dieu 122. Dieu kien cua cac ben tham gia giao dich ve nha o

1. Ben ban, ben cho thue, ben cho thue mua nha o phai co dieu kien sau day:
a) La chu so huu nha o hoac nguoi duoc chu so huu cho phep, uy quyen de thuc hien giao dich ve nha o theo quy dinh cua Luat nay va phap luat ve dan su;
b) Neu la ca nhan thi phai co day du nang luc hanh vi dan su de thuc hien giao dich ve nha o theo quy dinh cua phap luat ve dan su; neu la to chuc thi phai co tu cach phap nhan, tru truong hop to chuc duoc uy quyen quan ly nha o.

2. Ben mua, ben thue, ben thue mua nha o la ca nhan thi phai co day du nang luc hanh vi dan su de thuc hien giao dich ve nha o theo quy dinh cua phap luat dan su.''',
            'chapter': 'Chuong VIII: GIAO DICH VE NHA O',
            'document_title': 'Luat Nha o 2014',
            'document_type': 'luat',
        },
        {
            'id': 'luat_nha_o_2014_dieu_129',
            'document_id': 'luat_nha_o_2014',
            'article_number': 129,
            'title': 'Cho thue nha o',
            'content': '''Dieu 129. Cho thue nha o

1. Chu so huu nha o co quyen cho thue nha o cua minh theo quy dinh cua Luat nay va phap luat co lien quan.

2. Viec cho thue nha o phai duoc lap thanh hop dong; hop dong cho thue nha o phai co cac noi dung co ban sau day:
a) Ten, dia chi cua ben cho thue va ben thue;
b) Mo ta dac diem cua nha o cho thue;
c) Gia cho thue va phuong thuc thanh toan;
d) Thoi han cho thue;
d) Quyen va nghia vu cua ben cho thue va ben thue;
e) Cam ket cua ben cho thue va ben thue;
g) Cac thoa thuan khac.

3. Hop dong cho thue nha o co the cong chung, chung thuc theo yeu cau cua cac ben.''',
            'chapter': 'Chuong VIII: GIAO DICH VE NHA O',
            'document_title': 'Luat Nha o 2014',
            'document_type': 'luat',
        },
        {
            'id': 'luat_nha_o_2014_dieu_131',
            'document_id': 'luat_nha_o_2014',
            'article_number': 131,
            'title': 'Quyen va nghia vu cua ben cho thue nha o',
            'content': '''Dieu 131. Quyen va nghia vu cua ben cho thue nha o

1. Ben cho thue nha o co cac quyen sau day:
a) Nhan tien thue nha theo thoi han va phuong thuc da thoa thuan trong hop dong;
b) Yeu cau ben thue sua chua phan hu hong do ben thue gay ra;
c) Yeu cau ben thue tra lai nha khi het han hop dong thue hoac cham dut hop dong thue truoc thoi han theo thoa thuan hoac theo quy dinh cua phap luat.

2. Ben cho thue nha o co cac nghia vu sau day:
a) Giao nha o cho ben thue theo dung thoa thuan trong hop dong;
b) Bao dam cho ben thue su dung on dinh nha thue trong thoi han thue;
c) Bao tri, sua chua nha o theo dinh ky hoac theo thoa thuan;
d) Khong duoc don phuong cham dut hop dong thue nha o, tru cac truong hop quy dinh tai Dieu 132 cua Luat nay.''',
            'chapter': 'Chuong VIII: GIAO DICH VE NHA O',
            'document_title': 'Luat Nha o 2014',
            'document_type': 'luat',
        },
    ]

    for article in sample_articles:
        insert_article(article)

    # Add to ChromaDB
    add_articles(sample_articles)

    console.print(f"[green][OK] Added {len(sample_articles)} sample articles[/green]")
    console.print("\nYou can now test chat with:")
    console.print('[cyan]python -m legal_chatbot chat "Dieu kien cho thue nha"[/cyan]')


@app.command("seed-templates")
def seed_templates():
    """Seed contract templates into Supabase (requires db_mode=supabase)."""
    from legal_chatbot.utils.config import get_settings

    settings = get_settings()
    if settings.db_mode != "supabase":
        console.print("[red]seed-templates requires DB_MODE=supabase[/red]")
        raise typer.Exit(1)

    from legal_chatbot.db.supabase import get_database
    from legal_chatbot.services.pipeline import PipelineService, CONTRACT_TEMPLATES

    db = get_database()
    pipeline = PipelineService(db=db)
    pipeline.sync_categories()

    count = 0
    for cat_name in CONTRACT_TEMPLATES:
        n = pipeline.seed_templates_for_category(cat_name)
        if n:
            console.print(f"  [green][OK][/green] {cat_name}: {n} templates")
        count += n

    console.print(f"\n[green][OK] Seeded {count} contract templates[/green]")


@app.command("seed-registry")
def seed_registry():
    """Seed document registry entries into Supabase (requires db_mode=supabase)."""
    from legal_chatbot.utils.config import get_settings

    settings = get_settings()
    if settings.db_mode != "supabase":
        console.print("[red]seed-registry requires DB_MODE=supabase[/red]")
        raise typer.Exit(1)

    from legal_chatbot.db.supabase import get_database
    from legal_chatbot.services.pipeline import PipelineService, CATEGORIES

    db = get_database()
    pipeline = PipelineService(db=db)
    pipeline.sync_categories()

    count = 0
    for cat_name in CATEGORIES:
        n = pipeline.seed_registry_for_category(cat_name)
        if n:
            console.print(f"  [green][OK][/green] {cat_name}: {n} entries")
        count += n

    console.print(f"\n[green][OK] Seeded {count} document registry entries[/green]")


if __name__ == "__main__":
    app()

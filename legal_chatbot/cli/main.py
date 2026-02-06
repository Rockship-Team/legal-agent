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


if __name__ == "__main__":
    app()

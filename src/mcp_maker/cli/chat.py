"""
MCP-Maker Chat CLI — Interactive database chat command.

Provides the ``mcp-maker chat`` command that lets users ask database
questions in natural language via an LLM.
"""

import os

import typer
from rich.markdown import Markdown
from rich.panel import Panel

from mcp_maker.connectors.base import get_connector

from .main import app, console


@app.command()
def chat(
    source: str = typer.Argument(
        ...,
        help="Data source URI (e.g., sqlite:///mydata.db)",
    ),
    api_key: str = typer.Option(
        None,
        "--api-key",
        "-k",
        envvar="OPENAI_API_KEY",
        help=(
            "API key for the LLM provider. "
            "Env vars: OPENAI_API_KEY, OPENROUTER_API_KEY, "
            "XAI_API_KEY, DEEPSEEK_API_KEY"
        ),
    ),
    model: str = typer.Option(
        None,
        "--model",
        "-m",
        help=(
            "LLM model to use. "
            "OpenAI: gpt-4o-mini, gpt-4o. "
            "Grok: grok-3-mini, grok-4. "
            "DeepSeek: deepseek-chat, deepseek-reasoner. "
            "OpenRouter: anthropic/claude-sonnet-4, "
            "google/gemini-2.5-flash, deepseek/deepseek-chat, "
            "meta-llama/llama-3-70b-instruct"
        ),
    ),
    provider: str = typer.Option(
        None,
        "--provider",
        "-p",
        help="LLM provider: openai, openrouter, grok, or deepseek (auto-detected from key)",
    ),
    tables: str = typer.Option(
        None,
        "--tables",
        "-t",
        help="Comma-separated list of tables to include",
    ),
):
    """💬 Chat with your database using natural language.

    Connect to any data source and ask questions — the AI will query
    your database and return answers.

    Supports OpenAI, Grok (xAI), DeepSeek, and OpenRouter (500+ models
    including Claude, Gemini, Llama, Mixtral, and more).

    Examples:
        mcp-maker chat sqlite:///data.db --api-key sk-xxx
        mcp-maker chat sqlite:///data.db --api-key xai-xxx
        mcp-maker chat sqlite:///data.db --provider deepseek --api-key sk-xxx
        mcp-maker chat sqlite:///data.db --api-key sk-or-xxx -m anthropic/claude-sonnet-4
    """
    from mcp_maker import __version__

    # Resolve API key — check provider-specific env vars as fallback.
    # The env var a key came from decides the provider (DeepSeek keys share
    # OpenAI's "sk-" prefix, so the prefix alone can't distinguish them).
    if not api_key:
        for env_var, env_provider in (
            ("OPENROUTER_API_KEY", "openrouter"),
            ("XAI_API_KEY", "grok"),
            ("GROK_API_KEY", "grok"),
            ("DEEPSEEK_API_KEY", "deepseek"),
        ):
            env_key = os.environ.get(env_var)
            if env_key:
                api_key = env_key
                if not provider:
                    provider = env_provider
                break

    if not api_key:
        console.print(
            "[red]Error:[/red] No API key provided. "
            "Use --api-key or set OPENAI_API_KEY / OPENROUTER_API_KEY / "
            "XAI_API_KEY / DEEPSEEK_API_KEY."
        )
        raise typer.Exit(1)

    # Auto-detect provider from key prefix
    if not provider:
        if api_key.startswith("sk-or-"):
            provider = "openrouter"
        elif api_key.startswith("xai-"):
            provider = "grok"
        else:
            provider = "openai"

    provider = provider.lower()
    if provider not in ("openai", "openrouter", "grok", "deepseek"):
        console.print(
            f"[red]Error:[/red] Unknown provider: {provider}. "
            "Use: openai, openrouter, grok, or deepseek."
        )
        raise typer.Exit(1)

    # Resolve base_url and default model
    base_url = None
    if provider == "openrouter":
        base_url = "https://openrouter.ai/api/v1"
        if not model:
            model = "openai/gpt-4o-mini"
        provider_label = f"OpenRouter ({model})"
    elif provider == "grok":
        base_url = "https://api.x.ai/v1"
        if not model:
            model = "grok-3-mini"
        provider_label = f"Grok ({model})"
    elif provider == "deepseek":
        base_url = "https://api.deepseek.com/v1"
        if not model:
            model = "deepseek-chat"
        provider_label = f"DeepSeek ({model})"
    else:
        if not model:
            model = "gpt-4o-mini"
        provider_label = f"OpenAI ({model})"

    # Connect and inspect
    console.print(Panel(
        "[bold]💬 MCP-Maker Chat[/bold]",
        subtitle=f"v{__version__}",
    ))

    try:
        connector = get_connector(source)
        connector.validate()
        with console.status("Inspecting database..."):
            schema = connector.inspect()
    except Exception as e:
        console.print(f"[red]Connection failed:[/red] {e}")
        raise typer.Exit(1)

    # Filter tables if requested
    if tables:
        table_filter = {t.strip() for t in tables.split(",")}
        schema.tables = [t for t in schema.tables if t.name in table_filter]

    if not schema.tables:
        console.print("[red]No tables found.[/red]")
        raise typer.Exit(1)

    # Resolve database path for SQLite
    db_path = _resolve_db_path(source, schema)
    if not db_path:
        console.print(
            "[red]Error:[/red] Chat currently supports SQLite databases. "
            "Support for other databases is coming soon."
        )
        raise typer.Exit(1)

    # Initialize agent
    try:
        from mcp_maker.core.agent import ChatAgent, QueryExecutor

        executor = QueryExecutor(db_path, schema)
        agent = ChatAgent(
            api_key=api_key,
            model=model,
            schema=schema,
            executor=executor,
            base_url=base_url,
        )
    except ImportError:
        console.print(
            "[red]Error:[/red] OpenAI package not installed. "
            "Run: [cyan]pip install 'mcp-maker\\[chat]'[/cyan]"
        )
        raise typer.Exit(1)

    # Print connection summary
    table_names = ", ".join(t.name for t in schema.tables)
    total_tools = len(agent.tools)
    console.print(f"  📊 Connected: [cyan]{len(schema.tables)} tables[/cyan] ({table_names})")
    console.print(f"  🔧 [cyan]{total_tools} tools[/cyan] available (read-only)")
    console.print(f"  🧠 Provider: [cyan]{provider_label}[/cyan]")
    console.print()
    console.print(
        "  💡 Type [bold]exit[/bold] to quit, "
        "[bold]schema[/bold] to see tables, "
        "[bold]clear[/bold] to reset conversation"
    )
    console.print()

    # REPL loop
    while True:
        try:
            question = console.input("[bold green]You >[/bold green] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n👋 Goodbye!")
            break

        if not question:
            continue

        # Built-in commands
        if question.lower() in ("exit", "quit", "q"):
            console.print("👋 Goodbye!")
            break

        if question.lower() == "schema":
            _print_schema(schema)
            continue

        if question.lower() == "clear":
            agent.history = [agent.history[0]]  # Keep system prompt
            console.print("[dim]Conversation cleared.[/dim]")
            continue

        # Ask the agent
        try:
            with console.status("[dim]Thinking...[/dim]"):
                answer = agent.ask(question)

            # Show tool calls
            if agent.last_tool_calls:
                for call in agent.last_tool_calls:
                    console.print(f"  [dim]🔧 {call}[/dim]")
                console.print()

            # Render answer
            console.print(Markdown(answer))
            console.print()

        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            console.print()


def _resolve_db_path(source: str, schema) -> str | None:
    """Extract the database file path from the source URI."""
    if schema.source_type == "sqlite":
        path = source
        for prefix in ("sqlite:///", "sqlite://"):
            if path.startswith(prefix):
                path = path[len(prefix):]
                break
        return os.path.expanduser(path)

    if schema.source_type == "files":
        # Files connector stores data as CSV/JSON;
        # the generated server uses its own data dir.
        # For chat, we'd need a different executor.
        return None

    return None


def _print_schema(schema):
    """Print a formatted schema overview."""
    from rich.table import Table as RichTable

    table = RichTable(title="📊 Database Schema")
    table.add_column("Table", style="cyan")
    table.add_column("Columns", style="green")
    table.add_column("Rows", justify="right")

    for t in schema.tables:
        cols = ", ".join(c.name for c in t.columns)
        rows = str(t.row_count) if t.row_count is not None else "—"
        table.add_row(t.name, cols, rows)

    console.print(table)
    console.print()

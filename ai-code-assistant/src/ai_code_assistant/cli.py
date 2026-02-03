"""Command-line interface for AI Code Assistant."""

import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import click
from dotenv import load_dotenv
from rich.console import Console

# Load environment variables from .env file
# First try current directory, then home directory
if Path(".env").exists():
    load_dotenv(Path(".env"))
elif Path.home().joinpath(".cognify.env").exists():
    load_dotenv(Path.home().joinpath(".cognify.env"))
elif Path.home().joinpath(".env").exists():
    load_dotenv(Path.home().joinpath(".env"))
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from ai_code_assistant import __version__
from ai_code_assistant.config import Config, load_config, get_language_by_extension
from ai_code_assistant.llm import LLMManager
from ai_code_assistant.reviewer import CodeAnalyzer
from ai_code_assistant.generator import CodeGenerator
from ai_code_assistant.chat import ChatSession
from ai_code_assistant.editor import FileEditor
from ai_code_assistant.utils import FileHandler, get_formatter

console = Console()


def get_components(config_path: Optional[Path] = None, provider: Optional[str] = None, model: Optional[str] = None):
    """Initialize and return all components with optional provider/model override."""
    config = load_config(config_path)
    llm = LLMManager(config, provider=provider, model=model)
    return config, llm


@click.group()
@click.version_option(version=__version__, prog_name="ai-assist")
@click.option("--config", "-c", type=click.Path(exists=True, path_type=Path), help="Config file path")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def main(ctx, config: Optional[Path], verbose: bool):
    """AI Code Assistant - Review and generate code using local LLMs."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["verbose"] = verbose


@main.command()
@click.argument("files", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option("--type", "-t", "review_type", default="full",
              type=click.Choice(["full", "quick", "security"]), help="Review type")
@click.option("--format", "-f", "output_format", default="console",
              type=click.Choice(["console", "markdown", "json"]), help="Output format")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output file path")
@click.option("--recursive", "-r", is_flag=True, help="Recursively review directories")
@click.pass_context
def review(ctx, files: Tuple[Path, ...], review_type: str, output_format: str,
           output: Optional[Path], recursive: bool):
    """Review code files for issues and improvements."""
    import time
    from ai_code_assistant.analytics import get_collector

    collector = get_collector()
    start_time = time.time()
    success = True

    if not files:
        console.print("[red]Error:[/red] No files specified")
        sys.exit(1)

    try:
        config, llm = get_components(ctx.obj.get("config_path"))
        analyzer = CodeAnalyzer(config, llm)
        file_handler = FileHandler(config)
        formatter = get_formatter(output_format, config.output.use_colors)

        # Collect all files to review
        all_files = []
        for file_path in files:
            if file_path.is_dir():
                all_files.extend(file_handler.find_code_files(file_path, recursive=recursive))
            else:
                all_files.append(file_path)

        if not all_files:
            console.print("[yellow]No code files found to review[/yellow]")
            return

        console.print(f"\n[bold]Reviewing {len(all_files)} file(s)...[/bold]\n")

        all_output = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing...", total=len(all_files))

            for file_path in all_files:
                progress.update(task, description=f"Reviewing {file_path.name}...")

                result = analyzer.review_file(file_path, review_type=review_type)
                formatted = formatter.format_review(result)
                all_output.append(formatted)

                progress.advance(task)

        # Save or display output
        if output:
            combined = "\n\n---\n\n".join(all_output) if output_format != "json" else all_output
            if output_format == "json":
                import json
                combined = json.dumps([json.loads(o) for o in all_output], indent=2)
            output.write_text(combined)
            console.print(f"\n[green]Report saved to:[/green] {output}")
    except Exception as e:
        success = False
        collector.track_error(type(e).__name__, str(e)[:200], "review", "cli")
        raise
    finally:
        duration_ms = int((time.time() - start_time) * 1000)
        collector.track_command("review", duration_ms, success, "cli", {"files": len(files), "type": review_type})


@main.command()
@click.argument("description")
@click.option("--mode", "-m", default="generic",
              type=click.Choice(["function", "class", "script", "test", "generic"]))
@click.option("--language", "-l", default="python", help="Target language")
@click.option("--name", "-n", help="Name for function/class")
@click.option("--params", "-p", help="Parameters (for function mode)")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output file")
@click.option("--format", "-f", "output_format", default="console",
              type=click.Choice(["console", "markdown", "json"]))
@click.option("--source", "-s", type=click.Path(exists=True, path_type=Path),
              help="Source file (for test mode)")
@click.pass_context
def generate(ctx, description: str, mode: str, language: str, name: Optional[str],
             params: Optional[str], output: Optional[Path], output_format: str,
             source: Optional[Path]):
    """Generate code from natural language description."""
    import time
    from ai_code_assistant.analytics import get_collector

    collector = get_collector()
    start_time = time.time()
    success = True

    try:
        config, llm = get_components(ctx.obj.get("config_path"))
        generator = CodeGenerator(config, llm)
        formatter = get_formatter(output_format, config.output.use_colors)

        console.print(f"\n[bold]Generating {mode} in {language}...[/bold]\n")

        with console.status("[bold green]Generating code..."):
            if mode == "function":
                result = generator.generate_function(
                    description=description, name=name or "generated_function",
                    language=language, parameters=params or "",
                )
            elif mode == "class":
                result = generator.generate_class(
                    description=description, name=name or "GeneratedClass", language=language,
                )
            elif mode == "script":
                result = generator.generate_script(
                    description=description, requirements=[description], language=language,
                )
            elif mode == "test":
                if not source:
                    console.print("[red]Error:[/red] --source required for test mode")
                    sys.exit(1)
                source_code = source.read_text()
                result = generator.generate_tests(source_code=source_code, language=language)
            else:
                result = generator.generate(description=description, language=language)

        formatted = formatter.format_generation(result)

        if output and result.success:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(result.code)
            console.print(f"\n[green]Code saved to:[/green] {output}")
    except Exception as e:
        success = False
        collector.track_error(type(e).__name__, str(e)[:200], "generate", "cli")
        raise
    finally:
        duration_ms = int((time.time() - start_time) * 1000)
        collector.track_command("generate", duration_ms, success, "cli", {"mode": mode, "language": language})


@main.command()
@click.option("--context", "-c", multiple=True, type=click.Path(exists=True, path_type=Path),
              help="Files to load as context")
@click.option("--stream/--no-stream", default=True, help="Stream responses")
@click.pass_context
def chat(ctx, context: Tuple[Path, ...], stream: bool):
    """Start an interactive chat session about code."""
    config, llm = get_components(ctx.obj.get("config_path"))
    session = ChatSession(config, llm)

    # Load context files
    for file_path in context:
        if session.load_file_context(file_path):
            console.print(f"[dim]Loaded context: {file_path}[/dim]")
        else:
            console.print(f"[yellow]Warning: Could not load {file_path}[/yellow]")

    console.print(Panel(
        "[bold]AI Code Assistant Chat[/bold]\n\n"
        "Commands:\n"
        "  /load <file>  - Load a file as context\n"
        "  /clear        - Clear conversation history\n"
        "  /context      - Show loaded context files\n"
        "  /export       - Export conversation to markdown\n"
        "  /quit         - Exit chat\n",
        title="Interactive Mode",
    ))

    while True:
        try:
            user_input = console.input("\n[bold cyan]You>[/bold cyan] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input:
            continue

        # Handle commands
        if user_input.startswith("/"):
            cmd_parts = user_input[1:].split(maxsplit=1)
            cmd = cmd_parts[0].lower()
            arg = cmd_parts[1] if len(cmd_parts) > 1 else ""

            if cmd == "quit" or cmd == "exit":
                console.print("[dim]Goodbye![/dim]")
                break
            elif cmd == "clear":
                session.clear_history()
                console.print("[dim]History cleared[/dim]")
            elif cmd == "context":
                if session._code_context:
                    for name in session._code_context:
                        console.print(f"  • {name}")
                else:
                    console.print("[dim]No context files loaded[/dim]")
            elif cmd == "load" and arg:
                path = Path(arg)
                if session.load_file_context(path):
                    console.print(f"[green]Loaded: {path}[/green]")
                else:
                    console.print(f"[red]Could not load: {path}[/red]")
            elif cmd == "export":
                export_path = Path("chat_export.md")
                export_path.write_text(session.export_history())
                console.print(f"[green]Exported to: {export_path}[/green]")
            else:
                console.print(f"[yellow]Unknown command: {cmd}[/yellow]")
            continue

        # Send message
        console.print("\n[bold green]Assistant>[/bold green] ", end="")

        if stream:
            for chunk in session.send_message(user_input, stream=True):
                console.print(chunk, end="")
            console.print()
        else:
            response = session.send_message(user_input, stream=False)
            console.print(response)


@main.command()
@click.pass_context
def status(ctx):
    """Check Ollama connection and model status."""
    config, llm = get_components(ctx.obj.get("config_path"))

    console.print("\n[bold]AI Code Assistant Status[/bold]\n")

    # Model info
    info = llm.get_model_info()
    console.print(f"Model: [cyan]{info['model']}[/cyan]")
    console.print(f"Server: [cyan]{info['base_url']}[/cyan]")
    console.print(f"Temperature: {info['temperature']}")
    console.print(f"Max tokens: {info['max_tokens']}")

    # Connection check
    console.print("\n[bold]Connection Test:[/bold]")
    with console.status("[bold yellow]Testing connection to Ollama..."):
        if llm.check_connection():
            console.print("[green]✓ Ollama is accessible and model is loaded[/green]")
        else:
            console.print("[red]✗ Could not connect to Ollama[/red]")
            console.print("\nMake sure Ollama is running:")
            console.print("  1. Install Ollama: https://ollama.ai")
            console.print(f"  2. Pull the model: ollama pull {info['model']}")
            console.print("  3. Start Ollama: ollama serve")

    # Index status
    console.print("\n[bold]Codebase Index:[/bold]")
    try:
        from ai_code_assistant.retrieval import CodebaseSearch
        search = CodebaseSearch(root_path=str(Path.cwd()))
        count = search._collection.count()
        console.print(f"[green]✓ Index found with {count} chunks[/green]")
    except FileNotFoundError:
        console.print("[yellow]○ No index found. Run 'ai-assist index' to create one.[/yellow]")
    except Exception as e:
        console.print(f"[red]✗ Index error: {e}[/red]")


@main.command()
@click.argument("directory", default=".", type=click.Path(exists=True, path_type=Path))
@click.option("--clear", is_flag=True, help="Clear existing index before indexing")
@click.pass_context
def index(ctx, directory: Path, clear: bool):
    """Index codebase for semantic search.

    This creates a searchable index of your code that enables
    natural language queries to find relevant code.

    Example:
        ai-assist index .
        ai-assist index ./src --clear
    """
    from ai_code_assistant.retrieval import CodebaseIndexer
    from ai_code_assistant.retrieval.indexer import IndexConfig

    config = load_config(ctx.obj.get("config_path"))

    # Create indexer config from app config
    index_config = IndexConfig(
        embedding_model=config.retrieval.embedding_model,
        persist_directory=config.retrieval.persist_directory,
        collection_name=config.retrieval.collection_name,
    )

    console.print(f"\n[bold]Indexing codebase: {directory.absolute()}[/bold]\n")
    console.print(f"Embedding model: [cyan]{index_config.embedding_model}[/cyan]")
    console.print(f"Index location: [cyan]{index_config.persist_directory}[/cyan]\n")

    indexer = CodebaseIndexer(config=index_config, root_path=str(directory.absolute()))

    if clear:
        console.print("[yellow]Clearing existing index...[/yellow]")
        indexer.clear_index()

    console.print("[bold green]Starting indexing...[/bold green]\n")

    # First-time model download might take a while
    console.print("[dim]Note: First run downloads the embedding model (~90MB)[/dim]\n")

    stats = indexer.index_directory(verbose=True)

    console.print(f"\n[bold green]✓ Indexing complete![/bold green]")
    console.print(f"  Files indexed: {len(stats.indexed_files)}")
    console.print(f"  Total chunks: {stats.total_chunks}")
    if stats.skipped_files:
        console.print(f"  Files skipped: {len(stats.skipped_files)}")
    if stats.errors:
        console.print(f"  [yellow]Errors: {len(stats.errors)}[/yellow]")


@main.command()
@click.argument("query")
@click.option("--top-k", "-k", default=5, help="Number of results to return")
@click.option("--file", "-f", "file_filter", help="Filter by file path")
@click.option("--language", "-l", "lang_filter", help="Filter by language")
@click.option("--hybrid/--semantic", default=True,
              help="Use hybrid search (semantic + keyword). Use --semantic for vector-only search.")
@click.option("--alpha", default=0.5, type=float,
              help="Hybrid search balance: 1.0=semantic only, 0.0=keyword only, 0.5=balanced")
@click.option("--rerank/--no-rerank", default=False,
              help="Apply cross-encoder re-ranking for improved precision.")
@click.option("--format", "output_format", default="console",
              type=click.Choice(["console", "json", "context"]))
@click.pass_context
def search(ctx, query: str, top_k: int, file_filter: Optional[str],
           lang_filter: Optional[str], hybrid: bool, alpha: float,
           rerank: bool, output_format: str):
    """Search codebase using natural language.

    Find relevant code by describing what you're looking for.

    By default, uses hybrid search combining semantic (vector) and keyword (BM25) search
    for better exact match retrieval of function names, class names, and error codes.

    Use --rerank to apply cross-encoder re-ranking for improved precision (slower but
    more accurate ordering of results).

    Examples:
        ai-assist search "user authentication"
        ai-assist search "database connection" -k 10
        ai-assist search "error handling" --language python
        ai-assist search "processRequest" --alpha 0.3  # More weight on keyword match
        ai-assist search "config loading" --semantic   # Pure semantic search
        ai-assist search "config loading" --rerank     # Apply re-ranking
        ai-assist search "config loading" --format context
    """
    from ai_code_assistant.retrieval import CodebaseSearch
    from ai_code_assistant.retrieval.indexer import IndexConfig

    config = load_config(ctx.obj.get("config_path"))

    index_config = IndexConfig(
        embedding_model=config.retrieval.embedding_model,
        persist_directory=config.retrieval.persist_directory,
        collection_name=config.retrieval.collection_name,
    )

    try:
        searcher = CodebaseSearch(config=index_config, root_path=str(Path.cwd()))
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("\nRun [cyan]ai-assist index .[/cyan] first to create the index.")
        sys.exit(1)

    search_type = "hybrid" if hybrid else "semantic"
    if rerank:
        search_type += "+rerank"

    with console.status(f"[bold green]Searching ({search_type})..."):
        if hybrid:
            response = searcher.hybrid_search(
                query=query,
                top_k=top_k,
                alpha=alpha,
                file_filter=file_filter,
                language_filter=lang_filter,
                rerank=rerank,
                rerank_top_k=config.retrieval.rerank_top_k,
            )
        else:
            response = searcher.search(
                query=query,
                top_k=top_k,
                file_filter=file_filter,
                language_filter=lang_filter,
            )

    if output_format == "json":
        import json
        output = {
            "query": response.query,
            "total_results": response.total_results,
            "search_type": search_type,
            "alpha": alpha if hybrid else None,
            "rerank": rerank,
            "results": [r.to_dict() for r in response.results],
        }
        console.print(json.dumps(output, indent=2))

    elif output_format == "context":
        # Format for use as LLM context
        console.print(response.format_for_llm(max_results=top_k))

    else:  # console
        console.print(f"\n[bold]Search:[/bold] {query}")
        console.print(f"[bold]Mode:[/bold] {search_type}" + (f" (α={alpha})" if hybrid else ""))
        console.print(f"[bold]Results:[/bold] {response.total_results}\n")

        if not response.has_results:
            console.print("[yellow]No results found.[/yellow]")
            console.print("\nTips:")
            console.print("  • Try broader search terms")
            console.print("  • Check if the codebase is indexed: ai-assist status")
            return

        for i, result in enumerate(response.results, 1):
            console.print(f"[bold cyan]─── Result {i} ───[/bold cyan]")
            console.print(f"[bold]{result.file_path}[/bold]:{result.start_line}-{result.end_line}")
            # Show detailed scores for hybrid search
            if hybrid and (result.semantic_score > 0 or result.keyword_score > 0):
                console.print(f"[dim]Type: {result.chunk_type} | Name: {result.name}[/dim]")
                console.print(f"[dim]Score: {result.score:.3f} (semantic: {result.semantic_score:.3f}, keyword: {result.keyword_score:.3f})[/dim]")
            else:
                console.print(f"[dim]Type: {result.chunk_type} | Name: {result.name} | Score: {result.score:.3f}[/dim]")
            console.print()

            # Show code with syntax highlighting
            from rich.syntax import Syntax
            syntax = Syntax(
                result.content,
                result.language or "text",
                line_numbers=True,
                start_line=result.start_line,
                theme="monokai",
            )
            console.print(syntax)
            console.print()


@main.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.argument("instruction")
@click.option("--mode", "-m", default="edit",
              type=click.Choice(["edit", "refactor", "fix", "add"]),
              help="Edit mode")
@click.option("--preview", "-p", is_flag=True, help="Preview changes without applying")
@click.option("--no-backup", is_flag=True, help="Don't create backup file")
@click.option("--format", "-f", "output_format", default="console",
              type=click.Choice(["console", "json"]), help="Output format")
@click.option("--start-line", "-s", type=int, help="Start line for targeted edit")
@click.option("--end-line", "-e", type=int, help="End line for targeted edit")
@click.pass_context
def edit(ctx, file: Path, instruction: str, mode: str, preview: bool,
         no_backup: bool, output_format: str, start_line: Optional[int],
         end_line: Optional[int]):
    """Edit a file using AI based on natural language instructions.

    Examples:
        ai-assist edit main.py "Add error handling to the parse function"
        ai-assist edit utils.py "Add type hints" --mode refactor
        ai-assist edit app.py "Fix the null pointer bug" --mode fix
        ai-assist edit api.py "Add logging" --preview
        ai-assist edit config.py "Update the timeout value" -s 10 -e 20
    """
    config, llm = get_components(ctx.obj.get("config_path"))
    editor = FileEditor(config, llm)

    # Determine edit mode
    edit_mode = mode
    if start_line and end_line:
        edit_mode = "targeted"

    console.print(f"\n[bold]Editing {file}...[/bold]")
    console.print(f"Mode: [cyan]{edit_mode}[/cyan]")
    console.print(f"Instruction: [dim]{instruction}[/dim]\n")

    with console.status("[bold green]Generating edit..."):
        result = editor.edit_file(
            file_path=file,
            instruction=instruction,
            mode=edit_mode,
            preview=preview,
            create_backup=not no_backup,
            start_line=start_line,
            end_line=end_line,
        )

    if output_format == "json":
        import json
        console.print(json.dumps(result.to_dict(), indent=2))
        return

    # Console output
    if not result.success:
        console.print(f"[red]Error:[/red] {result.error}")
        sys.exit(1)

    if not result.has_changes:
        console.print("[yellow]No changes detected.[/yellow]")
        return

    # Show diff
    if result.diff:
        console.print("[bold]Changes:[/bold]")
        console.print(f"  [green]+{result.diff.additions}[/green] additions, "
                      f"[red]-{result.diff.deletions}[/red] deletions\n")

        from rich.syntax import Syntax
        diff_text = result.diff.unified_diff
        syntax = Syntax(diff_text, "diff", theme="monokai")
        console.print(syntax)

    if preview:
        console.print("\n[yellow]Preview mode - changes not applied[/yellow]")
        console.print("Run without --preview to apply changes.")
    else:
        if result.applied:
            console.print(f"\n[green]✓ Changes applied to {file}[/green]")
            if result.backup_path:
                console.print(f"[dim]Backup saved: {result.backup_path}[/dim]")
        else:
            console.print(f"\n[red]✗ Failed to apply changes[/red]")


@main.command()
@click.argument("instruction")
@click.option("--files", "-f", multiple=True, type=click.Path(exists=True, path_type=Path),
              help="Specific files to include")
@click.option("--pattern", "-p", help="Glob pattern to match files (e.g., '**/*.py')")
@click.option("--directory", "-d", type=click.Path(exists=True, path_type=Path),
              default=".", help="Directory to search for files")
@click.option("--dry-run", is_flag=True, help="Show plan without applying changes")
@click.option("--no-confirm", is_flag=True, help="Skip confirmation prompt")
@click.option("--no-backup", is_flag=True, help="Don't create backup")
@click.option("--format", "output_format", default="console",
              type=click.Choice(["console", "json"]), help="Output format")
@click.pass_context
def refactor(ctx, instruction: str, files: Tuple[Path, ...], pattern: Optional[str],
             directory: Path, dry_run: bool, no_confirm: bool, no_backup: bool,
             output_format: str):
    """Perform multi-file refactoring using AI.

    Analyzes the codebase and applies coordinated changes across multiple files.

    Examples:
        ai-assist refactor "Add type hints to all functions"
        ai-assist refactor "Rename User class to Account" -p "**/*.py"
        ai-assist refactor "Extract database logic to repository pattern" --dry-run
        ai-assist refactor "Add logging to all API endpoints" -d ./src/api
    """
    from ai_code_assistant.refactor import MultiFileEditor
    from ai_code_assistant.utils import FileHandler

    config, llm = get_components(ctx.obj.get("config_path"))
    editor = MultiFileEditor(config, llm)
    file_handler = FileHandler(config)

    # Collect files to refactor
    all_files: List[Path] = list(files)

    if pattern:
        # Use glob pattern
        all_files.extend(directory.glob(pattern))
    elif not files:
        # Default: find all code files in directory
        all_files.extend(file_handler.find_code_files(directory, recursive=True))

    # Remove duplicates and limit
    all_files = list(set(all_files))[:config.refactor.max_files]

    if not all_files:
        console.print("[red]Error:[/red] No files found to refactor")
        sys.exit(1)

    console.print(f"\n[bold]Multi-File Refactoring[/bold]")
    console.print(f"Instruction: [cyan]{instruction}[/cyan]")
    console.print(f"Files in scope: [cyan]{len(all_files)}[/cyan]\n")

    # Show files
    if ctx.obj.get("verbose"):
        for f in all_files[:10]:
            console.print(f"  • {f}")
        if len(all_files) > 10:
            console.print(f"  ... and {len(all_files) - 10} more")
        console.print()

    # Analyze and create plan
    with console.status("[bold green]Analyzing codebase..."):
        result = editor.refactor(
            instruction=instruction,
            files=all_files,
            dry_run=True,  # Always start with dry run to show plan
            create_backup=not no_backup,
        )

    if result.error and not result.plan.changes:
        console.print(f"[red]Error:[/red] {result.error}")
        sys.exit(1)

    # Output as JSON if requested
    if output_format == "json":
        import json
        console.print(json.dumps(result.to_dict(), indent=2))
        return

    # Show plan
    plan = result.plan
    console.print(f"[bold]Refactoring Plan[/bold]")
    console.print(f"Summary: {plan.summary}")
    console.print(f"Complexity: [cyan]{plan.complexity}[/cyan]")
    console.print(f"Files affected: [cyan]{plan.total_files}[/cyan]\n")

    if plan.risks:
        console.print("[yellow]Risks:[/yellow]")
        for risk in plan.risks:
            console.print(f"  ⚠ {risk}")
        console.print()

    # Show changes
    console.print("[bold]Planned Changes:[/bold]")
    for change in plan.changes:
        icon = {"modify": "📝", "create": "✨", "delete": "🗑️", "rename": "📛"}.get(
            change.change_type.value, "•"
        )
        console.print(f"  {icon} [{change.change_type.value}] {change.file_path}")
        console.print(f"     {change.description}")

    if dry_run:
        console.print("\n[yellow]Dry run - no changes applied[/yellow]")
        return

    # Confirm before applying
    if not no_confirm and config.refactor.require_confirmation:
        console.print()
        if not click.confirm("Apply these changes?"):
            console.print("[dim]Cancelled[/dim]")
            return

    # Apply changes
    console.print("\n[bold green]Applying changes...[/bold green]")

    with console.status("[bold green]Generating and applying changes..."):
        result = editor.refactor(
            instruction=instruction,
            files=all_files,
            dry_run=False,
            create_backup=not no_backup,
        )

    if result.error:
        console.print(f"[red]Error:[/red] {result.error}")
        sys.exit(1)

    # Show results
    console.print(f"\n[bold green]✓ Refactoring complete![/bold green]")
    console.print(f"  Files changed: {result.files_changed}")
    console.print(f"  Additions: [green]+{result.total_additions}[/green]")
    console.print(f"  Deletions: [red]-{result.total_deletions}[/red]")

    if result.backup_dir:
        console.print(f"\n[dim]Backup saved: {result.backup_dir}[/dim]")

    if result.files_failed > 0:
        console.print(f"\n[yellow]Warning: {result.files_failed} file(s) failed[/yellow]")
        for change in result.plan.changes:
            if change.error:
                console.print(f"  • {change.file_path}: {change.error}")


@main.command()
@click.argument("old_name")
@click.argument("new_name")
@click.option("--type", "-t", "symbol_type", default="symbol",
              type=click.Choice(["function", "class", "variable", "method", "symbol"]),
              help="Type of symbol to rename")
@click.option("--files", "-f", multiple=True, type=click.Path(exists=True, path_type=Path),
              help="Specific files to include")
@click.option("--pattern", "-p", help="Glob pattern to match files")
@click.option("--directory", "-d", type=click.Path(exists=True, path_type=Path),
              default=".", help="Directory to search")
@click.option("--dry-run", is_flag=True, help="Show changes without applying")
@click.pass_context
def rename(ctx, old_name: str, new_name: str, symbol_type: str, files: Tuple[Path, ...],
           pattern: Optional[str], directory: Path, dry_run: bool):
    """Rename a symbol across multiple files.

    Examples:
        ai-assist rename UserService AccountService --type class
        ai-assist rename get_user fetch_user --type function -p "**/*.py"
        ai-assist rename API_KEY API_SECRET --type variable --dry-run
    """
    from ai_code_assistant.refactor import MultiFileEditor
    from ai_code_assistant.utils import FileHandler

    config, llm = get_components(ctx.obj.get("config_path"))
    editor = MultiFileEditor(config, llm)
    file_handler = FileHandler(config)

    # Collect files
    all_files: List[Path] = list(files)
    if pattern:
        all_files.extend(directory.glob(pattern))
    elif not files:
        all_files.extend(file_handler.find_code_files(directory, recursive=True))

    all_files = list(set(all_files))[:config.refactor.max_files]

    if not all_files:
        console.print("[red]Error:[/red] No files found")
        sys.exit(1)

    console.print(f"\n[bold]Rename Symbol[/bold]")
    console.print(f"Renaming {symbol_type}: [cyan]{old_name}[/cyan] → [green]{new_name}[/green]")
    console.print(f"Files to search: [cyan]{len(all_files)}[/cyan]\n")

    with console.status("[bold green]Searching and renaming..."):
        result = editor.rename_symbol(
            old_name=old_name,
            new_name=new_name,
            symbol_type=symbol_type,
            files=all_files,
            dry_run=dry_run,
        )

    if result.error:
        console.print(f"[red]Error:[/red] {result.error}")
        sys.exit(1)

    # Show results
    console.print(f"[bold]Files affected: {result.plan.total_files}[/bold]\n")

    for change in result.plan.changes:
        status = "[green]✓[/green]" if change.applied else "[yellow]○[/yellow]"
        console.print(f"  {status} {change.file_path}")

    if dry_run:
        console.print("\n[yellow]Dry run - no changes applied[/yellow]")
    else:
        console.print(f"\n[green]✓ Renamed {old_name} to {new_name} in {result.files_changed} file(s)[/green]")


@main.command("smart-chat")
@click.argument("message")
@click.option("--context", "-c", help="Code context to include")
@click.option("--file", "-f", "context_file", type=click.Path(exists=True, path_type=Path),
              help="File to use as context")
@click.option("--language", "-l", default="python", help="Language for code generation")
@click.option("--history", "-h", "history_json", help="JSON conversation history")
@click.option("--system-prompt", "-s", "system_prompt", help="Custom system prompt for the AI agent")
@click.option("--provider", "-p", help="LLM provider (ollama, openai, google, groq)")
@click.option("--model", "-m", help="Model name to use (e.g., gpt-4, gemini-1.5-flash, llama3)")
@click.pass_context
def smart_chat(ctx, message: str, context: Optional[str], context_file: Optional[Path],
               language: str, history_json: Optional[str], system_prompt: Optional[str],
               provider: Optional[str], model: Optional[str]):
    """Intelligent chat that detects intent and executes appropriate actions.

    Automatically detects if the user wants to:
    - Generate code: "create a function to...", "write code that..."
    - Review code: "review this", "check for bugs", "is there anything wrong"
    - Edit code: "add error handling", "make this async", "refactor this"
    - Explain code: "what does this do", "explain this", "how does this work"
    - General chat: Any other programming questions

    Examples:
        cognify smart-chat "write a binary search function"
        cognify smart-chat "review this code" -c "def foo(): pass"
        cognify smart-chat "what's the difference between let and const"
        cognify smart-chat "explain recursion" --provider google --model gemini-1.5-flash
    """
    import json
    import re
    import time

    # Import analytics and licensing modules
    from ai_code_assistant.analytics import get_collector
    from ai_code_assistant.licensing import get_license_manager

    collector = get_collector()
    license_mgr = get_license_manager()

    # Check license/usage limits for cloud providers
    effective_provider = provider or "ollama"
    if effective_provider != "ollama":
        usage_check = license_mgr.check_usage_limit(effective_provider)
        if not usage_check["allowed"]:
            console.print(f"[yellow]⚠ {usage_check['message']}[/yellow]")
            console.print("[dim]Tip: Use Ollama for unlimited local LLM calls, or upgrade your plan.[/dim]")
            sys.exit(1)

    start_time = time.time()
    success = True

    config, llm = get_components(ctx.obj.get("config_path"), provider=provider, model=model)

    # Get effective model name for tracking
    effective_model = model or (config.llm.model if hasattr(config.llm, 'model') else "unknown")

    # Load context from file if provided
    if context_file and not context:
        try:
            context = context_file.read_text()
            language = get_language_by_extension(context_file.suffix) or language
        except Exception as e:
            console.print(f"[yellow]Warning: Could not read context file: {e}[/yellow]")

    # Parse conversation history if provided
    history = []
    if history_json:
        try:
            history = json.loads(history_json)
        except json.JSONDecodeError:
            pass

    # Search knowledge base for relevant context
    knowledge_context = ""
    try:
        from ai_code_assistant.knowledge import KnowledgeManager
        knowledge_mgr = KnowledgeManager()
        knowledge_context = knowledge_mgr.get_context_for_query(message, max_entries=3)
        if knowledge_context:
            collector.track_feature("knowledge_base", client="cli")
    except Exception:
        pass  # Knowledge base is optional enhancement

    # Combine knowledge context with user-provided context
    combined_context = context or ""
    if knowledge_context:
        if combined_context:
            combined_context = f"{knowledge_context}\n\n=== User Provided Context ===\n{combined_context}"
        else:
            combined_context = knowledge_context

    # Detect intent from message
    intent = _detect_intent(message, context)

    try:
        llm_start = time.time()

        if intent == "generate":
            result = _handle_generate(config, llm, message, language, system_prompt)
        elif intent == "review" and context:
            result = _handle_review(config, llm, context, language, system_prompt)
        elif intent == "edit" and context:
            result = _handle_edit(config, llm, message, context, language, system_prompt)
        elif intent == "explain" and context:
            result = _handle_explain(config, llm, context, language, system_prompt)
        else:
            # General chat - pass combined context with knowledge
            result = _handle_chat(config, llm, message, combined_context if combined_context else None, history, system_prompt)

        llm_latency = int((time.time() - llm_start) * 1000)

        # Track LLM call (we don't have exact token counts without parsing the response)
        collector.track_llm_call(
            provider=effective_provider,
            model=effective_model,
            latency_ms=llm_latency,
            client="cli",
        )

        # Output result (no formatting for VSCode extension consumption)
        print(result)

    except Exception as e:
        success = False
        collector.track_error(
            error_type=type(e).__name__,
            error_message=str(e)[:200],
            command="smart-chat",
            client="cli",
        )
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    finally:
        # Track command execution
        duration_ms = int((time.time() - start_time) * 1000)
        collector.track_command(
            command="smart-chat",
            duration_ms=duration_ms,
            success=success,
            client="cli",
            metadata={"intent": intent, "provider": effective_provider},
        )


def _detect_intent(message: str, context: Optional[str]) -> str:
    """Detect user intent from the message."""
    message_lower = message.lower().strip()

    # Generate patterns
    generate_patterns = [
        r'\b(create|write|generate|make|build|implement|code)\b.*\b(function|class|method|script|code|program)\b',
        r'^(create|write|generate|make|build|implement)\b',
        r'\bcan you (create|write|generate|make|build|implement)\b',
        r'\b(write|create) (me |a |an |the )?',
    ]

    # Review patterns
    review_patterns = [
        r'\b(review|check|analyze|audit|inspect|look at|examine)\b.*\b(code|this|it)\b',
        r'\b(is there|are there|any)\b.*\b(bug|issue|problem|error|wrong)\b',
        r'\b(what\'?s wrong|find (the )?bug|spot (the )?issue)\b',
        r'^review\b',
    ]

    # Edit patterns
    edit_patterns = [
        r'\b(add|remove|change|modify|update|fix|refactor|improve|optimize)\b.*\b(to |in |the |this)\b',
        r'\b(make|convert) (this|it) ',
        r'\b(add|include) (error handling|logging|type hints|comments|documentation)\b',
    ]

    # Explain patterns
    explain_patterns = [
        r'\b(explain|what does|how does|what is|describe|tell me about)\b.*\b(this|it|code|do|work)\b',
        r'^(explain|what|how)\b.*\?$',
        r'\bwhat\'?s (this|happening|going on)\b',
    ]

    # Check patterns in order of specificity
    for pattern in generate_patterns:
        if re.search(pattern, message_lower):
            return "generate"

    for pattern in review_patterns:
        if re.search(pattern, message_lower):
            if context:  # Only review if we have context
                return "review"

    for pattern in edit_patterns:
        if re.search(pattern, message_lower):
            if context:  # Only edit if we have context
                return "edit"

    for pattern in explain_patterns:
        if re.search(pattern, message_lower):
            if context:  # Only explain if we have context
                return "explain"

    return "chat"


def _handle_generate(config: Config, llm: LLMManager, message: str, language: str, system_prompt: Optional[str] = None) -> str:
    """Handle code generation request."""
    # If custom system prompt is provided, use it directly via chat
    if system_prompt:
        return _handle_chat(config, llm, f"Generate code: {message} (in {language})", None, [], system_prompt)

    generator = CodeGenerator(config, llm)
    result = generator.generate(
        description=message,
        language=language,
    )

    # Format response with code block
    if result.success:
        response = f"Here's the generated code:\n\n```{language}\n{result.code}\n```"
        if result.raw_response and result.raw_response != result.code:
            # Extract any explanation from the raw response
            pass
    else:
        response = f"Error generating code: {result.error}"
    return response


def _handle_review(config: Config, llm: LLMManager, code: str, language: str, system_prompt: Optional[str] = None) -> str:
    """Handle code review request."""
    # If custom system prompt is provided, use it directly via chat
    if system_prompt:
        return _handle_chat(config, llm, f"Review this {language} code:\n```{language}\n{code}\n```", None, [], system_prompt)

    analyzer = CodeAnalyzer(config, llm)
    result = analyzer.review_code(code, language=language)

    # Check for errors
    if result.error:
        return f"Error during code review: {result.error}"

    # Format response
    response = f"**Code Review Summary:**\n{result.summary}\n\n"

    if result.issues:
        response += "**Issues Found:**\n"
        for issue in result.issues:
            severity_icon = {"critical": "🔴", "warning": "🟡", "suggestion": "💡"}.get(issue.severity, "ℹ️")
            response += f"\n{severity_icon} **{issue.severity.upper()}**"
            if issue.line_start:
                if issue.line_start == issue.line_end:
                    response += f" (Line {issue.line_start})"
                else:
                    response += f" (Lines {issue.line_start}-{issue.line_end})"
            response += f": {issue.title}"
            if issue.description:
                response += f"\n   {issue.description}"
            if issue.suggestion:
                response += f"\n   💡 Suggestion: {issue.suggestion}"
    else:
        response += "✅ No issues found! The code looks good."

    return response


def _handle_edit(config: Config, llm: LLMManager, instruction: str, code: str, language: str, custom_system_prompt: Optional[str] = None) -> str:
    """Handle code edit request."""
    from langchain_core.messages import HumanMessage, SystemMessage

    # Use custom system prompt if provided, otherwise use default
    if custom_system_prompt:
        system_prompt = custom_system_prompt
    else:
        system_prompt = """You are an expert code editor. Given code and an instruction, modify the code accordingly.

Rules:
- Return ONLY the modified code in a code block
- Preserve the original structure where possible
- Add comments explaining significant changes
- Ensure the code is syntactically correct"""

    user_prompt = f"""**Original Code:**
```{language}
{code}
```

**Instruction:** {instruction}

Please provide the modified code:"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]

    response = llm.llm.invoke(messages)
    result = str(response.content)

    return f"Here's the modified code:\n\n{result}"


def _handle_explain(config: Config, llm: LLMManager, code: str, language: str, custom_system_prompt: Optional[str] = None) -> str:
    """Handle code explanation request."""
    from langchain_core.messages import HumanMessage, SystemMessage

    # Use custom system prompt if provided, otherwise use default
    if custom_system_prompt:
        system_prompt = custom_system_prompt
    else:
        system_prompt = """You are an expert programming teacher. Explain code clearly and concisely.

When explaining code:
- Start with a brief overview of what the code does
- Explain key components and their purpose
- Highlight any important patterns or techniques used
- Mention potential improvements if relevant
- Use simple language that beginners can understand"""

    user_prompt = f"""Please explain this code:

```{language}
{code}
```"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]

    response = llm.llm.invoke(messages)
    return str(response.content)


def _handle_chat(config: Config, llm: LLMManager, message: str, context: Optional[str],
                 history: List[dict], custom_system_prompt: Optional[str] = None) -> str:
    """Handle general chat request."""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    # Use custom system prompt if provided (for different AI agents)
    if custom_system_prompt:
        system_prompt = custom_system_prompt
    else:
        system_prompt = """You are Cognify AI, an expert programming assistant. You help developers with:
- Answering programming questions
- Explaining concepts and best practices
- Debugging help and suggestions
- Code architecture discussions
- Technology recommendations

Be helpful, concise, and provide code examples when relevant. Use markdown formatting."""

    messages = [SystemMessage(content=system_prompt)]

    # Add code context if provided
    if context:
        messages.append(SystemMessage(content=f"**Code Context:**\n```\n{context}\n```"))

    # Add conversation history
    for msg in history:
        if msg.get("role") == "user":
            messages.append(HumanMessage(content=msg.get("content", "")))
        elif msg.get("role") == "assistant":
            messages.append(AIMessage(content=msg.get("content", "")))

    # Add current message
    messages.append(HumanMessage(content=message))

    response = llm.llm.invoke(messages)
    return str(response.content)


# ==================== Knowledge Base Commands ====================

@main.group()
@click.pass_context
def knowledge(ctx):
    """Manage the knowledge base for persistent learning."""
    pass


@knowledge.command("save")
@click.argument("title")
@click.option("--content", "-c", help="Knowledge content (or use stdin)")
@click.option("--content-file", "-f", type=click.Path(exists=True), help="Read content from file")
@click.option("--tags", "-t", multiple=True, help="Tags for this entry")
@click.option("--category", default="general", help="Category (e.g., patterns, architecture, decisions)")
@click.option("--source", default="user", help="Source of knowledge (user, ai, code)")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
@click.pass_context
def knowledge_save(ctx, title: str, content: Optional[str], content_file: Optional[str],
                   tags: tuple, category: str, source: str, output_format: str):
    """Save a new knowledge entry to the knowledge base."""
    from ai_code_assistant.knowledge import KnowledgeManager

    # Get content from various sources
    if content_file:
        content = Path(content_file).read_text()
    elif not content:
        # Read from stdin if no content provided
        content = click.get_text_stream('stdin').read().strip()

    if not content:
        click.echo("Error: No content provided. Use --content, --content-file, or pipe content.", err=True)
        ctx.exit(1)

    manager = KnowledgeManager()
    entry = manager.save(
        title=title,
        content=content,
        tags=list(tags),
        category=category,
        source=source
    )

    if output_format == "json":
        click.echo(json.dumps(entry.to_dict(), indent=2))
    else:
        click.echo(f"✅ Knowledge saved!")
        click.echo(f"   ID: {entry.id}")
        click.echo(f"   Title: {entry.title}")
        click.echo(f"   Category: {entry.category}")
        click.echo(f"   Tags: {', '.join(entry.tags) if entry.tags else 'none'}")
        click.echo(f"   File: {entry.file_path}")


@knowledge.command("search")
@click.argument("query")
@click.option("--tags", "-t", multiple=True, help="Filter by tags")
@click.option("--category", "-c", help="Filter by category")
@click.option("--limit", "-l", default=5, help="Maximum results to return")
@click.option("--format", "output_format", type=click.Choice(["text", "json", "context"]), default="text")
@click.pass_context
def knowledge_search(ctx, query: str, tags: tuple, category: Optional[str],
                     limit: int, output_format: str):
    """Search the knowledge base."""
    from ai_code_assistant.knowledge import KnowledgeManager

    manager = KnowledgeManager()
    results = manager.search(query, tags=list(tags) if tags else None,
                            category=category, limit=limit)

    if not results:
        click.echo("No matching knowledge found.")
        return

    if output_format == "json":
        click.echo(json.dumps([e.to_dict() for e in results], indent=2))
    elif output_format == "context":
        # Format for LLM context
        click.echo(manager.get_context_for_query(query, max_entries=limit))
    else:
        click.echo(f"Found {len(results)} matching entries:\n")
        for entry in results:
            click.echo(f"📚 {entry.title}")
            click.echo(f"   ID: {entry.id}")
            click.echo(f"   Category: {entry.category} | Tags: {', '.join(entry.tags) if entry.tags else 'none'}")
            click.echo(f"   Updated: {entry.updated_at}")
            # Show first 100 chars of content
            preview = entry.content[:100].replace('\n', ' ')
            if len(entry.content) > 100:
                preview += "..."
            click.echo(f"   Preview: {preview}")
            click.echo()


@knowledge.command("list")
@click.option("--category", "-c", help="Filter by category")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
@click.pass_context
def knowledge_list(ctx, category: Optional[str], output_format: str):
    """List all knowledge entries."""
    from ai_code_assistant.knowledge import KnowledgeManager

    manager = KnowledgeManager()
    entries = manager.list_all(category)

    if not entries:
        click.echo("No knowledge entries found.")
        return

    if output_format == "json":
        click.echo(json.dumps([e.to_dict() for e in entries], indent=2))
    else:
        click.echo(f"Found {len(entries)} entries:\n")
        for entry in entries:
            click.echo(f"📚 {entry.title}")
            click.echo(f"   ID: {entry.id} | Category: {entry.category}")
            click.echo()


@knowledge.command("delete")
@click.argument("entry_id")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.pass_context
def knowledge_delete(ctx, entry_id: str, yes: bool):
    """Delete a knowledge entry by ID."""
    from ai_code_assistant.knowledge import KnowledgeManager

    manager = KnowledgeManager()
    entry = manager.get(entry_id)

    if not entry:
        click.echo(f"Error: Entry with ID '{entry_id}' not found.", err=True)
        ctx.exit(1)

    if not yes:
        click.confirm(f"Delete '{entry.title}'?", abort=True)

    if manager.delete(entry_id):
        click.echo(f"✅ Deleted: {entry.title}")
    else:
        click.echo("Error: Failed to delete entry.", err=True)
        ctx.exit(1)


@knowledge.command("stats")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
@click.pass_context
def knowledge_stats(ctx, output_format: str):
    """Show knowledge base statistics."""
    from ai_code_assistant.knowledge import KnowledgeManager

    manager = KnowledgeManager()
    stats = manager.get_stats()

    if output_format == "json":
        click.echo(json.dumps(stats, indent=2))
    else:
        click.echo("📊 Knowledge Base Statistics\n")
        click.echo(f"   Total Entries: {stats['total_entries']}")
        click.echo(f"   Directory: {stats['knowledge_dir']}")
        click.echo()

        if stats['categories']:
            click.echo("   Categories:")
            for cat, count in sorted(stats['categories'].items()):
                click.echo(f"      - {cat}: {count}")

        if stats['tags']:
            click.echo("\n   Tags:")
            for tag, count in sorted(stats['tags'].items(), key=lambda x: -x[1])[:10]:
                click.echo(f"      - {tag}: {count}")


# ==================== Settings Commands ====================

@main.group()
@click.pass_context
def settings(ctx):
    """Manage Cognify AI settings and preferences."""
    pass


@settings.command("show")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
@click.pass_context
def settings_show(ctx, output_format: str):
    """Show current settings."""
    from ai_code_assistant.settings import get_settings_manager

    manager = get_settings_manager()
    all_settings = manager.get_all_settings()

    if output_format == "json":
        click.echo(json.dumps(all_settings, indent=2))
    else:
        click.echo("⚙️  Cognify AI Settings\n")
        click.echo(f"   Config file: {manager.config_path}")
        click.echo(f"   Device ID: {manager.device_id[:8]}...\n")

        def print_settings(settings_dict, indent=0):
            for key, value in settings_dict.items():
                prefix = "   " * (indent + 1)
                if isinstance(value, dict):
                    click.echo(f"{prefix}[{key}]")
                    print_settings(value, indent + 1)
                else:
                    status = "✓" if value is True else ("✗" if value is False else "")
                    click.echo(f"{prefix}{key}: {value} {status}")

        print_settings(all_settings)


@settings.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def settings_set(ctx, key: str, value: str):
    """Set a configuration value (use dot notation, e.g., telemetry.enabled)."""
    from ai_code_assistant.settings import get_settings_manager

    manager = get_settings_manager()

    # Convert string value to appropriate type
    if value.lower() == "true":
        typed_value = True
    elif value.lower() == "false":
        typed_value = False
    elif value.isdigit():
        typed_value = int(value)
    else:
        try:
            typed_value = float(value)
        except ValueError:
            typed_value = value

    old_value = manager.get(key)
    manager.set(key, typed_value)

    click.echo(f"✅ Updated {key}")
    click.echo(f"   Old: {old_value}")
    click.echo(f"   New: {typed_value}")


@settings.command("privacy")
@click.option("--telemetry/--no-telemetry", default=None, help="Enable/disable telemetry")
@click.option("--analytics/--no-analytics", default=None, help="Enable/disable local analytics")
@click.option("--show", is_flag=True, help="Show current privacy settings")
@click.pass_context
def settings_privacy(ctx, telemetry, analytics, show):
    """Configure privacy and telemetry settings."""
    from ai_code_assistant.settings import PrivacySettings

    privacy = PrivacySettings()

    if show or (telemetry is None and analytics is None):
        consent = privacy.get_consent_status()
        click.echo("🔒 Privacy Settings\n")
        for key, value in consent.items():
            status = "✓ Enabled" if value else "✗ Disabled"
            click.echo(f"   {key}: {status}")
        click.echo("\nUse --telemetry/--no-telemetry or --analytics/--no-analytics to change.")
        return

    privacy.update_consent(
        telemetry_enabled=telemetry,
        analytics_enabled=analytics,
    )

    click.echo("✅ Privacy settings updated")
    if telemetry is not None:
        click.echo(f"   Telemetry: {'Enabled' if telemetry else 'Disabled'}")
    if analytics is not None:
        click.echo(f"   Analytics: {'Enabled' if analytics else 'Disabled'}")


# ==================== Data Commands ====================

@main.group()
@click.pass_context
def data(ctx):
    """Manage your usage data and analytics."""
    pass


@data.command("show")
@click.option("--days", "-d", default=7, help="Number of days to show")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
@click.pass_context
def data_show(ctx, days: int, output_format: str):
    """Show usage analytics summary."""
    from ai_code_assistant.analytics import get_collector
    from ai_code_assistant.settings import PrivacySettings

    collector = get_collector()
    privacy = PrivacySettings()

    summary = collector.get_summary()
    daily_stats = collector.get_daily_stats(days)
    data_summary = privacy.get_data_summary()

    if output_format == "json":
        click.echo(json.dumps({
            "summary": summary,
            "daily_stats": daily_stats,
            "data_info": data_summary,
        }, indent=2))
    else:
        if not summary.get("analytics_enabled", True):
            click.echo("📊 Analytics is disabled. Enable with: cognify settings set analytics.enabled true")
            return

        click.echo("📊 Usage Analytics\n")
        click.echo(f"   Total events: {summary.get('total_events', 0)}")

        if summary.get('date_range'):
            dr = summary['date_range']
            click.echo(f"   Data range: {dr.get('from', 'N/A')} to {dr.get('to', 'N/A')}")

        if summary.get('top_commands'):
            click.echo("\n   Top commands:")
            for cmd in summary['top_commands'][:5]:
                click.echo(f"      - {cmd['event_name']}: {cmd['count']} times")

        if daily_stats:
            click.echo(f"\n   Last {days} days:")
            for day in daily_stats[:7]:
                click.echo(f"      {day.get('date', 'N/A')}: {day.get('total_events', 0)} events")


@data.command("export")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.pass_context
def data_export(ctx, output: str):
    """Export all your data to JSON (GDPR data portability)."""
    from ai_code_assistant.settings import PrivacySettings

    privacy = PrivacySettings()
    output_path = Path(output) if output else None

    export_file = privacy.export_user_data(output_path)
    click.echo(f"✅ Data exported to: {export_file}")
    click.echo("   This file contains all your Cognify AI data including settings and analytics.")


@data.command("delete")
@click.option("--confirm", is_flag=True, help="Confirm deletion")
@click.pass_context
def data_delete(ctx, confirm: bool):
    """Delete all your local data (GDPR right to be forgotten)."""
    from ai_code_assistant.settings import PrivacySettings

    privacy = PrivacySettings()

    if not confirm:
        summary = privacy.get_data_summary()
        click.echo("⚠️  This will delete ALL your Cognify AI data:")
        click.echo(f"   - Analytics database ({summary.get('total_events', 0)} events)")
        click.echo("   - Cached credentials")
        click.echo("   - License information")
        click.echo("   - Device ID (will be regenerated)")
        click.echo("\nSettings will be reset to defaults.\n")
        click.echo("Run with --confirm to proceed:")
        click.echo("   cognify data delete --confirm")
        return

    if privacy.delete_all_data(confirm=True):
        click.echo("✅ All data deleted successfully")
        click.echo("   Your settings have been reset to defaults.")
    else:
        click.echo("❌ Failed to delete data", err=True)


# ==================== Auth Commands ====================

@main.group()
@click.pass_context
def auth(ctx):
    """Manage authentication (optional)."""
    pass


@auth.command("status")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
@click.pass_context
def auth_status(ctx, output_format: str):
    """Show authentication status."""
    from ai_code_assistant.auth import get_auth_manager

    manager = get_auth_manager()
    status = manager.get_auth_status()

    if output_format == "json":
        click.echo(json.dumps(status, indent=2))
    else:
        click.echo("🔐 Authentication Status\n")
        click.echo(f"   Auth enabled: {'Yes' if status['auth_enabled'] else 'No'}")
        click.echo(f"   Authenticated: {'Yes' if status['is_authenticated'] else 'No'}")
        click.echo(f"   Device ID: {status['device_id'][:8]}...")

        if status.get('user'):
            user = status['user']
            click.echo(f"\n   User: {user.get('name', 'N/A')}")
            click.echo(f"   Email: {user.get('email', 'N/A')}")
        elif status.get('message'):
            click.echo(f"\n   {status['message']}")


@auth.command("login")
@click.option("--api-key", "-k", help="API key for authentication")
@click.option("--provider", "-p", type=click.Choice(["github", "google"]), default="github",
              help="OAuth provider (future feature)")
@click.pass_context
def auth_login(ctx, api_key: str, provider: str):
    """Login to Cognify AI (optional for cloud features)."""
    from ai_code_assistant.auth import get_auth_manager

    manager = get_auth_manager()

    if api_key:
        result = manager.login_with_api_key(api_key)
    else:
        result = manager.login_oauth(provider)

    if result['success']:
        click.echo(f"✅ {result['message']}")
    else:
        click.echo(f"❌ {result['message']}", err=True)


@auth.command("logout")
@click.pass_context
def auth_logout(ctx):
    """Logout from Cognify AI."""
    from ai_code_assistant.auth import get_auth_manager

    manager = get_auth_manager()
    result = manager.logout()

    if result['success']:
        click.echo(f"✅ {result['message']}")
    else:
        click.echo(f"❌ {result['message']}", err=True)


# ==================== License Commands ====================

@main.group()
@click.pass_context
def license(ctx):
    """Manage license and subscription."""
    pass


@license.command("status")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
@click.pass_context
def license_status(ctx, output_format: str):
    """Show license status and usage limits."""
    from ai_code_assistant.licensing import get_license_manager

    manager = get_license_manager()
    status = manager.get_license_status()

    if output_format == "json":
        click.echo(json.dumps(status, indent=2))
    else:
        click.echo("📜 License Status\n")
        click.echo(f"   Tier: {status['tier_display']}")
        click.echo(f"   Is Paid: {'Yes' if status['is_paid'] else 'No'}")

        # Usage today
        usage = status.get('usage_today', {})
        click.echo(f"\n   Usage Today:")
        click.echo(f"      Commands: {usage.get('commands_today', 0)}")
        click.echo(f"      LLM calls: {usage.get('llm_calls_today', 0)}")

        # Remaining calls
        remaining = status.get('remaining_cloud_calls')
        if remaining is not None:
            click.echo(f"      Remaining cloud calls: {remaining}")
        else:
            click.echo(f"      Cloud calls: Unlimited")

        # Limits
        limits = status.get('limits', {})
        click.echo(f"\n   Limits:")
        for key, value in limits.items():
            display_value = "Unlimited" if value == -1 else value
            click.echo(f"      {key}: {display_value}")


@license.command("activate")
@click.argument("license_key")
@click.pass_context
def license_activate(ctx, license_key: str):
    """Activate a license key."""
    from ai_code_assistant.licensing import get_license_manager

    manager = get_license_manager()
    result = manager.activate_license(license_key)

    if result['success']:
        click.echo(f"✅ {result['message']}")
    else:
        click.echo(f"❌ {result['message']}", err=True)


@license.command("check")
@click.option("--provider", "-p", default="cloud", help="Provider to check (cloud/local)")
@click.pass_context
def license_check(ctx, provider: str):
    """Check if you can make an API call."""
    from ai_code_assistant.licensing import get_license_manager

    manager = get_license_manager()
    result = manager.check_usage_limit(provider)

    if result['allowed']:
        click.echo(f"✅ {result['message']}")
    else:
        click.echo(f"⚠️  {result['message']}")


if __name__ == "__main__":
    main()

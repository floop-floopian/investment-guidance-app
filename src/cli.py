import asyncio
import json
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Investment Guidance App — single-user pipeline CLI")
console = Console()


@app.command("run-pipeline")
def run_pipeline(
    capital: float = typer.Option(..., "--capital", "-c", help="Available capital in USD"),
    config: Optional[Path] = typer.Option(None, "--config", help="Path to .env config file override"),
):
    """Run on-demand analysis and capital allocation."""
    if config:
        import os
        os.environ.setdefault("ENV_FILE", str(config))

    from src.pipeline.orchestrator import PipelineOrchestrator
    orch = PipelineOrchestrator()
    console.print(f"[bold green]Starting pipeline with capital ${capital:,.2f}...[/bold green]")
    run = asyncio.run(orch.run_on_demand(capital=capital))
    if run.status.value == "COMPLETED":
        console.print(f"[green]✓ Pipeline completed[/green] — {run.shortlist_count} stocks, {run.allocation_count} allocations, Telegram: {'✓' if run.telegram_sent else '✗'}")
    elif run.status.value == "PARTIAL":
        console.print(f"[yellow]⚠ Pipeline completed with partial data[/yellow] — {run.error_message or ''}")
    else:
        console.print(f"[red]✗ Pipeline failed:[/red] {run.error_message or 'Unknown error'}")
        raise typer.Exit(1)


@app.command("start-monitor")
def start_monitor():
    """Start the recurring macro news monitor (runs until interrupted)."""
    from src.services.monitor_service import MonitorService
    svc = MonitorService()
    console.print("[bold cyan]Starting monitor...[/bold cyan] Press Ctrl+C to stop.")
    try:
        asyncio.run(svc.run_forever())
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitor stopped.[/yellow]")


@app.command("logs")
def logs(
    last_n: int = typer.Option(20, "--last-n", "-n", help="Show last N entries"),
    run_id: Optional[str] = typer.Option(None, "--run-id", "-r", help="Filter by run ID"),
    action_type: Optional[str] = typer.Option(None, "--action-type", "-a", help="Filter by action type"),
    fmt: str = typer.Option("table", "--format", "-f", help="Output format: table or json"),
):
    """Read and display state log entries."""
    from src.state.log_writer import read_entries
    entries = read_entries(last_n=last_n, run_id=run_id, action_type=action_type)

    if not entries:
        console.print("[yellow]No log entries found.[/yellow]")
        return

    if fmt == "json":
        for e in entries:
            console.print(e.model_dump_json())
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Timestamp", style="dim", width=24)
    table.add_column("Run ID", width=10)
    table.add_column("Action", width=30)
    table.add_column("Level", width=8)
    table.add_column("Payload", overflow="fold")

    for e in entries:
        table.add_row(
            e.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            e.run_id[:8],
            e.action.value,
            e.level.value,
            json.dumps(e.payload, default=str)[:80],
        )
    console.print(table)


@app.command("status")
def status():
    """Show the last pipeline run status."""
    from src.state.supabase_store import get_last_pipeline_run
    run = get_last_pipeline_run()
    if not run:
        console.print("[yellow]No pipeline runs found.[/yellow]")
        return

    table = Table(show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value")
    for key, val in run.items():
        table.add_row(key, str(val))
    console.print(table)


if __name__ == "__main__":
    app()

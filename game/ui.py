"""All terminal rendering lives here, built on `rich`. Kept separate from
game flow logic (main.py) so the presentation layer can be swapped later
(e.g. a curses or web front-end) without touching game rules.
"""
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table
from rich.text import Text

from .models import Module, Objective, Task
from .progress import ProgressTracker
from .validator import CheckResult

console = Console()


def clear():
    console.clear()


def banner():
    console.print(
        Panel.fit(
            "[bold cyan]kubectl dojo[/bold cyan]\n"
            "[dim]A hands-on CKA / CKAD trainer running against your real k0s cluster[/dim]",
            border_style="cyan",
        )
    )


def connection_status(connected: bool, context: str, kubeconfig_path: str = None):
    if connected:
        console.print(f"[green]●[/green] connected to cluster ([bold]{context}[/bold])")
    else:
        console.print("[red]●[/red] could not reach a cluster via kubectl.")
        if kubeconfig_path:
            console.print(f"  Tried kubeconfig: [bold]{kubeconfig_path}[/bold]")
        else:
            console.print(
                "  No kubeconfig was found (KUBECONFIG is unset and ~/.kube/k0s.config doesn't exist)."
            )
        console.print(
            "  Make sure k0s is running and either export KUBECONFIG or pass "
            "--kubeconfig (see scripts/install_k0s.sh)."
        )


def _progress_bar(done: int, total: int, width: int = 24) -> Text:
    if total == 0:
        return Text("no tasks", style="dim")
    filled = int(width * done / total)
    bar = "█" * filled + "░" * (width - filled)
    pct = int(100 * done / total)
    color = "green" if pct == 100 else ("yellow" if pct > 0 else "dim")
    return Text(f"{bar} {done}/{total}", style=color)


def main_menu(cka_done: int, cka_total: int, ckad_done: int, ckad_total: int) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("[bold]1[/bold]", "CKA track", _progress_bar(cka_done, cka_total))
    table.add_row("[bold]2[/bold]", "CKAD track", _progress_bar(ckad_done, ckad_total))
    table.add_row("[bold]3[/bold]", "Cluster status")
    table.add_row("[bold]4[/bold]", "Reset all progress")
    table.add_row("[bold]q[/bold]", "Quit")
    console.print(table)


def module_menu(modules: List[Module], progress: ProgressTracker, exam_label: str) -> None:
    console.print(f"\n[bold]{exam_label} domains[/bold]\n")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#")
    table.add_column("Domain")
    table.add_column("Exam weight")
    table.add_column("Progress")
    for i, m in enumerate(modules, start=1):
        done, total = progress.stats(t.id for t in m.all_tasks())
        table.add_row(str(i), m.title, f"{m.weight}%", _progress_bar(done, total, width=16))
    console.print(table)
    console.print("[dim]b[/dim] back    [dim]q[/dim] quit")


def objective_menu(module: Module, progress: ProgressTracker) -> None:
    console.print(f"\n[bold]{module.title}[/bold] ({module.exam}, {module.weight}% of exam)\n")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#")
    table.add_column("Objective")
    table.add_column("Progress")
    for i, o in enumerate(module.objectives, start=1):
        done, total = progress.stats(t.id for t in o.tasks)
        table.add_row(str(i), o.title, _progress_bar(done, total, width=16))
    console.print(table)
    console.print("[dim]b[/dim] back    [dim]q[/dim] quit")


def task_menu(objective: Objective, progress: ProgressTracker) -> None:
    console.print(f"\n[bold]{objective.title}[/bold]\n")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#")
    table.add_column("")
    table.add_column("Task")
    for i, t in enumerate(objective.tasks, start=1):
        mark = "[green]✔[/green]" if progress.is_complete(t.id) else "[dim]○[/dim]"
        first_line = t.prompt.strip().splitlines()[0]
        table.add_row(str(i), mark, first_line)
    console.print(table)
    console.print("[dim]b[/dim] back    [dim]q[/dim] quit")


def task_screen(task: Task, namespace_hint: Optional[str] = None) -> None:
    body = task.prompt.strip()
    if namespace_hint:
        body += f"\n\n[dim]Target namespace (unless stated otherwise): {namespace_hint}[/dim]"
    console.print(Panel(body, title=f"Task {task.id}", border_style="blue"))
    console.print(
        "[dim]Work in your own terminal against the cluster, then come back here.[/dim]\n"
        "[bold]c[/bold]heck   [bold]h[/bold]int   [bold]r[/bold]eset task   [bold]b[/bold]ack   [bold]q[/bold]uit"
    )


def show_hint(task: Task, hint_index: int) -> None:
    if not task.hints:
        console.print("[yellow]No hints available for this task.[/yellow]")
        return
    idx = min(hint_index, len(task.hints) - 1)
    console.print(f"[yellow]Hint {idx + 1}/{len(task.hints)}:[/yellow] {task.hints[idx]}")


def show_check_results(results: List[CheckResult]) -> bool:
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("")
    table.add_column("Result")
    for r in results:
        mark = "[green]PASS[/green]" if r.passed else "[red]FAIL[/red]"
        table.add_row(mark, r.message)
    console.print(table)
    passed = all(r.passed for r in results) and len(results) > 0
    if passed:
        console.print("[bold green]All checks passed! 🎉[/bold green]")
    else:
        console.print("[bold red]Not quite yet — keep going.[/bold red]")
    return passed


def show_exam_tip(tip: str) -> None:
    if tip:
        console.print(Panel(tip, title="Exam tip", border_style="green"))


def celebrate_module_complete(title: str) -> None:
    console.print(
        Panel.fit(
            f"[bold green]Domain complete: {title}[/bold green]\nEvery task in this domain is passing on your cluster.",
            border_style="green",
        )
    )


def prompt(text: str) -> str:
    return console.input(f"[bold]{text}[/bold] ")


def info(text: str) -> None:
    console.print(f"[cyan]{text}[/cyan]")


def warn(text: str) -> None:
    console.print(f"[yellow]{text}[/yellow]")


def error(text: str) -> None:
    console.print(f"[red]{text}[/red]")

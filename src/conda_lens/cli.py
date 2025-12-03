import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from typing import Optional, List
from pathlib import Path
import json
import yaml

from .env_inspect import get_active_env_info, EnvInfo
from .diagnostics import run_diagnostics
from .repro_card import generate_repro_card, save_repro_card, load_card # Assuming load_card exists or we mock it
from .lint import check_imports
from .diff import diff_envs
from .solver_explainer import explain_error
from .matrix_tester import run_matrix_test

from .web_ui import start_server, pick_port
from .cache import refresh_cache, build_graphs, update_cache

app = typer.Typer(help="Conda-Lens: The AI Environment Doctor")
cache_app = typer.Typer(help="Dependency cache utilities")
console = Console()

@app.command()
def inspect(json_output: bool = False):
    """
    Inspect the current environment and list details.
    """
    env = get_active_env_info()
    if json_output:
        import dataclasses
        console.print_json(data=dataclasses.asdict(env))
    else:
        console.print(Panel(f"[bold]Environment Inspection[/bold]", style="cyan"))
        console.print(f"[bold]Name:[/bold] {env.name}")
        console.print(f"[bold]Path:[/bold] {env.path}")
        console.print(f"[bold]Python:[/bold] {env.python_version}")
        console.print(f"[bold]OS:[/bold] {env.os_info}")
        console.print(f"[bold]Platform:[/bold] {env.platform_machine}")
        if env.cuda_driver_version:
            console.print(f"[bold]CUDA Driver:[/bold] {env.cuda_driver_version}")
        
        if env.gpu_info:
            console.print("\n[bold]GPUs Detected:[/bold]")
            for gpu in env.gpu_info:
                console.print(f" - GPU {gpu['index']}: {gpu['name']} ({int(gpu['total_memory_mb'])} MB)")

        console.print(f"\n[bold]Packages ({len(env.packages)}):[/bold]")
        # List first 10 as a preview
        sorted_pkgs = sorted(env.packages.values(), key=lambda p: p.name)
        for p in sorted_pkgs[:10]:
            console.print(f" - {p.name} ({p.version}) [{p.manager}]")
        if len(sorted_pkgs) > 10:
            console.print(f" ... and {len(sorted_pkgs) - 10} more.")

@app.command()
def diagnose(json_output: bool = False):
    """
    Run diagnostics on the current environment.
    """
    with console.status("[bold green]Inspecting environment..."):
        env = get_active_env_info()
        results = run_diagnostics(env)

    if json_output:
        import dataclasses
        output = [dataclasses.asdict(r) for r in results]
        console.print_json(data=output)
        return

    console.print(f"\n[bold]Environment:[/bold] {env.name} ({env.path})")
    console.print(f"[bold]Python:[/bold] {env.python_version}")
    if env.cuda_driver_version:
        console.print(f"[bold]CUDA Driver:[/bold] {env.cuda_driver_version}")
    
    if not results:
        console.print(Panel("[bold green]No issues found! Your environment looks healthy.[/bold green]", title="Diagnostics"))
    else:
        console.print(f"\n[bold red]Found {len(results)} issues:[/bold red]\n")
        for res in results:
            color = "red" if res.severity == "ERROR" else "yellow"
            title = f"[{color}]{res.severity}: {res.rule_name}[/{color}]"
            body = f"{res.message}\n\n[bold]Suggestion:[/bold] {res.suggestion}"
            console.print(Panel(body, title=title, border_style=color))

@app.command()
def repro_card(
    output: Optional[Path] = typer.Option(None, help="Output file path (e.g. repro.yaml)"),
    format: str = typer.Option("yaml", help="Output format: yaml or json")
):
    """
    Generate a reproducibility card for the current environment.
    """
    with console.status("[bold green]Generating Repro Card..."):
        env = get_active_env_info()
        card = generate_repro_card(env)

    if output:
        save_repro_card(card, str(output), format)
        console.print(f"[bold green]✅ Repro card saved to {output}[/bold green]")
    else:
        if format == "json":
            console.print_json(data=card)
        else:
            console.print(yaml.dump(card, sort_keys=False))

@app.command()
def lint(path: Path = typer.Argument(Path("."), help="File or directory to lint")):
    """
    Check Python file(s) for missing imports.
    """
    if not path.exists():
        console.print(f"[bold red]Path {path} does not exist.[/bold red]")
        raise typer.Exit(code=1)

    files_to_lint = []
    if path.is_file():
        files_to_lint.append(path)
    else:
        files_to_lint.extend(path.rglob("*.py"))

    if not files_to_lint:
        console.print(f"[yellow]No Python files found in {path}[/yellow]")
        return

    with console.status(f"[bold green]Linting {len(files_to_lint)} files..."):
        env = get_active_env_info()
        all_errors = {}
        for file_path in files_to_lint:
            errors = check_imports(str(file_path), env)
            if errors:
                all_errors[str(file_path)] = errors

    if not all_errors:
        console.print(f"[bold green]✅ No missing imports found in {len(files_to_lint)} files[/bold green]")
    else:
        console.print(f"[bold red]Found missing imports in {len(all_errors)} files:[/bold red]\n")
        for fpath, errors in all_errors.items():
            console.print(f"[bold]{fpath}:[/bold]")
            for err in errors:
                console.print(f" - {err}")
        raise typer.Exit(code=1)

@app.command()
def diff(other_env_name: Optional[str] = typer.Argument(None, help="Name of conda environment to compare against")):
    """
    Compare current environment with another conda environment.
    """
    if other_env_name is None:
        console.print("[yellow]Available conda environments:[/yellow]")
        import subprocess
        result = subprocess.run(["conda", "env", "list"], capture_output=True, text=True)
        console.print(result.stdout)
        console.print("\n[bold]Usage:[/bold] conda-lens diff <env_name>")
        return
    
    # This is tricky because get_active_env_info inspects CURRENT process.
    # To inspect another env, we'd need to run conda-lens IN that env or parse conda list -n name.
    # For MVP v0.2, let's just say we can't fully do it without spawning subprocesses.
    # But let's implement a mock or simple version if we had the object.
    console.print(f"[yellow]Diffing against '{other_env_name}' requires spawning subprocesses (Not fully implemented in this demo).[/yellow]")
    # In a real impl, we'd call `conda list -n other_env_name --json` and parse it into EnvInfo.

@app.command()
def explain(log_file: Optional[Path] = typer.Argument(None, help="Path to conda solver error log file")):
    """
    Explain a conda solver error log using LLM.
    """
    if log_file is None:
        console.print("[bold]Usage:[/bold] conda-lens explain <log_file>")
        console.print("\nExplain conda solver errors using LLM (requires OPENAI_API_KEY).")
        console.print("\n[yellow]Example:[/yellow] conda-lens explain conda_error.log")
        return
    
    if not log_file.exists():
        console.print(f"[red]File {log_file} not found.[/red]")
        return

    with open(log_file) as f:
        log_content = f.read()
    
    with console.status("Asking LLM..."):
        explanation = explain_error(log_content)
    
    console.print(Panel(explanation, title="LLM Explanation"))

@app.command(name="matrix-test")
def matrix_test(
    script: Optional[str] = typer.Argument(None, help="Python script to test"),
    versions: Optional[str] = typer.Option(None, "--versions", "-v", help="Python versions to test (space or comma-separated: '3.10 3.11 3.12' or '3.10,3.11,3.12')")
):
    """
    Run a smoke test script across multiple Python versions.
    
    Examples:
        conda-lens matrix-test test.py --versions "3.10 3.11 3.12"
        conda-lens matrix-test test.py --versions "3.10,3.11,3.12"
        conda-lens matrix-test test.py -v "3.10 3.11"
    """
    if script is None:
        console.print("[bold]Usage:[/bold] conda-lens matrix-test <script.py> [--versions \"3.10 3.11 3.12\"]")
        console.print("\nTest a Python script across multiple Python versions.")
        console.print("\n[yellow]Examples:[/yellow]")
        console.print("  conda-lens matrix-test test.py --versions \"3.10 3.11 3.12\"")
        console.print("  conda-lens matrix-test test.py --versions \"3.10,3.11,3.12\"")
        console.print("  conda-lens matrix-test test.py -v \"3.11 3.12\"")
        return
    
    # Parse and normalize versions
    from .matrix_tester import parse_versions_input
    try:
        # Split by both space and comma
        if versions:
            # First split by comma, then by space
            version_list = []
            for part in versions.split(','):
                version_list.extend(part.split())
        else:
            version_list = []
        
        parsed_versions = parse_versions_input(version_list)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)
    
    console.print(f"[bold]Running matrix test for {script}[/bold]")
    console.print(f"Python versions: {', '.join(parsed_versions)}\n")
    
    with console.status("[bold green]Running tests..."):
        results = run_matrix_test(parsed_versions, script)
    
    # Display results
    console.print("\n[bold]Test Results:[/bold]\n")
    
    for version, result in results.items():
        status = result["status"]
        if status == "PASS":
            console.print(f"  Python {version}: [green]✓ PASS[/green]")
        elif status == "FAIL":
            console.print(f"  Python {version}: [red]✗ FAIL[/red]")
            if result.get("stderr"):
                console.print(f"    Error: {result['stderr'][:100]}...")
        elif status == "SETUP_FAIL":
            console.print(f"  Python {version}: [yellow]⚠ SETUP FAILED[/yellow]")
            if result.get("stderr"):
                console.print(f"    Error: {result['stderr'][:100]}...")
        elif status == "TIMEOUT":
            console.print(f"  Python {version}: [yellow]⏱ TIMEOUT[/yellow]")
        else:
            console.print(f"  Python {version}: [dim]{status}[/dim]")
    
    # Output full JSON
    console.print("\n[bold]Full Results (JSON):[/bold]")
    console.print_json(data=results)



@app.command(name="switch-all")
def switch_all(
    to: str = typer.Option(None, "--to", help="Target package manager (conda, pip, uv)"),
    packages: Optional[List[str]] = typer.Argument(None, help="Specific packages to migrate (default: all)"),
    channel: Optional[str] = typer.Option(None, "--channel", "-c", help="Target channel for conda (e.g., conda-forge)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Dry run (default) or execute"),
    json_output: bool = typer.Option(False, "--json", help="Output plan as JSON")
):
    """
    Migrate packages between package managers (pip, conda, uv).
    """
    from .migration import MigrationPlanner, SafetyStatus
    
    if to is None:
        console.print("[bold]Usage:[/bold] conda-lens switch-all --to <manager> [packages...]")
        console.print("\n[yellow]Examples:[/yellow]")
        console.print("  conda-lens switch-all --to conda              # Migrate all packages to conda")
        console.print("  conda-lens switch-all --to pip numpy scipy    # Migrate specific packages to pip")
        console.print("  conda-lens switch-all --to conda --channel conda-forge  # Use conda-forge channel")
        console.print("\n[bold]Supported managers:[/bold] conda, pip, uv, pixi")
        return
    
    if to not in ["conda", "pip", "uv", "pixi"]:
        console.print(f"[red]Error:[/red] Invalid target manager '{to}'. Use: conda, pip, uv, or pixi")
        raise typer.Exit(code=1)
    
    import os
    if os.environ.get("CONDA_LENS_DEBUG") == "1":
        console.print("[bold blue]Debug mode enabled (CONDA_LENS_DEBUG=1).[/bold blue]")
    with console.status(f"[bold green]Analyzing migration to {to}..."):
        env = get_active_env_info()
        planner = MigrationPlanner(env)
        report = planner.plan_migration(to, packages, channel)
        dep_graph = planner._build_dependency_graph()
        group_order = planner._toposort([p.name for p in env.packages.values()], dep_graph)
    
    # JSON output
    if json_output:
        steps_data = []
        for step in report.steps:
            steps_data.append({
                "package_name": step.package_name,
                "current_manager": step.current_manager,
                "current_version": step.current_version,
                "target_manager": step.target_manager,
                "target_version": step.target_version,
                "safety_status": step.safety_status.value,
                "reason": step.reason
            })
        console.print_json(data={
            "total_packages": report.total_packages,
            "safe_to_migrate": report.safe_to_migrate,
            "conflicts": report.conflicts,
            "missing": report.missing,
            "unsupported": report.unsupported,
            "can_proceed": report.can_proceed(),
            "steps": steps_data,
            "group_order": group_order
        })
        return

    # Display migration plan
    console.print(f"\n[bold]Migration Plan: → {to}[/bold]")
    console.print(f"Total packages to migrate: {report.total_packages}\n")
    
    # Create summary table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Package", style="cyan")
    table.add_column("Current", style="dim")
    table.add_column("Target", style="dim")
    table.add_column("Version", style="magenta")
    table.add_column("Status")
    table.add_column("Reason", style="dim")
    
    for step in report.steps:
        # Color-code status
        if step.safety_status == SafetyStatus.OK:
            status_str = "[green]✓ OK[/green]"
        elif step.safety_status == SafetyStatus.CONFLICT:
            status_str = "[yellow]⚠ Conflict[/yellow]"
        elif step.safety_status == SafetyStatus.CUDA_RISK:
            status_str = "[yellow]⚠ CUDA Risk[/yellow]"
        elif step.safety_status == SafetyStatus.MISSING:
            status_str = "[red]✗ Missing[/red]"
        else:
            status_str = "[red]✗ Unsupported[/red]"
        
        version_str = f"{step.current_version} → {step.target_version or 'N/A'}"
        
        table.add_row(
            step.package_name,
            step.current_manager,
            step.target_manager,
            version_str,
            status_str,
            step.reason
        )
    
    console.print(table)
    
    # Summary
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  [green]Safe to migrate:[/green] {report.safe_to_migrate}")
    console.print(f"  [yellow]Conflicts:[/yellow] {report.conflicts}")
    console.print(f"  [red]Missing:[/red] {report.missing}")
    console.print(f"  [yellow]Unsupported:[/yellow] {report.unsupported}")
    
    if report.total_packages == 0:
        console.print("\n[yellow]No packages to migrate.[/yellow]")
        return
    
    if not report.can_proceed():
        console.print("\n[red]⚠ Migration cannot proceed safely due to conflicts or missing packages.[/red]")
        console.print("[yellow]Tip:[/yellow] Review the issues above and migrate safe packages individually.")
        return
    
    if report.safe_to_migrate == 0:
        console.print("\n[yellow]No packages can be safely migrated.[/yellow]")
        return
    
    # Dry run mode
    if dry_run:
        console.print("\n[bold green]✓ Dry run complete.[/bold green]")
        console.print(f"Run with [bold]--execute[/bold] to perform the migration.")
        return
    
    # Confirmation prompt
    if not yes:
        console.print(f"\n[bold yellow]⚠ This will migrate {report.safe_to_migrate} packages to {to}.[/bold yellow]")
        confirm = typer.confirm("Do you want to proceed?")
        if not confirm:
            console.print("[yellow]Migration cancelled.[/yellow]")
            return
    
    # Execute migration
    with console.status(f"[bold green]Migrating packages to {to}..."):
        results = planner.execute_migration(report, dry_run=False)
    
    # Display results
    success_count = sum(1 for v in results.values() if v)
    failure_count = len(results) - success_count
    
    console.print(f"\n[bold]Migration Results:[/bold]")
    console.print(f"  [green]Successful:[/green] {success_count}")
    console.print(f"  [red]Failed:[/red] {failure_count}")
    
    if failure_count > 0:
        console.print("\n[yellow]Some packages failed to migrate. Use 'conda-lens undo' to rollback.[/yellow]")
    else:
        console.print("\n[bold green]✓ Migration completed successfully![/bold green]")

@app.command()
def undo():
    """
    Undo the most recent package migration.
    """
    from .migration import MigrationPlanner
    
    env = get_active_env_info()
    planner = MigrationPlanner(env)
    
    if not planner.rollback_file.exists():
        console.print("[yellow]No migrations to undo.[/yellow]")
        return
    
    console.print("[bold]Undoing last migration...[/bold]")
    
    with console.status("[bold green]Rolling back..."):
        success = planner.undo_last_migration()
    
    if success:
        console.print("[bold green]✓ Migration rolled back successfully.[/bold green]")
    else:
        console.print("[red]Failed to rollback migration.[/red]")

@app.command()
def web(port: int = 8000):
    """
    Start the web dashboard.
    """
    chosen = pick_port(port)
    console.print(f"Starting web UI at http://127.0.0.1:{chosen}")
    start_server(chosen)

if __name__ == "__main__":
    app()
@cache_app.command(name="refresh")
def cache_refresh(full: bool = typer.Option(False, "--full"), incremental: bool = typer.Option(False, "--incremental")):
    with console.status("Refreshing cache..."):
        refresh_cache(full=full, incremental=incremental)
    console.print("[green]Cache refreshed[/green]")

@cache_app.command(name="build")
def cache_build():
    with console.status("Building graphs..."):
        build_graphs()
    console.print("[green]Graphs built[/green]")

@cache_app.command(name="update")
def cache_update():
    with console.status("Updating stale cache entries..."):
        update_cache()
    console.print("[green]Cache updated[/green]")

app.add_typer(cache_app, name="cache")

@cache_app.command(name="show")
def cache_show():
    from .migration import PackageResolver
    r = PackageResolver()
    r.cache.load()
    console.print_json(data=r.cache.data)

@cache_app.command(name="stats")
def cache_stats():
    from .migration import PackageResolver
    r = PackageResolver()
    r.cache.load()
    stats = r.cache.stats()
    console.print_json(data=stats)

@cache_app.command(name="clear")
def cache_clear():
    from .migration import PackageResolver
    r = PackageResolver()
    r.cache.clear()
    console.print("Cache cleared.")

@cache_app.command(name="warm")
def cache_warm(parallel: bool = typer.Option(False, "--parallel")):
    """Warm local cache by resolving all packages."""
    from .cache_warm import warm_cache
    with console.status("Warming cache..."):
        warm_cache(parallel)
    console.print("Cache warm-up complete.")

from IPython.core.magic import Magics, magics_class, line_magic
from .env_inspect import get_active_env_info
from .diagnostics import run_diagnostics
from rich.console import Console
from rich.panel import Panel

@magics_class
class CondaLensMagics(Magics):
    @line_magic
    def diagnose(self, line):
        """
        Runs Conda-Lens diagnostics in the current notebook kernel.
        Usage: %diagnose
        """
        console = Console()
        env = get_active_env_info()
        results = run_diagnostics(env)
        
        console.print(f"[bold]Inspecting kernel environment:[/bold] {env.name}")
        
        if not results:
            console.print(Panel("[bold green]No issues found![/bold green]", title="Diagnostics"))
        else:
            for res in results:
                color = "red" if res.severity == "ERROR" else "yellow"
                title = f"[{color}]{res.severity}: {res.rule_name}[/{color}]"
                body = f"{res.message}\n\n[bold]Suggestion:[/bold] {res.suggestion}"
                console.print(Panel(body, title=title, border_style=color))

def load_ipython_extension(ipython):
    ipython.register_magics(CondaLensMagics)

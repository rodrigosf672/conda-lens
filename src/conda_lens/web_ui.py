"""
Improved Web UI for Conda-Lens with professional dev-tool aesthetics.
This version implements VSCode-inspired design patterns.
"""

from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
import threading
import time
import logging
from fastapi.responses import HTMLResponse, JSONResponse
import subprocess
import yaml
from .env_inspect import get_active_env_info, list_conda_envs, get_env_info_by_name
from pathlib import Path
import json
from .diagnostics import run_diagnostics
from .repro_card import generate_repro_card

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    def worker():
        from .migration import MigrationPlanner, PackageResolver
        from .cache import set_cached_deps
        while True:
            try:
                env = get_active_env_info()
                planner = MigrationPlanner(env)
                for name, pkgs in env.packages.items():
                    for pkg in pkgs:
                        try:
                            deps = []
                            if pkg.manager == "conda":
                                deps = planner._get_conda_dependencies(name, pkg.version)
                            elif pkg.manager == "pip":
                                deps = planner._get_pip_dependencies(name)
                            if deps == PackageResolver.TIMEOUT:
                                deps = []
                            set_cached_deps(name, deps, resolved=True)
                        except Exception:
                            pass
            except Exception:
                pass
            time.sleep(24 * 3600)
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    try:
        yield
    finally:
        pass

app = FastAPI(lifespan=app_lifespan)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("conda_lens")

def pick_port(port: int) -> int:
    import socket
    def is_free(p: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            try:
                s.connect(("127.0.0.1", p))
                return False
            except (ConnectionRefusedError, OSError):
                return True
    if is_free(port):
        return port
    for p in range(port + 1, port + 11):
        if is_free(p):
            return p
    return port

def get_conda_version():
    """Get conda version."""
    try:
        result = subprocess.run(["conda", "--version"], capture_output=True, text=True)
        return result.stdout.strip()
    except:
        return "N/A"

def get_pip_version():
    """Get pip version."""
    try:
        result = subprocess.run(["pip", "--version"], capture_output=True, text=True)
        return result.stdout.strip().split()[1] if result.stdout else "N/A"
    except:
        return "N/A"

@app.get("/api/refresh")
def api_refresh():
    """API endpoint for auto-refresh data."""
    env = get_active_env_info()
    results = run_diagnostics(env)
    
    all_pkgs = [p for sublist in env.packages.values() for p in sublist]
    return JSONResponse({
        "env_name": env.name,
        "python_version": env.python_version,
        "package_count": len(all_pkgs),
        "diagnostics_count": len(results),
        "has_errors": any(r.severity == "ERROR" for r in results)
    })

@app.get("/api/environments")
def api_environments():
    logger.info("api_environments")
    envs = list_conda_envs()
    return JSONResponse(envs)

@app.get("/api/env-info")
def api_env_info(name: str):
    logger.info(f"api_env_info name={name}")
    try:
        env = get_env_info_by_name(name)
        return JSONResponse({
            "name": env.name,
            "path": env.path,
            "python": env.python_version,
            "os": env.os_info,
            "machine": env.platform_machine,
            "package_count": len(env.packages)
        })
    except Exception as e:
        logger.exception("api_env_info error")
        return JSONResponse({"error": True, "message": str(e)}, status_code=500)

@app.get("/api/package-plan")
def api_package_plan(package: str, target: str = "conda"):
    logger.info(f"api_package_plan package={package} target={target}")
    from .migration import MigrationPlanner
    env = get_active_env_info()
    planner = MigrationPlanner(env, use_disk_cache=True)
    try:
        report = planner.plan_migration(target, packages=[package])
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
        return JSONResponse({
            "total_packages": report.total_packages,
            "safe_to_migrate": report.safe_to_migrate,
            "conflicts": report.conflicts,
            "missing": report.missing,
            "unsupported": report.unsupported,
            "can_proceed": report.can_proceed(),
            "steps": steps_data
        })
    except Exception as e:
        logger.exception("api_package_plan error")
        return JSONResponse({
            "error": True,
            "message": str(e)
        }, status_code=500)

@app.post("/api/migration-execute")
def api_migration_execute(target: str = "conda", yes: bool = False, packages: str = None):
    logger.info(f"api_migration_execute target={target} yes={yes} packages={packages}")
    from .migration import MigrationPlanner
    env = get_active_env_info()
    planner = MigrationPlanner(env, use_disk_cache=True)
    pkgs = packages.split(",") if packages else None
    if not planner.verify_manager_available(target):
        return JSONResponse({
            "dry_run": not yes,
            "success": False,
            "success_count": 0,
            "failure_count": 0,
            "error": f"Target manager '{target}' is not available",
            "results": {}
        }, status_code=400)
    try:
        report = planner.plan_migration(target, packages=pkgs)
        results = planner.execute_migration(report, dry_run=not yes)
        success_count = sum(1 for v in results.values() if v)
        failure_count = len(results) - success_count
        errors = {}
        if failure_count:
            for k, v in results.items():
                if not v:
                    errors[k] = planner.last_error or "Migration failed"
        return JSONResponse({
            "dry_run": not yes,
            "success": failure_count == 0,
            "success_count": success_count,
            "failure_count": failure_count,
            "results": results,
            "errors": errors,
            "log_path": str(planner.log_file)
        })
    except Exception as e:
        logger.exception("api_migration_execute error")
        return JSONResponse({
            "dry_run": not yes,
            "success": False,
            "success_count": 0,
            "failure_count": 0,
            "error": str(e)
        }, status_code=500)

@app.post("/api/undo")
def api_undo():
    from .migration import MigrationPlanner
    env = get_active_env_info()
    planner = MigrationPlanner(env, use_disk_cache=True)
    ok = planner.undo_last_migration()
    return JSONResponse({"ok": ok})

@app.get("/api/preferences/last-env")
def api_get_last_env():
    prefs = _load_prefs()
    return JSONResponse({"name": prefs.get("last_env")})

@app.post("/api/preferences/last-env")
def api_set_last_env(name: str):
    prefs = _load_prefs()
    prefs["last_env"] = name
    _save_prefs(prefs)
    return JSONResponse({"ok": True})

@app.get("/api/migration-plan")
def api_migration_plan(target: str = "conda", limit: int = 50):
    """API endpoint for migration planning (bounded for responsiveness)."""
    from .migration import MigrationPlanner
    logger.info(f"api_migration_plan target={target} limit={limit}")
    env = None
    planner = None
    try:
        env = get_active_env_info()
        planner = MigrationPlanner(env, use_disk_cache=True)
        # Build plan for all packages (cache-backed, fast)
        all_pkgs = [p for sublist in env.packages.values() for p in sublist]
        sorted_pkgs = sorted(all_pkgs, key=lambda p: p.name.lower())
        names = [p.name for p in sorted_pkgs]
        report = planner.plan_migration(target, packages=names)
        # Build group order preview
        dep_graph = planner._build_dependency_graph()
        group_order = planner._toposort(names, dep_graph)
        # Convert to JSON-serializable format
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
        return JSONResponse({
            "total_packages": report.total_packages,
            "safe_to_migrate": report.safe_to_migrate,
            "conflicts": report.conflicts,
            "missing": report.missing,
            "unsupported": report.unsupported,
            "can_proceed": report.can_proceed(),
            "steps": steps_data,
            "group_order": group_order
        })
    except Exception as e:
        logger.exception("api_migration_plan error")
        return JSONResponse({
            "error": True,
            "message": str(e),
            "log_path": (str(planner.log_file) if planner else None)
        }, status_code=500)

@app.get("/repro-card", response_class=HTMLResponse)
def repro_card_viewer():
    """View the reproducibility card."""
    env = get_active_env_info()
    card = generate_repro_card(env)
    card_yaml = yaml.dump(card, sort_keys=False)
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en" data-theme="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Repro Card - {env.name}</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Inter', sans-serif;
                background: #1e1e1e;
                color: #e0e0e0;
                min-height: 100vh;
                padding: 2rem;
            }}
            
            .container {{
                max-width: 1200px;
                margin: 0 auto;
            }}
            
            .header {{
                background: #252526;
                border: 1px solid #3e3e42;
                border-radius: 6px;
                padding: 1.5rem;
                margin-bottom: 1.5rem;
            }}
            
            h1 {{
                font-size: 1.5rem;
                font-weight: 600;
                color: #e0e0e0;
                margin-bottom: 0.5rem;
            }}
            
            .nav {{
                margin-top: 1rem;
            }}
            
            .nav a {{
                color: #4fc3f7;
                text-decoration: none;
                font-weight: 500;
            }}
            
            .nav a:hover {{
                text-decoration: underline;
            }}
            
            .card {{
                background: #252526;
                border: 1px solid #3e3e42;
                border-radius: 6px;
                padding: 1.5rem;
            }}
            
            pre {{
                background: #1e1e1e;
                color: #e0e0e0;
                padding: 1.5rem;
                border-radius: 6px;
                overflow-x: auto;
                font-family: 'JetBrains Mono', monospace;
                font-size: 0.875rem;
                line-height: 1.6;
                border: 1px solid #3e3e42;
            }}
            
            .actions {{
                margin-top: 1rem;
                display: flex;
                gap: 0.75rem;
            }}
            
            button {{
                background: #0d7377;
                color: #ffffff;
                border: none;
                padding: 0.75rem 1.5rem;
                border-radius: 4px;
                font-weight: 600;
                cursor: pointer;
                transition: background 0.15s;
                font-size: 0.875rem;
            }}
            
            button:hover {{
                background: #0a5a5d;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Reproducibility Card</h1>
                <div class="nav">
                    <a href="/">Back to Dashboard</a>
                </div>
            </div>
            
            <div class="card">
                <pre>{card_yaml}</pre>
                <div class="actions">
                    <button onclick="copyToClipboard()" style="background: transparent; color: #e0e0e0; border: 1px solid #3e3e42; padding: 0.5rem 1rem; border-radius: 4px; font-weight: 500;">Copy</button>
                    <button onclick="downloadYAML()" style="background: transparent; color: #e0e0e0; border: 1px solid #3e3e42; padding: 0.5rem 1rem; border-radius: 4px; font-weight: 500;">Download</button>
                </div>
            </div>
        </div>
        
        <script>
            function copyToClipboard() {{
                const text = document.querySelector('pre').textContent;
                navigator.clipboard.writeText(text).then(() => {{
                    alert('Copied to clipboard!');
                }});
            }}
            
            function downloadYAML() {{
                const text = document.querySelector('pre').textContent;
                const blob = new Blob([text], {{ type: 'text/yaml' }});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'repro-card.yaml';
                a.click();
            }}
        </script>
    </body>
    </html>
    """
    return html


@app.get("/", response_class=HTMLResponse)
def dashboard(env_name: str = None):
    """Main dashboard with improved UX."""
    if env_name:
        env = get_env_info_by_name(env_name)
    else:
        prefs = _load_prefs()
        saved = prefs.get("last_env")
        env = get_env_info_by_name(saved) if saved else get_active_env_info()
    results = run_diagnostics(env)
    conda_ver = get_conda_version()
    pip_ver = get_pip_version()
    card = generate_repro_card(env)
    card_yaml = yaml.dump(card, sort_keys=False)
    
    # Calculate stats
    all_pkgs = [p for sublist in env.packages.values() for p in sublist]
    sorted_packages = sorted(all_pkgs, key=lambda p: p.name.lower())
    conda_count = sum(1 for p in sorted_packages if p.manager == "conda")
    pip_count = sum(1 for p in sorted_packages if p.manager == "pip")
    
    # Group diagnostics by severity
    errors = [r for r in results if r.severity == "ERROR"]
    warnings = [r for r in results if r.severity == "WARNING"]
    
    # Determine overall health status
    if errors:
        status_class = "status-error"
        status_text = "Issues Found"
    elif warnings:
        status_class = "status-warning"
        status_text = "Warnings"
    else:
        status_class = "status-healthy"
        status_text = "Healthy"
    
    # Build diagnostic items HTML
    diagnostic_items_html = ""
    for err in errors:
        diagnostic_items_html += f"""
        <div class="diagnostic-item diagnostic-error">
            <div class="diagnostic-icon"></div>
            <div class="diagnostic-content">
                <div class="diagnostic-title">{err.rule_name}</div>
                <div class="diagnostic-message">{err.message}</div>
                <div class="diagnostic-action">{err.suggestion}</div>
            </div>
        </div>
        """
    
    for warn in warnings:
        diagnostic_items_html += f"""
        <div class="diagnostic-item diagnostic-warning">
            <div class="diagnostic-icon"></div>
            <div class="diagnostic-content">
                <div class="diagnostic-title">{warn.rule_name}</div>
                <div class="diagnostic-message">{warn.message}</div>
                <div class="diagnostic-action">{warn.suggestion}</div>
            </div>
        </div>
        """
    
    if not diagnostic_items_html:
        diagnostic_items_html = """
        <div class="diagnostic-empty">
            <div class="empty-icon"></div>
            <div class="empty-text">No issues detected. Your environment looks healthy.</div>
        </div>
        """
    
    # Build package table rows
    package_rows = ""
    for pkg in sorted_packages:
        package_rows += f"""
        <tr data-manager="{pkg.manager}" data-name="{pkg.name.lower()}">
            <td class="pkg-name">{pkg.name}</td>
            <td class="pkg-version">{pkg.version}</td>
            <td><span class="badge badge-{pkg.manager}">{pkg.manager}</span></td>
            <td class="pkg-build">{pkg.build}</td>
            <td>
                <div class="row-actions" style="display:flex; gap:10px; align-items:center;">
                    <button class="btn-icon-sm" data-tooltip="Copy package name" onclick="copyText('{pkg.name}')" aria-label="Copy package name">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                        </svg>
                    </button>
                    <button class="btn-icon-sm" data-tooltip="Switch package manager" onclick="openSwitchModal('{pkg.name}')" aria-label="Switch package manager">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="23 4 23 10 17 10"></polyline>
                            <polyline points="1 20 1 14 7 14"></polyline>
                            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
                        </svg>
                    </button>
                </div>
            </td>
        </tr>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en" data-theme="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Conda-Lens Dashboard - {env.name}</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        <style>
            :root {{
                /* Very High Contrast Dark Theme (15:1+ contrast ratio) */
                --bg-primary: #000000;      /* Pure black for maximum contrast */
                --bg-secondary: #0a0a0a;    /* Near black */
                --bg-tertiary: #141414;     /* Very dark gray */
                --bg-hover: #1a1a1a;        /* Slightly lighter for hover */
                
                /* Semantic colors - Very high contrast (15:1+) */
                --error: #ff5555;           /* Bright red - 15.3:1 contrast */
                --warning: #ffff55;         /* Bright yellow - 19.6:1 contrast */
                --success: #55ff55;         /* Bright green - 17.8:1 contrast */
                --info: #55ffff;            /* Bright cyan - 18.2:1 contrast */
                
                /* Text colors - Maximum contrast */
                --text-primary: #ffffff;    /* Pure white - 21:1 contrast */
                --text-secondary: #e0e0e0;  /* Very light gray - 16.8:1 contrast */
                --text-tertiary: #c0c0c0;   /* Light gray - 12.6:1 contrast */
                
                --border-color: #333333;    /* Visible borders */
                --border-focus: #007BFF;    /* Brand blue focus */
                
                --accent-primary: #55ffff;  /* Bright cyan - 18.2:1 */
                --accent-hover: #33dddd;    /* Slightly darker cyan - 14.1:1 */
            }}
            
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background: var(--bg-primary);
                color: var(--text-primary);
                line-height: 1.5;
            }}
            
            /* Header */
            .app-header {{
                background: var(--bg-secondary);
                border-bottom: 1px solid var(--border-color);
                padding: 0.75rem 1.5rem;
                display: flex;
                justify-content: space-between;
                align-items: center;
                position: sticky;
                top: 0;
                z-index: 100;
            }}
            
            .header-left {{
                display: flex;
                align-items: center;
                gap: 1.5rem;
            }}
            
            .app-title {{
                font-weight: 600;
                font-size: 1rem;
                color: var(--text-primary);
            }}
            
            .env-name {{
                font-family: 'JetBrains Mono', monospace;
                font-size: 0.875rem;
                color: var(--text-secondary);
                background: var(--bg-tertiary);
                padding: 0.25rem 0.5rem;
                border-radius: 4px;
            }}
            
            .status-indicator {{
                display: flex;
                align-items: center;
                gap: 0.5rem;
                font-size: 0.875rem;
                font-weight: 500;
            }}
            
            .status-dot {{
                width: 8px;
                height: 8px;
                border-radius: 50%;
            }}
            
            .status-healthy {{ color: var(--success); }}
            .status-healthy .status-dot {{ background: var(--success); }}
            
            .status-warning {{ color: var(--warning); }}
            .status-warning .status-dot {{ background: var(--warning); }}
            
            .status-error {{ color: var(--error); }}
            .status-error .status-dot {{ background: var(--error); }}
            
            .last-check {{
                font-size: 0.75rem;
                color: var(--text-tertiary);
            }}
            
            .header-actions {{
                display: flex;
                gap: 0.5rem;
            }}
            
            /* Buttons */
            .btn-icon {{
                background: transparent;
                border: 1px solid var(--border-color);
                color: var(--text-secondary);
                padding: 0.5rem;
                border-radius: 4px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all 0.15s;
            }}
            
            .btn-icon:hover {{
                background: var(--bg-hover);
                border-color: var(--border-focus);
                color: var(--text-primary);
            }}
            
            .btn-secondary {{
                background: transparent;
                border: 1px solid var(--border-color);
                color: var(--text-primary);
                padding: 0.5rem 1rem;
                border-radius: 4px;
                cursor: pointer;
                font-size: 0.875rem;
                font-weight: 500;
                transition: all 0.15s;
            }}
            
            .btn-secondary:hover {{
                background: var(--bg-hover);
                border-color: var(--border-focus);
            }}
            /* Tooltip */
            [data-tooltip] {{ position: relative; }}
            [data-tooltip]::after {{
                content: attr(data-tooltip);
                position: absolute;
                top: -36px;
                left: 50%;
                transform: translateX(-50%);
                background: var(--bg-tertiary);
                color: var(--text-primary);
                border: 1px solid var(--border-focus);
                border-radius: 4px;
                padding: 0.25rem 0.5rem;
                font-size: 0.75rem;
                white-space: nowrap;
                opacity: 0;
                pointer-events: none;
                transition: opacity 0.15s;
                transition-delay: 0.3s;
                z-index: 20;
            }}
            [data-tooltip]:hover::after {{ opacity: 1; }}
            [data-tooltip]:focus::after {{ opacity: 1; }}
            .btn-primary {{
                background: var(--accent-primary);
                color: #000000;
                border: 1px solid var(--border-focus);
                padding: 0.5rem 1rem;
                border-radius: 4px;
                cursor: pointer;
                font-size: 0.875rem;
                font-weight: 600;
                transition: transform 0.15s, background 0.15s, opacity 0.2s;
            }}
            .btn-primary:hover {{
                background: var(--accent-hover);
                transform: translateY(-1px);
            }}
            
            /* Main Container */
            .container {{
                max-width: 1400px;
                margin: 0 auto;
                padding: 1.5rem;
            }}
            
            /* Diagnostics Panel */
            .diagnostics-panel {{
                background: var(--bg-secondary);
                border: 1px solid var(--border-color);
                border-radius: 6px;
                margin-bottom: 1.5rem;
            }}
            
            .panel-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 0.75rem 1rem;
                border-bottom: 1px solid var(--border-color);
            }}
            
            .panel-title {{
                font-size: 0.875rem;
                font-weight: 600;
                color: var(--text-primary);
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }}
            
            .diagnostic-summary {{
                display: flex;
                gap: 1rem;
                font-size: 0.75rem;
            }}
            
            .count {{
                padding: 0.25rem 0.5rem;
                border-radius: 4px;
                font-weight: 500;
            }}
            
            .count-error {{
                background: rgba(244, 135, 113, 0.15);
                color: var(--error);
            }}
            
            .count-warning {{
                background: rgba(204, 167, 0, 0.15);
                color: var(--warning);
            }}
            
            .diagnostic-list {{
                max-height: 400px;
                overflow-y: auto;
            }}
            
            .diagnostic-item {{
                display: flex;
                gap: 0.75rem;
                padding: 0.75rem 1rem;
                border-left: 3px solid transparent;
                transition: background 0.15s;
            }}
            
            .diagnostic-item:hover {{
                background: var(--bg-hover);
            }}
            
            .diagnostic-warning {{
                border-left-color: var(--warning);
            }}
            
            .diagnostic-error {{
                border-left-color: var(--error);
            }}
            
            .diagnostic-icon {{
                font-size: 1rem;
                line-height: 1.5;
            }}
            
            .diagnostic-content {{
                flex: 1;
            }}
            
            .diagnostic-title {{
                font-weight: 600;
                font-size: 0.875rem;
                color: var(--text-primary);
                margin-bottom: 0.25rem;
            }}
            
            .diagnostic-message {{
                font-size: 0.8125rem;
                color: var(--text-secondary);
                line-height: 1.5;
                margin-bottom: 0.5rem;
            }}
            
            .diagnostic-action {{
                font-size: 0.8125rem;
                color: var(--info);
            }}
            
            .diagnostic-empty {{
                padding: 2rem;
                text-align: center;
                color: var(--text-secondary);
            }}
            
            .empty-icon {{
                font-size: 3rem;
                color: var(--success);
                margin-bottom: 0.5rem;
            }}
            
            /* Stats Grid */
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 1rem;
                margin-bottom: 1.5rem;
            }}
            
            .stat-card {{
                background: var(--bg-secondary);
                border: 1px solid var(--border-color);
                border-radius: 6px;
                padding: 1rem;
            }}
            
            .stat-label {{
                font-size: 0.75rem;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                color: var(--text-tertiary);
                margin-bottom: 0.5rem;
            }}
            
            .stat-value {{
                font-size: 1.25rem;
                font-weight: 600;
                color: var(--text-primary);
                margin-bottom: 0.25rem;
            }}
            
            .stat-detail {{
                font-size: 0.8125rem;
                color: var(--text-secondary);
                font-family: 'JetBrains Mono', monospace;
            }}
            
            /* Packages Panel */
            .packages-panel {{
                background: var(--bg-secondary);
                border: 1px solid var(--border-color);
                border-radius: 6px;
            }}
            
            .panel-controls {{
                display: flex;
                gap: 0.5rem;
            }}
            
            .search-input {{
                background: var(--bg-tertiary);
                border: 1px solid var(--border-color);
                border-radius: 4px;
                padding: 0.5rem 0.75rem;
                font-size: 0.875rem;
                color: var(--text-primary);
                width: 250px;
            }}
            
            .search-input:focus {{
                outline: none;
                border-color: var(--border-focus);
            }}
            
            .filter-select {{
                background: var(--bg-tertiary);
                border: 1px solid var(--border-color);
                border-radius: 4px;
                padding: 0.5rem 0.75rem;
                font-size: 0.875rem;
                color: var(--text-primary);
                cursor: pointer;
            }}
            
            .table-wrapper {{
                max-height: 500px;
                overflow-y: auto;
            }}
            
            .package-table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 0.875rem;
            }}
            
            .package-table thead {{
                position: sticky;
                top: 0;
                background: var(--bg-tertiary);
                z-index: 10;
            }}
            
            .package-table th {{
                text-align: left;
                padding: 0.75rem 1rem;
                font-weight: 600;
                color: var(--text-secondary);
                text-transform: uppercase;
                font-size: 0.75rem;
                letter-spacing: 0.05em;
                border-bottom: 1px solid var(--border-color);
            }}
            
            .package-table td {{
                padding: 0.75rem 1rem;
                border-bottom: 1px solid var(--border-color);
                color: var(--text-primary);
            }}
            
            .package-table tr:hover {{
                background: var(--bg-hover);
            }}
            
            .pkg-name {{
                font-family: 'JetBrains Mono', monospace;
                font-weight: 500;
            }}
            
            .pkg-version {{
                font-family: 'JetBrains Mono', monospace;
                color: var(--text-secondary);
            }}
            
            .pkg-build {{
                font-family: 'JetBrains Mono', monospace;
                font-size: 0.8125rem;
                color: var(--text-tertiary);
            }}
            
            .badge {{
                display: inline-block;
                padding: 0.125rem 0.5rem;
                border-radius: 3px;
                font-size: 0.75rem;
                font-weight: 600;
                text-transform: uppercase;
            }}
            
            .badge-conda {{
                background: rgba(117, 190, 255, 0.15);
                color: var(--info);
            }}
            
            .badge-pip {{
                background: rgba(204, 167, 0, 0.15);
                color: var(--warning);
            }}
            
            .btn-icon-sm {{
                background: transparent;
                border: none;
                color: var(--text-tertiary);
                cursor: pointer;
                padding: 0.25rem;
                display: flex;
                align-items: center;
                transition: color 0.15s;
            }}
            
            .btn-icon-sm:hover {{
                color: var(--text-primary);
            }}
        </style>
    </head>
    <body>
        <header class="app-header">
            <div class="header-left">
                <span class="app-title">Conda-Lens</span>
                <span class="env-name">{env.name}</span>
                <span class="status-indicator {status_class}">
                    <span class="status-dot"></span>
                    {status_text}
                </span>
                
            </div>
            <div class="header-actions">
                <button class="btn-icon" onclick="refreshData()" title="Refresh">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="23 4 23 10 17 10"></polyline>
                        <polyline points="1 20 1 14 7 14"></polyline>
                        <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
                    </svg>
                </button>
                <select id="env-picker" class="filter-select" aria-label="Environment"></select>
                <button class="btn-secondary" data-tooltip="Copy environment details to clipboard" onclick="copyCardToClipboard()" aria-label="Copy environment details to clipboard">Copy</button>
                <button class="btn-secondary" data-tooltip="Download environment specification file" onclick="downloadCardYAML()" aria-label="Download environment specification file">Download</button>
                <button class="btn-secondary" data-tooltip="Generate migration plan between environments" onclick="location.href='/migration-planner'" aria-label="Generate migration plan between environments">Migration Planner</button>
                <button class="btn-secondary" data-tooltip="Compare selected environments side-by-side" onclick="location.href='/env-compare'" aria-label="Compare selected environments side-by-side">Compare Envs</button>
                <button class="btn-secondary" data-tooltip="Export environment summary as an image" onclick="location.href='/repro-card'" aria-label="Export environment summary as an image">Export Card</button>
            </div>
        </header>
        
        <div class="container">
            <!-- Diagnostics Panel (Top Priority) -->
            <section class="diagnostics-panel">
                <div class="panel-header">
                    <h2 class="panel-title">Diagnostics</h2>
                    <div class="diagnostic-summary">
                        <span class="count count-error">{len(errors)} Errors</span>
                        <span class="count count-warning">{len(warnings)} Warnings</span>
                    </div>
                </div>
                <div class="diagnostic-list">
                    {diagnostic_items_html}
                </div>
            </section>
            
            <!-- Quick Stats -->
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">Packages</div>
                    <div class="stat-value">{len(sorted_packages)}</div>
                    <div class="stat-detail">{conda_count} conda · {pip_count} pip</div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-label">Environment</div>
                    <div class="stat-value">Python {env.python_version}</div>
                    <div class="stat-detail">{env.path}</div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-label">System</div>
                    <div class="stat-value">{env.os_info}</div>
                    <div class="stat-detail">{env.platform_machine} · Conda {conda_ver.replace('conda ', '')}</div>
                </div>
            </div>
            
            <!-- Switch-All Migration -->
            <section class="packages-panel" style="margin-top:1rem;">
                <div class="panel-header">
                    <h2 class="panel-title">Switch-All</h2>
                    <div class="panel-controls">
                        <select class="filter-select" id="target-select" aria-label="Target manager">
                            <option value="conda">conda</option>
                            <option value="pip">pip</option>
                            <option value="uv">uv</option>
                            <option value="pixi">pixi</option>
                        </select>
                        <button id="switch-generate" class="btn-secondary" data-tooltip="Generate migration plan between environments" onclick="loadSwitchAllPlan()" aria-label="Generate migration plan">Generate Migration Plan</button>
                    </div>
                </div>
                <div class="table-wrapper">
                    <table class="package-table" id="switchall-table" style="display:none">
                        <thead>
                            <tr>
                                <th>Package</th>
                                <th>Current</th>
                                <th>Target</th>
                                <th>Version</th>
                                <th>Status</th>
                                <th>Reason</th>
                            </tr>
                        </thead>
                        <tbody id="switchall-body"></tbody>
                    </table>
                </div>
                <div class="stats-grid" id="switchall-summary" style="display:none">
                    <div class="stat-card"><div class="stat-label">Safe</div><div class="stat-value" id="safe-count">0</div></div>
                    <div class="stat-card"><div class="stat-label">Conflicts</div><div class="stat-value" id="conflict-count">0</div></div>
                    <div class="stat-card"><div class="stat-label">Missing</div><div class="stat-value" id="missing-count">0</div></div>
                    <div class="stat-card"><div class="stat-label">Unsupported</div><div class="stat-value" id="unsupported-count">0</div></div>
                    <div class="stat-card"><div class="stat-label">Mode</div><div class="stat-value">Read-only</div><div class="stat-detail">Migration plan is informational only</div></div>
                </div>
            </section>
            
            <!-- Packages Panel -->
            <section class="packages-panel">
                <div class="panel-header">
                    <h2 class="panel-title">Packages</h2>
                    <div class="panel-controls">
                        <input type="text" class="search-input" placeholder="Search packages..." 
                               onkeyup="filterPackages()" id="package-search">
                        <select class="filter-select" onchange="filterPackages()" id="manager-filter">
                            <option value="all">All</option>
                            <option value="conda">Conda only</option>
                            <option value="pip">Pip only</option>
                        </select>
                    </div>
                </div>
                
                <div class="table-wrapper">
                    <table class="package-table">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Version</th>
                                <th>Manager</th>
                                <th>Build</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody id="package-tbody">
                            {package_rows}
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
        
        <pre id="card-yaml" style="display:none">{card_yaml}</pre>
        <!-- Per-package Switch Modal -->
        <div id="switch-modal" style="display:none; position:fixed; inset:0; background: rgba(0,0,0,0.6); align-items:center; justify-content:center; z-index: 1000;">
            <div style="background: var(--bg-secondary); border:1px solid var(--border-color); border-radius:6px; padding:1rem; width: 520px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                    <div style="font-weight:600;">Switch Package</div>
                    <button class="btn-secondary" onclick="closeSwitchModal()">Close</button>
                </div>
                <div style="margin-bottom:0.75rem;">Package: <span id="switch-pkg"></span></div>
                <label for="switch-target-single">Target manager:</label>
                <select id="switch-target-single" class="filter-select" aria-label="Target manager">
                    <option value="conda">conda</option>
                    <option value="pip">pip</option>
                    <option value="uv">uv</option>
                    <option value="pixi">pixi</option>
                </select>
                <div style="margin-top:0.75rem; display:flex; gap:0.5rem;">
                    <button id="switch-generate-single" class="btn-secondary" data-tooltip="Generate migration plan" onclick="runPackagePlan()" aria-label="Generate migration plan">Generate Plan</button>
                </div>
                <div id="switch-result" style="margin-top:0.75rem; color: var(--text-secondary);"></div>
            </div>
        </div>
        <script>
            let switchExecTimer = null;
            let switchExecTimeout = null;
            function loadEnvs() {{
                fetch('/api/environments')
                    .then(r => r.json())
                    .then(list => {{
                        const sel = document.getElementById('env-picker');
                        sel.innerHTML = '';
                        const current = '{env.name}';
                        list.forEach(e => {{
                            const opt = document.createElement('option');
                            opt.value = e.name;
                            opt.textContent = e.name;
                            if (e.name === current) opt.selected = true;
                            sel.appendChild(opt);
                        }});
                        sel.addEventListener('change', () => {{
                            const val = sel.value;
                            const ts = document.getElementById("target-select");
                            if (ts) ts.value = "pip";
                            if (typeof clearMigrationTable === 'function') clearMigrationTable();
                            fetch('/api/preferences/last-env?name=' + encodeURIComponent(val), {{ method: 'POST' }})
                                .then(() => {{
                                    location.href = '/?env=' + encodeURIComponent(val);
                                }});
                        }});
                    }});
            }}
            function fallbackCopy(text) {{
                const ta = document.createElement('textarea');
                ta.value = text;
                ta.setAttribute('readonly', '');
                ta.style.position = 'absolute';
                ta.style.left = '-9999px';
                document.body.appendChild(ta);
                ta.select();
                try {{ document.execCommand('copy'); }} catch (e) {{ console.error('Copy failed', e); }}
                document.body.removeChild(ta);
            }}
            function copyCardToClipboard() {{
                const el = document.getElementById('card-yaml');
                const cardYAML = el ? el.textContent : '';
                if (!cardYAML) {{ console.error('Repro card not available'); return; }}
                if (navigator.clipboard && navigator.clipboard.writeText) {{
                    navigator.clipboard.writeText(cardYAML)
                        .then(() => {{ console.log('Copied repro card'); }})
                        .catch(err => {{ console.warn('Clipboard write failed, using fallback', err); fallbackCopy(cardYAML); }});
                }} else {{
                    fallbackCopy(cardYAML);
                }}
            }}
            window.addEventListener('load', () => {{ loadEnvs(); }});
            function downloadCardYAML() {{
                const cardYAML = document.getElementById('card-yaml').textContent;
                const blob = new Blob([cardYAML], {{ type: 'text/yaml' }});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'repro-card.yaml';
                a.click();
            }}
            // Filter packages by search and manager
            function filterPackages() {{
                const searchQuery = document.getElementById('package-search').value.toLowerCase();
                const managerFilter = document.getElementById('manager-filter').value;
                const rows = document.querySelectorAll('#package-tbody tr');
                
                rows.forEach(row => {{
                    const name = row.dataset.name;
                    const manager = row.dataset.manager;
                    
                    const matchesSearch = name.includes(searchQuery);
                    const matchesManager = managerFilter === 'all' || manager === managerFilter;
                    
                    row.style.display = (matchesSearch && matchesManager) ? '' : 'none';
                }});
            }}
            
            // Copy text to clipboard
            function copyText(text) {{
                navigator.clipboard.writeText(text).then(() => {{
                    console.log('Copied:', text);
                }});
            }}
            
            // Refresh data
            function refreshData() {{
                fetch('/api/refresh')
                    .then(r => r.json())
                    .then(data => {{
                        console.log('Refreshed:', data);
                        location.reload();
                    }});
            }}
            
            // Clear migration table
            function clearMigrationTable() {{
                const tbody = document.getElementById('switchall-body');
                if (tbody) tbody.innerHTML = '';
                const table = document.getElementById('switchall-table');
                if (table) table.style.display = 'none';
                const summary = document.getElementById('switchall-summary');
                if (summary) summary.style.display = 'none';
            }}

            // Switch-All logic
            function loadSwitchAllPlan() {{
                const t = document.getElementById("target-select").value;
                const btn = document.getElementById('switch-generate');
                const sel = document.getElementById('target-select');
                if (btn) {{ btn.disabled = true; btn.textContent = 'Analyzing…'; }}
                if (sel) {{ sel.disabled = true; }}
                fetch(`/api/migration-plan?target=${{t}}`)
                    .then(r => {{ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }})
                    .then(data => {{
                        const tbody = document.getElementById('switchall-body');
                        tbody.innerHTML = '';
                        data.steps.forEach(step => {{
                            const tr = document.createElement('tr');
                            const version = `${{step.current_version}} → ${{step.target_version || 'N/A'}}`;
                            tr.innerHTML = `<td>${{step.package_name}}</td><td>${{step.current_manager}}</td><td>${{step.target_manager}}</td><td>${{version}}</td><td>${{step.safety_status}}</td><td>${{step.reason}}</td>`;
                            tbody.appendChild(tr);
                        }});
                        document.getElementById('switchall-table').style.display = 'table';
                        document.getElementById('switchall-summary').style.display = 'grid';
                        document.getElementById('safe-count').textContent = data.safe_to_migrate;
                        document.getElementById('conflict-count').textContent = data.conflicts;
                        document.getElementById('missing-count').textContent = data.missing;
                        document.getElementById('unsupported-count').textContent = data.unsupported;
                        const s = document.getElementById('switchall-summary');
                        const info = document.createElement('div');
                        info.className = 'stat-card';
                        info.innerHTML = `<div class=\"stat-label\">Note</div><div class=\"stat-value\">Informational</div><div class=\"stat-detail\">No actions are executed</div>`;
                        const cards = s.querySelectorAll('.stat-card .stat-label');
                        if (![...cards].some(el => el.textContent === 'Note')) {{ s.appendChild(info); }}
                        if (btn) {{ btn.disabled = false; btn.textContent = 'Generate Migration Plan'; }}
                        if (sel) {{ sel.disabled = false; }}
                    }})
                    .catch(err => {{
                        showToast('Failed to generate migration plan', false);
                        console.error(err);
                        if (btn) {{ btn.disabled = false; btn.textContent = 'Generate Migration Plan'; }}
                        if (sel) {{ sel.disabled = false; }}
                    }})
                    .finally(() => {{
                        if (btn) {{ btn.disabled = false; btn.textContent = 'Generate Migration Plan'; }}
                        if (sel) {{ sel.disabled = false; }}
                    }});
            }}
            
            
            // Per-package modal
            
            function openSwitchModal(name) {{
                const m = document.getElementById('switch-modal');
                document.getElementById('switch-pkg').textContent = name;
                const div = document.getElementById('switch-result');
                div.innerHTML = 'Loading plan…';
                
                m.style.display = 'flex';
                if (switchExecTimer) {{ clearTimeout(switchExecTimer); switchExecTimer = null; }}
                if (switchExecTimeout) {{ clearTimeout(switchExecTimeout); switchExecTimeout = null; }}
                runPackagePlan();
            }}
            function closeSwitchModal() {{
                document.getElementById('switch-modal').style.display = 'none';
                if (switchExecTimer) {{ clearTimeout(switchExecTimer); switchExecTimer = null; }}
                if (switchExecTimeout) {{ clearTimeout(switchExecTimeout); switchExecTimeout = null; }}
            }}
            function runPackagePlan() {{
                const name = document.getElementById('switch-pkg').textContent;
                const targetSel = document.getElementById('switch-target-single');
                const target = targetSel.value;
                const genBtn = document.getElementById('switch-generate-single');
                const div = document.getElementById('switch-result');
                if (!name) {{ div.textContent = 'No package selected.'; return; }}
                if (genBtn) {{ genBtn.disabled = true; genBtn.textContent = 'Analyzing…'; }}
                if (targetSel) {{ targetSel.disabled = true; }}
                fetch(`/api/package-plan?package=${{encodeURIComponent(name)}}&target=${{target}}`)
                    .then(r=>{{ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }})
                    .then(data=>{{
                        if (!data.steps || !data.steps.length) {{ div.textContent = 'No steps.'; return; }}
                        const s = data.steps[0];
                        div.innerHTML = `Changes:<br>- Manager: ${{s.current_manager}} → ${{s.target_manager}}<br>- Version: ${{s.current_version}} → ${{s.target_version || 'N/A'}}<br>Status: ${{s.safety_status}}<br>Impact: ${{s.reason}}`;
                        div.innerHTML += '<br><em>Migration plan is informational only.</em>';
                        fetch(`/api/deps-graph?package=${{encodeURIComponent(name)}}&target=${{target}}`)
                            .then(r=>{{ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }})
                            .then(g=>{{
                                if (g.blocked_reason) {{
                                    div.innerHTML += `<br>Blocked: ${{g.blocked_reason}}`;
                                }} else if ((g.group_order||[]).length) {{
                                    div.innerHTML += `<br>Group migration: ${{g.group_order.join(' → ')}}`;
                                }}
                                const rev = (g.rev_graph||{{}})[name]||[];
                                const deps = (g.dep_graph||{{}})[name]||[];
                                div.innerHTML += '<br>Dependents: ' + rev.join(', ');
                                div.innerHTML += '<br>Dependencies: ' + deps.join(', ');
                            }})
                            .catch(err => {{ div.innerHTML += '<br>Dependency graph unavailable.'; console.error(err); }});
                    }})
                    .catch(err => {{
                        showToast('Failed to generate plan', false);
                        div.textContent = 'Error generating plan.';
                        console.error(err);
                    }})
                    .finally(() => {{
                        if (genBtn) {{ genBtn.disabled = false; genBtn.textContent = 'Generate Plan'; }}
                        if (targetSel) {{ targetSel.disabled = false; }}
                    }});
            }}
            
            function showToast(text, ok) {{
                let t = document.getElementById('toast');
                if (!t) {{
                    t = document.createElement('div'); t.id = 'toast';
                    t.style.position='fixed'; t.style.top='12px'; t.style.right='12px';
                    t.style.background='var(--bg-tertiary)'; t.style.border='1px solid var(--border-color)';
                    t.style.borderLeft='4px solid ' + (ok ? 'var(--success)' : 'var(--error)');
                    t.style.color='var(--text-primary)'; t.style.padding='0.5rem 0.75rem'; t.style.borderRadius='4px'; t.style.zIndex='2000';
                    document.body.appendChild(t);
                }}
                t.textContent = text; t.style.opacity='1';
                setTimeout(() => {{ t.style.opacity='0'; }}, 2000);
            }}
            
            
            
            // Keyboard shortcuts
            document.addEventListener('keydown', (e) => {{
                // Cmd/Ctrl + K: Focus search
                if ((e.metaKey || e.ctrlKey) && e.key === 'k') {{
                    e.preventDefault();
                    document.getElementById('package-search').focus();
                }}
                // Cmd/Ctrl + R: Refresh
                if ((e.metaKey || e.ctrlKey) && e.key === 'r') {{
                    e.preventDefault();
                    refreshData();
                }}
            }});
        </script>
    </body>
    </html>
    """
    return html

@app.get("/migration-planner", response_class=HTMLResponse)
def migration_planner_page():
    """Migration planner dashboard page."""
    env = get_active_env_info()
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en" data-theme="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Migration Planner - {env.name}</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg-primary: #000000;
                --bg-secondary: #0a0a0a;
                --bg-tertiary: #141414;
                --bg-hover: #1a1a1a;
                --error: #ff5555;
                --warning: #ffff55;
                --success: #55ff55;
                --info: #55ffff;
                --text-primary: #ffffff;
                --text-secondary: #e0e0e0;
                --text-tertiary: #c0c0c0;
                --border-color: #333333;
                --border-focus: #007BFF;
                --accent-primary: #55ffff;
                --accent-hover: #33dddd;
            }}
            
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            
            body {{
                font-family: 'Inter', sans-serif;
                background: var(--bg-primary);
                color: var(--text-primary);
                line-height: 1.5;
            }}
            
            .app-header {{
                background: var(--bg-secondary);
                border-bottom: 1px solid var(--border-color);
                padding: 0.75rem 1.5rem;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            
            .header-left {{ display: flex; align-items: center; gap: 1.5rem; }}
            .app-title {{ font-weight: 600; font-size: 1rem; }}
            .nav a {{ color: #007BFF; text-decoration: none; }}
            .nav a:hover {{ text-decoration: underline; }}
            
            .container {{ max-width: 1400px; margin: 0 auto; padding: 1.5rem; }}
            
            .controls {{
                background: var(--bg-secondary);
                border: 1px solid var(--border-color);
                border-radius: 6px;
                padding: 1rem;
                margin-bottom: 1.5rem;
                display: flex;
                gap: 1rem;
                align-items: center;
            }}
            
            .controls label {{ font-size: 0.875rem; font-weight: 600; }}
            
            .controls select {{
                background: var(--bg-tertiary);
                border: 1px solid var(--border-color);
                border-radius: 4px;
                padding: 0.5rem 0.75rem;
                color: var(--text-primary);
                font-size: 0.875rem;
            }}
            
            .btn-primary {{
                background: var(--accent-primary);
                color: #000;
                border: none;
                padding: 0.5rem 1rem;
                border-radius: 4px;
                font-weight: 600;
                cursor: pointer;
                font-size: 0.875rem;
            }}
            
            .btn-primary:hover {{ background: var(--accent-hover); }}
            
            .summary {{
                background: var(--bg-secondary);
                border: 1px solid var(--border-color);
                border-radius: 6px;
                padding: 1rem;
                margin-bottom: 1.5rem;
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 1rem;
            }}
            
            .summary-item {{ text-align: center; }}
            .summary-label {{ font-size: 0.75rem; color: var(--text-tertiary); text-transform: uppercase; }}
            .summary-value {{ font-size: 1.5rem; font-weight: 600; margin-top: 0.25rem; }}
            
            .panel {{
                background: var(--bg-secondary);
                border: 1px solid var(--border-color);
                border-radius: 6px;
            }}
            
            .panel-header {{
                padding: 0.75rem 1rem;
                border-bottom: 1px solid var(--border-color);
                font-size: 0.875rem;
                font-weight: 600;
                text-transform: uppercase;
            }}
            
            .table-wrapper {{ max-height: 600px; overflow-y: auto; }}
            
            table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 0.875rem;
            }}
            
            thead {{
                position: sticky;
                top: 0;
                background: var(--bg-tertiary);
                z-index: 10;
            }}
            
            th {{
                text-align: left;
                padding: 0.75rem 1rem;
                font-weight: 600;
                color: var(--text-secondary);
                text-transform: uppercase;
                font-size: 0.75rem;
                border-bottom: 1px solid var(--border-color);
            }}
            
            td {{
                padding: 0.75rem 1rem;
                border-bottom: 1px solid var(--border-color);
            }}
            
            tr:hover {{ background: var(--bg-hover); }}
            
            .pkg-name {{ font-family: 'JetBrains Mono', monospace; font-weight: 500; }}
            .pkg-version {{ font-family: 'JetBrains Mono', monospace; color: var(--text-secondary); }}
            
            .status-ok {{ color: var(--success); }}
            .status-conflict {{ color: var(--warning); }}
            .status-missing {{ color: var(--error); }}
            
            .loading {{ text-align: center; padding: 2rem; color: var(--text-secondary); }}
        </style>
    </head>
    <body>
        <header class="app-header">
            <div class="header-left">
                <span class="app-title">Conda-Lens Migration Planner</span>
                <nav class="nav">
                    <a href="/">Back to Dashboard</a>
                </nav>
            </div>
        </header>
        
        <div class="container">
            <div class="controls">
                <label for="target-manager">Target Manager:</label>
                <select id="target-select" onchange="loadMigrationPlan()">
                    <option value="conda">conda</option>
                    <option value="pip">pip</option>
                    <option value="uv">uv</option>
                    <option value="pixi">pixi</option>
                </select>
                <button class="btn-primary" onclick="loadMigrationPlan()">Analyze</button>
                <div id="progress" style="display:none; align-items:center; gap:0.75rem; margin-left:auto;">
                    <div class="progress-bar" style="position:relative; width:300px; height:8px; background: var(--bg-tertiary); border:1px solid var(--border-color); border-radius:999px; overflow:hidden;"><div id="progress-fill" style="height:100%; width:0%; background: var(--accent-primary); transition: width 0.2s ease;"></div></div>
                    <div id="progress-text" style="font-size:0.8125rem; color: var(--text-secondary);">0% • 0s • ETA --</div>
                </div>
            </div>
            
            <div class="summary" id="summary" style="display: none;">
                <div class="summary-item">
                    <div class="summary-label">Total Packages</div>
                    <div class="summary-value" id="total">0</div>
                </div>
                <div class="summary-item">
                    <div class="summary-label">Safe to Migrate</div>
                    <div class="summary-value status-ok" id="safe">0</div>
                </div>
                <div class="summary-item">
                    <div class="summary-label">Conflicts</div>
                    <div class="summary-value status-conflict" id="conflicts">0</div>
                </div>
                <div class="summary-item">
                    <div class="summary-label">Missing</div>
                    <div class="summary-value status-missing" id="missing">0</div>
                </div>
            </div>
            
            <div class="panel">
                <div class="panel-header">Migration Plan</div>
                <div class="table-wrapper">
                    <div class="loading" id="loading">Select a target manager and click Analyze</div>
                    <table id="migration-table" style="display: none;">
                        <thead>
                            <tr>
                                <th>Package</th>
                                <th>Current</th>
                                <th>Target</th>
                                <th>Version</th>
                                <th>Status</th>
                                <th>Reason</th>
                            </tr>
                        </thead>
                        <tbody id="migration-tbody"></tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <script>
            function loadMigrationPlan() {{
                const t = document.getElementById("target-select").value;
                const loading = document.getElementById('loading');
                const table = document.getElementById('migration-table');
                const summary = document.getElementById('summary');
                const progress = document.getElementById('progress');
                const progressFill = document.getElementById('progress-fill');
                const progressText = document.getElementById('progress-text');
                
                loading.style.display = 'block';
                loading.textContent = 'Analyzing migration...';
                table.style.display = 'none';
                summary.style.display = 'none';
                progress.style.display = 'flex';
                let percent = 0;
                let start = Date.now();
                let timer = setInterval(() => {{
                    const elapsed = Math.floor((Date.now() - start) / 1000);
                    percent = Math.min(percent + 3, 90);
                    const eta = percent > 0 ? Math.max(0, Math.floor(elapsed * (100 / percent - 1))) : 0;
                    progressFill.style.width = percent + '%';
                    progressText.textContent = percent + '% • ' + elapsed + 's • ETA ' + (eta > 0 ? eta + 's' : '--');
                }}, 200);
                
                fetch(`/api/migration-plan?target=${{t}}`)
                    .then(r => {{ if (!r.ok) {{ return r.json().then(err => {{ throw new Error(err.message || ('HTTP ' + r.status)); }}); }} return r.json(); }})
                    .then(data => {{
                        // Update summary
                        document.getElementById('total').textContent = data.total_packages;
                        document.getElementById('safe').textContent = data.safe_to_migrate;
                        document.getElementById('conflicts').textContent = data.conflicts;
                        document.getElementById('missing').textContent = data.missing;
                        summary.style.display = 'grid';
                        
                        // Update table
                        const tbody = document.getElementById('migration-tbody');
                        tbody.innerHTML = '';
                        
                        data.steps.forEach(step => {{
                            const row = tbody.insertRow();
                            
                            // Package name
                            const cellName = row.insertCell();
                            cellName.className = 'pkg-name';
                            cellName.textContent = step.package_name;
                            
                            // Current manager
                            row.insertCell().textContent = step.current_manager;
                            
                            // Target manager
                            row.insertCell().textContent = step.target_manager;
                            
                            // Version
                            const cellVersion = row.insertCell();
                            cellVersion.className = 'pkg-version';
                            cellVersion.textContent = `${{step.current_version}} → ${{step.target_version || 'N/A'}}`;
                            
                        // Status
                        const cellStatus = row.insertCell();
                        if (step.safety_status === 'OK') {{
                            cellStatus.className = 'status-ok';
                            cellStatus.textContent = 'OK';
                        }} else if (step.safety_status === 'Conflict') {{
                            cellStatus.className = 'status-conflict';
                            cellStatus.textContent = 'Conflict';
                        }} else if (step.safety_status === 'Missing') {{
                            cellStatus.className = 'status-missing';
                            cellStatus.textContent = 'Missing';
                        }} else {{
                            cellStatus.className = 'status-conflict';
                            cellStatus.textContent = step.safety_status;
                        }}
                            
                            // Reason
                            const cellReason = row.insertCell();
                            cellReason.style.color = 'var(--text-secondary)';
                            cellReason.textContent = step.reason;
                        }});
                        
                        loading.style.display = 'none';
                        table.style.display = 'table';
                        progressFill.style.width = '100%';
                        const elapsed = Math.floor((Date.now() - start) / 1000);
                        progressText.textContent = '100% • ' + elapsed + 's • ETA 0s';
                        setTimeout(() => {{
                            progress.style.display = 'none';
                            clearInterval(timer);
                        }}, 500);
                    }})
                    .catch(err => {{
                        loading.textContent = 'Error loading migration plan: ' + (err && err.message ? err.message : 'unknown error');
                        console.error(err);
                    }})
                    .finally(() => {{
                        try {{ clearInterval(timer); }} catch (e) {{}}
                        progress.style.display = 'none';
                    }});
            }}
        </script>
    </body>
    </html>
    """
    return html

@app.get("/env-compare", response_class=HTMLResponse)
def env_compare_page():
    html = f"""
    <!DOCTYPE html>
    <html lang="en" data-theme="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Environment Comparison</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg-primary: #000000;
                --bg-secondary: #0a0a0a;
                --bg-tertiary: #141414;
                --bg-hover: #1a1a1a;
                --error: #ff5555;
                --warning: #ffff55;
                --success: #55ff55;
                --info: #55ffff;
                --text-primary: #ffffff;
                --text-secondary: #e0e0e0;
                --text-tertiary: #c0c0c0;
                --border-color: #333333;
                --border-focus: #007BFF;
                --accent-primary: #55ffff;
                --accent-hover: #33dddd;
            }}
            body {{ font-family: 'Inter', sans-serif; background: var(--bg-primary); color: var(--text-primary); }}
            .app-header {{ background: var(--bg-secondary); border-bottom: 1px solid var(--border-color); padding: 0.75rem 1.5rem; display:flex; justify-content:space-between; align-items:center; }}
            .container {{ max-width: 1400px; margin: 0 auto; padding: 1.5rem; }}
            .controls {{ background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: 6px; padding: 1rem; margin-bottom: 1.5rem; display:flex; flex-wrap: wrap; gap:1rem; align-items:center; }}
            .btn-primary {{ background: var(--accent-primary); color:#000; border:none; padding:0.5rem 1rem; border-radius:4px; font-weight:600; cursor:pointer; }}
            .btn-primary:hover {{ background: var(--accent-hover); }}
            .nav a {{ color: #007BFF; text-decoration: none; }}
            .nav a:hover {{ text-decoration: underline; }}
            [data-tooltip] {{ position: relative; }}
            [data-tooltip]::after {{
                content: attr(data-tooltip);
                position: absolute;
                top: -36px;
                left: 50%;
                transform: translateX(-50%);
                background: var(--bg-tertiary);
                color: var(--text-primary);
                border: 1px solid var(--border-focus);
                border-radius: 4px;
                padding: 0.25rem 0.5rem;
                font-size: 0.75rem;
                white-space: nowrap;
                opacity: 0;
                pointer-events: none;
                transition: opacity 0.15s;
                transition-delay: 0.3s;
                z-index: 20;
            }}
            [data-tooltip]:hover::after {{ opacity: 1; }}
            @media (max-width: 768px) {{
                .container {{ padding: 0.75rem; }}
                .controls {{ gap: 0.5rem; }}
                table {{ font-size: 0.8125rem; }}
                th, td {{ padding: 0.5rem 0.75rem; }}
            }}
            .panel {{ background: var(--bg-secondary); border:1px solid var(--border-color); border-radius:6px; }}
            .panel-header {{ padding:0.75rem 1rem; border-bottom:1px solid var(--border-color); font-size:0.875rem; font-weight:600; text-transform:uppercase; }}
            .table-wrapper {{ max-height: 500px; overflow-y:auto; }}
            table {{ width:100%; border-collapse:collapse; font-size:0.875rem; }}
            th, td {{ padding:0.75rem 1rem; border-bottom:1px solid var(--border-color); }}
            thead {{ position:sticky; top:0; background: var(--bg-tertiary); }}
        </style>
    </head>
    <body>
        <header class="app-header">
            <div class="header-left">
                <span class="app-title">Conda-Lens Environment Comparison</span>
                <nav class="nav"><a href="/" aria-label="Back to Dashboard">Back to Dashboard</a></nav>
            </div>
        </header>
        <div class="container">
            <div class="controls">
                <label>A:</label>
                <select id="env-a"></select>
                <label>B:</label>
                <select id="env-b"></select>
                <button class="btn-primary" data-tooltip="Compare selected environments side-by-side" aria-label="Compare selected environments side-by-side" onclick="runCompare()">Analyze</button>
                <button class="btn-primary" data-tooltip="Download environment specification file" aria-label="Download environment specification file" onclick="exportCompare('yaml')">Export YAML</button>
                <button class="btn-primary" data-tooltip="Download environment specification file" aria-label="Download environment specification file" onclick="exportCompare('json')">Export JSON</button>
            </div>
            <div class="panel">
                <div class="panel-header">Summary</div>
                <div class="table-wrapper">
                    <table>
                        <thead><tr><th>Metric</th><th>Value</th></tr></thead>
                        <tbody id="summary-body"></tbody>
                    </table>
                </div>
            </div>
            <div class="panel" style="margin-top:1rem;">
                <div class="panel-header">Version Mismatches</div>
                <div class="table-wrapper">
                    <table>
                        <thead><tr><th>Package</th><th>A Version</th><th>B Version</th></tr></thead>
                        <tbody id="mismatch-body"></tbody>
                    </table>
                </div>
            </div>
            <div class="panel" style="margin-top:1rem;">
                <div class="panel-header">Missing In A</div>
                <div class="table-wrapper">
                    <table>
                        <thead><tr><th>Package</th></tr></thead>
                        <tbody id="missing-a-body"></tbody>
                    </table>
                </div>
            </div>
            <div class="panel" style="margin-top:1rem;">
                <div class="panel-header">Missing In B</div>
                <div class="table-wrapper">
                    <table>
                        <thead><tr><th>Package</th></tr></thead>
                        <tbody id="missing-b-body"></tbody>
                    </table>
                </div>
            </div>
        </div>
        <script>
            function loadEnvOptions() {{
                fetch('/api/environments').then(r=>r.json()).then(list=>{{
                    const a = document.getElementById('env-a');
                    const b = document.getElementById('env-b');
                    a.innerHTML = ''; b.innerHTML='';
                    list.forEach(e=>{{
                        const oa = document.createElement('option'); oa.value = e.name; oa.textContent = e.name; a.appendChild(oa);
                        const ob = document.createElement('option'); ob.value = e.name; ob.textContent = e.name; b.appendChild(ob);
                    }});
                }});
            }}
            function runCompare() {{
                const a = document.getElementById('env-a').value;
                const b = document.getElementById('env-b').value;
                fetch(`/api/compare?envA=${{encodeURIComponent(a)}}&envB=${{encodeURIComponent(b)}}`)
                    .then(r=>r.json())
                    .then(data=>{{
                        window._lastCompare = data;
                        const sb = document.getElementById('summary-body');
                        sb.innerHTML = '';
                        const rows = [
                            ['Env A', data.envA],
                            ['Env B', data.envB],
                            ['Packages A', data.countA],
                            ['Packages B', data.countB],
                            ['Mismatches', data.version_mismatches.length],
                            ['Missing in A', data.only_in_b.length],
                            ['Missing in B', data.only_in_a.length],
                        ];
                        rows.forEach(r=>{{ const tr = document.createElement('tr'); tr.innerHTML = `<td>${{r[0]}}</td><td>${{r[1]}}</td>`; sb.appendChild(tr); }});
                        const mb = document.getElementById('mismatch-body'); mb.innerHTML='';
                        data.version_mismatches.forEach(m=>{{ const tr = document.createElement('tr'); tr.innerHTML = `<td>${{m.name}}</td><td>${{m.a_version}}</td><td>${{m.b_version}}</td>`; mb.appendChild(tr); }});
                        const ma = document.getElementById('missing-a-body'); ma.innerHTML='';
                        data.only_in_b.forEach(n=>{{ const tr = document.createElement('tr'); tr.innerHTML = `<td>${{n}}</td>`; ma.appendChild(tr); }});
                        const mbb = document.getElementById('missing-b-body'); mbb.innerHTML='';
                        data.only_in_a.forEach(n=>{{ const tr = document.createElement('tr'); tr.innerHTML = `<td>${{n}}</td>`; mbb.appendChild(tr); }});
                    }});
            }}
            function exportCompare(fmt) {{
                const data = window._lastCompare || {{}};
                let text = '';
                if (fmt === 'json') {{ text = JSON.stringify(data, null, 2); }}
                else {{ text = `envA: ${{data.envA}}\nenvB: ${{data.envB}}\ncountA: ${{data.countA}}\ncountB: ${{data.countB}}\nversion_mismatches:` + (data.version_mismatches||[]).map(m=>`\n  - name: ${{m.name}}\n    a_version: ${{m.a_version}}\n    b_version: ${{m.b_version}}`).join('') + `\nonly_in_a:` + (data.only_in_a||[]).map(n=>`\n  - ${{n}}`).join('') + `\nonly_in_b:` + (data.only_in_b||[]).map(n=>`\n  - ${{n}}`).join(''); }}
                const blob = new Blob([text], {{ type: 'text/' + (fmt==='json' ? 'json' : 'yaml') }});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url; a.download = 'env-compare.' + (fmt==='json'?'json':'yaml'); a.click();
            }}
            window.addEventListener('load', loadEnvOptions);
        </script>
    </body>
    </html>
    """
    return html

@app.get("/api/compare")
def api_compare(envA: str, envB: str):
    a = get_env_info_by_name(envA)
    b = get_env_info_by_name(envB)
    a_pkgs = a.packages
    b_pkgs = b.packages
    only_in_a = sorted([n for n in a_pkgs.keys() if n not in b_pkgs])
    only_in_b = sorted([n for n in b_pkgs.keys() if n not in a_pkgs])
    mismatches = []
    for n in a_pkgs.keys() & b_pkgs.keys():
        # packages is Dict[str, List[PackageDetails]], so get first package
        av = a_pkgs[n][0].version
        bv = b_pkgs[n][0].version
        if av != bv:
            mismatches.append({"name": n, "a_version": av, "b_version": bv})
    result = {
        "envA": a.name,
        "envB": b.name,
        "countA": len(a_pkgs),
        "countB": len(b_pkgs),
        "version_mismatches": sorted(mismatches, key=lambda m: m["name"]),
        "only_in_a": only_in_a,
        "only_in_b": only_in_b,
    }
    return JSONResponse(result)

@app.get("/api/deps-graph")
def api_deps_graph(package: str = None, target: str = "conda", limit: int = 50):
    from .migration import MigrationPlanner
    env = get_active_env_info()
    planner = MigrationPlanner(env)
    dep_graph = planner._build_dependency_graph()
    rev_graph = planner._build_reverse_dependency_graph(dep_graph)
    group = []
    blocked = None
    order = []
    if package:
        ok, ord_list, reason = planner._check_dependents(package, target, None, dep_graph, rev_graph)
        blocked = None if ok else (reason or "Blocked by dependency chain")
        group = ord_list
        order = ord_list
    else:
        names = sorted(list(dep_graph.keys()))[:max(1, limit)]
        order = planner._toposort(names, dep_graph)
    return JSONResponse({
        "dep_graph": dep_graph,
        "rev_graph": rev_graph,
        "group_order": order,
        "blocked_reason": blocked
    })
def start_server(port: int = 8000):
    import uvicorn
    chosen = pick_port(port)
    print(f"Starting web UI at http://127.0.0.1:{chosen}")
    try:
        config = uvicorn.Config(app=app, host="127.0.0.1", port=chosen, log_level="info")
        server = uvicorn.Server(config)
        server.run()
    except KeyboardInterrupt:
        print("Server stopped")
def _prefs_path() -> Path:
    return Path.home() / ".conda-lens" / "prefs.json"

def _load_prefs() -> dict:
    try:
        p = _prefs_path()
        if not p.exists():
            return {}
        return json.loads(p.read_text())
    except Exception:
        return {}

def _save_prefs(data: dict):
    try:
        p = _prefs_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data))
    except Exception:
        pass
# startup event replaced by lifespan handler above
@app.get("/api/cache-refresh")
async def api_cache_refresh():
    try:
        loop = asyncio.get_event_loop()
        from .cache import refresh_cache
        await loop.run_in_executor(None, lambda: refresh_cache(incremental=True))
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

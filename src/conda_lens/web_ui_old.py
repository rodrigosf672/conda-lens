from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import subprocess
import yaml
from .env_inspect import get_active_env_info
from .diagnostics import run_diagnostics
from .repro_card import generate_repro_card

app = FastAPI()

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
    
    return JSONResponse({
        "env_name": env.name,
        "python_version": env.python_version,
        "package_count": len(env.packages),
        "diagnostics_count": len(results),
        "has_errors": any(r.severity == "ERROR" for r in results),
        "timestamp": __import__('datetime').datetime.now().isoformat()
    })

@app.get("/repro-card", response_class=HTMLResponse)
def repro_card_viewer():
    """View the reproducibility card."""
    env = get_active_env_info()
    card = generate_repro_card(env)
    card_yaml = yaml.dump(card, sort_keys=False)
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Repro Card - {env.name}</title>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono&display=swap" rel="stylesheet">
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{
                    font-family: 'Inter', sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    padding: 2rem;
                }}
                
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                }}
                
                .header {{
                    background: rgba(255, 255, 255, 0.95);
                    backdrop-filter: blur(10px);
                    border-radius: 16px;
                    padding: 2rem;
                    margin-bottom: 2rem;
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
                }}
                
                h1 {{
                    font-size: 2rem;
                    font-weight: 700;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    margin-bottom: 0.5rem;
                }}
                
                .nav {{
                    margin-top: 1rem;
                }}
                
                .nav a {{
                    color: #667eea;
                    text-decoration: none;
                    font-weight: 500;
                }}
                
                .nav a:hover {{
                    text-decoration: underline;
                }}
                
                .card {{
                    background: white;
                    border-radius: 12px;
                    padding: 2rem;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
                }}
                
                pre {{
                    background: #1e293b;
                    color: #e2e8f0;
                    padding: 1.5rem;
                    border-radius: 8px;
                    overflow-x: auto;
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 0.875rem;
                    line-height: 1.6;
                }}
                
                .actions {{
                    margin-top: 1rem;
                    display: flex;
                    gap: 1rem;
                }}
                
                button {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border: none;
                    padding: 0.75rem 1.5rem;
                    border-radius: 8px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: transform 0.2s;
                }}
                
                button:hover {{
                    transform: translateY(-2px);
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📄 Reproducibility Card</h1>
                    <div class="nav">
                        <a href="/">← Back to Dashboard</a>
                    </div>
                </div>
                
                <div class="card">
                    <pre>{card_yaml}</pre>
                    <div class="actions">
                        <button onclick="copyToClipboard()">📋 Copy to Clipboard</button>
                        <button onclick="downloadYAML()">💾 Download YAML</button>
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
def read_root():
    env = get_active_env_info()
    results = run_diagnostics(env)
    conda_ver = get_conda_version()
    pip_ver = get_pip_version()
    
    # Sort packages by name
    sorted_packages = sorted(env.packages.values(), key=lambda p: p.name.lower())
    
    # Build package table rows with zebra stripes
    package_rows = ""
    for idx, pkg in enumerate(sorted_packages):
        row_class = "even" if idx % 2 == 0 else "odd"
        package_rows += f"""
        <tr class="{row_class}">
            <td>{pkg.name}</td>
            <td>{pkg.version}</td>
            <td><span class="badge badge-{pkg.manager}">{pkg.manager}</span></td>
            <td class="build-info">{pkg.build}</td>
        </tr>
        """
    
    # Group diagnostics by severity
    errors = [r for r in results if r.severity == "ERROR"]
    warnings = [r for r in results if r.severity == "WARNING"]
    
    diagnostics_html = ""
    if not results:
        diagnostics_html = "<div class='alert alert-success'>✅ No issues found! Your environment looks healthy.</div>"
    else:
        if errors:
            diagnostics_html += "<h4 style='color: #991b1b; margin-bottom: 0.5rem;'>🔴 Errors</h4>"
            for res in errors:
                diagnostics_html += f"""
                <div class='alert alert-danger'>
                    <h5>{res.rule_name}</h5>
                    <p>{res.message}</p>
                    <p><strong>Suggestion:</strong> {res.suggestion}</p>
                </div>
                """
        
        if warnings:
            diagnostics_html += "<h4 style='color: #92400e; margin-top: 1rem; margin-bottom: 0.5rem;'>⚠️ Warnings</h4>"
            for res in warnings:
                diagnostics_html += f"""
                <div class='alert alert-warning'>
                    <h5>{res.rule_name}</h5>
                    <p>{res.message}</p>
                    <p><strong>Suggestion:</strong> {res.suggestion}</p>
                </div>
                """
    
    # GPU info section
    gpu_html = ""
    if env.gpu_info:
        gpu_html = "<div class='metadata-section'><h3>🎮 GPU Information</h3><div class='metadata-grid'>"
        for gpu in env.gpu_info:
            gpu_html += f"""
            <div class='metadata-item'>
                <span class='label'>GPU {gpu['index']}</span>
                <span class='value'>{gpu['name']} ({int(gpu['total_memory_mb'])} MB)</span>
            </div>
            """
        gpu_html += "</div></div>"
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Conda-Lens Dashboard - {env.name}</title>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{
                    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    padding: 2rem;
                    color: #1a202c;
                }}
                
                .container {{
                    max-width: 1400px;
                    margin: 0 auto;
                }}
                
                .header {{
                    background: rgba(255, 255, 255, 0.95);
                    backdrop-filter: blur(10px);
                    border-radius: 16px;
                    padding: 2rem;
                    margin-bottom: 2rem;
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    flex-wrap: wrap;
                    gap: 1rem;
                }}
                
                .header-left {{
                    flex: 1;
                }}
                
                .header-right {{
                    display: flex;
                    gap: 1rem;
                }}
                
                h1 {{
                    font-size: 2.5rem;
                    font-weight: 700;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    margin-bottom: 0.5rem;
                }}
                
                .env-name {{
                    font-size: 1.5rem;
                    color: #4a5568;
                    font-weight: 600;
                    margin-bottom: 1rem;
                }}
                
                .btn {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border: none;
                    padding: 0.75rem 1.5rem;
                    border-radius: 8px;
                    font-weight: 600;
                    cursor: pointer;
                    text-decoration: none;
                    display: inline-block;
                    transition: transform 0.2s;
                }}
                
                .btn:hover {{
                    transform: translateY(-2px);
                }}
                
                .btn-secondary {{
                    background: white;
                    color: #667eea;
                    border: 2px solid #667eea;
                }}
                
                .metadata-section {{
                    background: white;
                    border-radius: 12px;
                    padding: 1.5rem;
                    margin-bottom: 2rem;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
                }}
                
                .metadata-section h3 {{
                    font-size: 1.25rem;
                    font-weight: 600;
                    margin-bottom: 1rem;
                    color: #2d3748;
                }}
                
                .metadata-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 1rem;
                }}
                
                .metadata-item {{
                    display: flex;
                    flex-direction: column;
                    gap: 0.25rem;
                }}
                
                .metadata-item .label {{
                    font-size: 0.875rem;
                    color: #718096;
                    font-weight: 500;
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                }}
                
                .metadata-item .value {{
                    font-size: 1rem;
                    color: #2d3748;
                    font-weight: 600;
                }}
                
                .alert {{
                    padding: 1rem 1.5rem;
                    border-radius: 8px;
                    margin-bottom: 1rem;
                    border-left: 4px solid;
                }}
                
                .alert h5 {{
                    font-size: 1rem;
                    font-weight: 600;
                    margin-bottom: 0.5rem;
                }}
                
                .alert p {{
                    margin-bottom: 0.5rem;
                    line-height: 1.6;
                    font-size: 0.9375rem;
                }}
                
                .alert-success {{
                    background: #f0fdf4;
                    border-color: #22c55e;
                    color: #166534;
                }}
                
                .alert-warning {{
                    background: #fffbeb;
                    border-color: #f59e0b;
                    color: #92400e;
                }}
                
                .alert-danger {{
                    background: #fef2f2;
                    border-color: #ef4444;
                    color: #991b1b;
                }}
                
                .table-container {{
                    background: white;
                    border-radius: 12px;
                    overflow: hidden;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
                    border: 1px solid #e2e8f0;
                }}
                
                .table-header {{
                    padding: 1.5rem;
                    border-bottom: 2px solid #e2e8f0;
                }}
                
                .table-header h3 {{
                    font-size: 1.25rem;
                    font-weight: 600;
                    color: #2d3748;
                }}
                
                .table-header .count {{
                    font-size: 0.875rem;
                    color: #718096;
                    margin-top: 0.25rem;
                }}
                
                .table-wrapper {{
                    max-height: 600px;
                    overflow-y: auto;
                }}
                
                table {{
                    width: 100%;
                    border-collapse: collapse;
                }}
                
                thead {{
                    background: #f7fafc;
                    position: sticky;
                    top: 0;
                    z-index: 10;
                }}
                
                th {{
                    padding: 1rem 1.5rem;
                    text-align: left;
                    font-size: 0.875rem;
                    font-weight: 600;
                    color: #4a5568;
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                    border-bottom: 2px solid #e2e8f0;
                }}
                
                td {{
                    padding: 1rem 1.5rem;
                    border-bottom: 1px solid #f1f5f9;
                    font-size: 0.9375rem;
                }}
                
                tr.even {{
                    background: #ffffff;
                }}
                
                tr.odd {{
                    background: #f8fafc;
                }}
                
                tr:hover {{
                    background: #eef2ff !important;
                }}
                
                .badge {{
                    display: inline-block;
                    padding: 0.25rem 0.75rem;
                    border-radius: 9999px;
                    font-size: 0.75rem;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                }}
                
                .badge-conda {{
                    background: #dbeafe;
                    color: #1e40af;
                }}
                
                .badge-pip {{
                    background: #fef3c7;
                    color: #92400e;
                }}
                
                .build-info {{
                    color: #64748b;
                    font-size: 0.875rem;
                    font-family: 'Monaco', 'Courier New', monospace;
                }}
                
                .refresh-indicator {{
                    display: inline-block;
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                    background: #22c55e;
                    margin-right: 0.5rem;
                    animation: pulse 2s infinite;
                }}
                
                @keyframes pulse {{
                    0%, 100% {{ opacity: 1; }}
                    50% {{ opacity: 0.5; }}
                }}
                
                @media (max-width: 768px) {{
                    body {{
                        padding: 1rem;
                    }}
                    
                    h1 {{
                        font-size: 2rem;
                    }}
                    
                    .header {{
                        flex-direction: column;
                        align-items: flex-start;
                    }}
                    
                    .metadata-grid {{
                        grid-template-columns: 1fr;
                    }}
                    
                    table {{
                        font-size: 0.875rem;
                    }}
                    
                    th, td {{
                        padding: 0.75rem 1rem;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="header-left">
                        <h1>🔬 Conda-Lens Dashboard</h1>
                        <div class="env-name">
                            <span class="refresh-indicator"></span>
                            Environment: {env.name}
                        </div>
                    </div>
                    <div class="header-right">
                        <button class="btn" onclick="refreshData()">🔄 Refresh</button>
                        <a href="/repro-card" class="btn btn-secondary">📄 View Repro Card</a>
                    </div>
                </div>
                
                <div class="metadata-section">
                    <h3>📊 Environment Metadata</h3>
                    <div class="metadata-grid">
                        <div class="metadata-item">
                            <span class="label">Environment Path</span>
                            <span class="value">{env.path}</span>
                        </div>
                        <div class="metadata-item">
                            <span class="label">Python Version</span>
                            <span class="value">{env.python_version}</span>
                        </div>
                        <div class="metadata-item">
                            <span class="label">Platform</span>
                            <span class="value">{env.platform_machine}</span>
                        </div>
                        <div class="metadata-item">
                            <span class="label">OS</span>
                            <span class="value">{env.os_info}</span>
                        </div>
                        <div class="metadata-item">
                            <span class="label">Conda Version</span>
                            <span class="value">{conda_ver}</span>
                        </div>
                        <div class="metadata-item">
                            <span class="label">Pip Version</span>
                            <span class="value">{pip_ver}</span>
                        </div>
                        {f'''<div class="metadata-item">
                            <span class="label">CUDA Driver</span>
                            <span class="value">{env.cuda_driver_version}</span>
                        </div>''' if env.cuda_driver_version else ''}
                    </div>
                </div>
                
                {gpu_html}
                
                <div class="metadata-section">
                    <h3>🔍 Diagnostics</h3>
                    {diagnostics_html}
                </div>
                
                <div class="table-container">
                    <div class="table-header">
                        <h3>📦 Installed Packages</h3>
                        <div class="count">{len(sorted_packages)} packages installed</div>
                    </div>
                    <div class="table-wrapper">
                        <table>
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Version</th>
                                    <th>Manager</th>
                                    <th>Build</th>
                                </tr>
                            </thead>
                            <tbody>
                                {package_rows}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            
            <script>
                function refreshData() {{
                    fetch('/api/refresh')
                        .then(response => response.json())
                        .then(data => {{
                            console.log('Refreshed:', data);
                            location.reload();
                        }})
                        .catch(error => {{
                            console.error('Refresh failed:', error);
                            alert('Failed to refresh data');
                        }});
                }}
                
                // Optional: Auto-refresh every 30 seconds
                // setInterval(refreshData, 30000);
            </script>
        </body>
    </html>
    """
    return html

def start_server(port: int = 8000):
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=port)

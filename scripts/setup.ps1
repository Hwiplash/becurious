$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$WorkspaceRoot = Split-Path -Parent $ProjectRoot
$Python = Join-Path $WorkspaceRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    python -m venv (Join-Path $WorkspaceRoot ".venv")
}

& $Python -m pip install -r (Join-Path $ProjectRoot "requirements.txt")

$EnvFile = Join-Path $ProjectRoot ".env"
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $ProjectRoot ".env.example") $EnvFile
    Write-Host "Created .env. Add OPENAI_API_KEY before using the AI agent."
}

New-Item -ItemType Directory -Force (Join-Path $ProjectRoot "data\raw") | Out-Null
New-Item -ItemType Directory -Force (Join-Path $ProjectRoot "data\pdfs") | Out-Null
New-Item -ItemType Directory -Force (Join-Path $ProjectRoot "data\rag_index") | Out-Null

Write-Host "Setup complete."
Write-Host "Run: & '$Python' -m streamlit run '$ProjectRoot\app.py'"


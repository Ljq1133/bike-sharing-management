param(
    [Parameter(Mandatory=$true)][string]$DatabaseUrl,
    [Parameter(Mandatory=$true)][string]$Secret,
    [string]$Invite = 'local-demo-invite'
)
$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath ([System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')))
try {
    $pythonExe = '.\.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Prepare .venv using scripts/setup_windows.ps1 first.' }
    $env:DATABASE_URL = $DatabaseUrl
    $env:SECRET_KEY = $Secret
    $env:MAINTAINER_INVITE = $Invite
    & $pythonExe scripts/create_db.py
    if ($LASTEXITCODE -ne 0) { throw 'Database initialization failed.' }
    & $pythonExe -m uvicorn app.server:app --host 127.0.0.1 --port 8000
} finally { Pop-Location }

param([string]$PythonCommand = 'py')
$ErrorActionPreference = 'Stop'
$projectDir = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Push-Location -LiteralPath $projectDir
try {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        if ($PythonCommand -eq 'py') { & $PythonCommand -3.11 -m venv .venv }
        else { & $PythonCommand -m venv .venv }
        if ($LASTEXITCODE -ne 0) { throw 'Failed to create virtual environment; use Python 3.11.' }
    }
    & '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    Write-Host 'Environment prepared. Follow README.md to configure and start the application.'
} finally { Pop-Location }

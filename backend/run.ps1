# Start the AI Application Architect backend reliably.
#
# This script fixes the "No module named 'app'" startup problem by:
#   1. Setting the working directory to the backend folder (where `app` lives).
#   2. Using the project's virtual environment Python (which has uvicorn).
#
# Usage (from anywhere):
#   powershell -ExecutionPolicy Bypass -File .\run.ps1
#
# The server runs in the foreground. Press Ctrl+C to stop.

$ErrorActionPreference = "Stop"

# Resolve the backend directory (this script's folder) and run from there.
$backendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $backendDir

$python = Join-Path $backendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "Virtual environment not found at $python. Run 'uv sync' first."
    exit 1
}

# Start uvicorn from the backend directory so `app` is importable.
& $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

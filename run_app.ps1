# Launch the Tessellator UI (PowerShell equivalent of run_app.sh).
# Usage: powershell -File run_app.ps1 [--embed-backend X --llm-backend Y ...]
Get-Content "$PSScriptRoot\runpod.env" | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') {
        Set-Item "env:$($Matches[1].Trim())" $Matches[2].Trim()
    }
}
& "$PSScriptRoot\.venv\Scripts\python.exe" "$PSScriptRoot\app.py" @args

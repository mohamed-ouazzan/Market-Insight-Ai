$ErrorActionPreference = 'Stop'
$pythonProjet = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonProjet)) {
    throw 'Environnement Python absent. Créez .venv et installez requirements.txt comme indiqué dans README.md.'
}
Push-Location $PSScriptRoot
try {
    & $pythonProjet -m streamlit run app.py --server.address 127.0.0.1 --server.port 8502
}
finally {
    Pop-Location
}

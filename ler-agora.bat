@echo off
rem Faz UMA leitura e mostra na tela (sem bandeja). Bom para conferir com o GameSir Connect.
cd /d "%~dp0"
set PYTHONPATH=%~dp0src
".venv\Scripts\python.exe" -m monitor_bateria --once
pause

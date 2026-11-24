@echo off
rem Inicia o monitor na bandeja, sem janela de console.
cd /d "%~dp0"
set PYTHONPATH=%~dp0src
start "" /B ".venv\Scripts\pythonw.exe" -m monitor_bateria

@echo off
rem Roda a bateria de testes (nao precisa de aparelhos).
cd /d "%~dp0"
set "PY=python"
where py >nul 2>nul && set "PY=py -3"
%PY% -m venv .venv-dev || exit /b 1
".venv-dev\Scripts\python.exe" -m pip install -r requirements-dev.txt Pillow==12.3.0 || exit /b 1
".venv-dev\Scripts\python.exe" -m pytest

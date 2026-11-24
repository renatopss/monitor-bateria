@echo off
rem Cria o ambiente isolado (.venv) e instala só o que está em requirements.txt,
rem recusando qualquer pacote cujo hash não confira.
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (echo Python nao encontrado. Instale o Python 3.10+ de python.org e rode de novo. & exit /b 1)
%PY% -m venv .venv || exit /b 1
".venv\Scripts\python.exe" -m pip install --require-hashes --only-binary=:all: -r requirements.txt || exit /b 1
echo.
echo Instalado. Confira uma leitura com: ler-agora.bat   e abra na bandeja com: iniciar.bat

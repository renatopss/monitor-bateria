"""Ponto de entrada do executável empacotado (PyInstaller)."""
import os
import sys

# Executável sem console: stdout/stderr são None e qualquer print quebraria.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

from monitor_bateria.__main__ import main

sys.exit(main())

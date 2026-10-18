@echo off
rem LAN chat relay for desktop<->laptop Claude instances (:8898).
rem Pure ASCII; python-path.txt (gitignored) can override the interpreter.
cd /d %~dp0
set PY=python
if exist "%~dp0python-path.txt" set /p PY=<"%~dp0python-path.txt"
title cc chat relay :8898
"%PY%" chat_server.py
pause

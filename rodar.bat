@echo off
cd /d D:\Automacoes\geoserver_daily
call .venv\Scripts\activate.bat
python baixar_geoserver.py >> downloads\stdout.log 2>&1

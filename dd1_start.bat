@echo off
title DD1 Platform
echo DD1 Platform baslatiliyor...
cd /d "C:\Users\DDSOUND\Desktop\exemiz\dd1_platform"
start "" "http://127.0.0.1:9000/"
python -m uvicorn main:app --host 127.0.0.1 --port 9000

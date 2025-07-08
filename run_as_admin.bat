@echo off
echo Running Card Placer as Administrator...
powershell -Command "Start-Process cmd -ArgumentList '/k cd /d \"%~dp0\" && python auto_card_placer.py' -Verb RunAs"
pause 
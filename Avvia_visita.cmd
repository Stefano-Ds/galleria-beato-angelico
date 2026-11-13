@echo off
set "BLENDER_EXE=C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
if not exist "%BLENDER_EXE%" (
 echo Blender 5.1 non trovato. Apri il progetto ed esegui il testo Visita_galleria.py.
 pause
 exit /b 1
)
start "Galleria" "%BLENDER_EXE%" --python "%~dp0Visita_galleria.py"

@echo off
setlocal EnableDelayedExpansion

cd /d "%~dp0"

echo ========================================
echo Prospection_IA - Installation Windows
echo ========================================
echo.

REM ============================================================
REM [1/6] OUTILS SYSTEME
REM ============================================================

echo [1/6] Verification des outils systeme...
echo.

where winget >nul 2>&1
if errorlevel 1 (
echo ERREUR : winget n'est pas disponible.
pause
exit /b 1
)

where curl >nul 2>&1
if errorlevel 1 (
echo ERREUR : curl est requis.
pause
exit /b 1
)

REM ============================================================
REM GNU MAKE
REM ============================================================

echo Verification de GNU Make...

where make >nul 2>&1

if not errorlevel 1 (
echo make est deja disponible.
goto MAKE_OK
)

echo make n'est pas trouve.
echo Installation de GNU Make...

winget install --id GnuWin32.Make -e --accept-source-agreements --accept-package-agreements

REM Le package peut deja etre installe : ce n'est pas une erreur.
echo.

REM ============================================================
REM Emplacement connu de GnuWin32 Make
REM ============================================================

set "MAKE_DIR=C:\Program Files (x86)\GnuWin32\bin"

if not exist "!MAKE_DIR!\make.exe" (
set "MAKE_DIR=C:\Program Files\GnuWin32\bin"
)

if not exist "!MAKE_DIR!\make.exe" (
echo.
echo Recherche de make.exe...

for /f "delims=" %%F in ('where /R "C:\Program Files (x86)" make.exe 2^>nul') do (
    set "MAKE_EXE=%%F"
    goto MAKE_FOUND
)

for /f "delims=" %%F in ('where /R "C:\Program Files" make.exe 2^>nul') do (
    set "MAKE_EXE=%%F"
    goto MAKE_FOUND
)

echo.
echo ERREUR : make.exe est introuvable.
pause
exit /b 1


)

goto MAKE_DIR_READY

:MAKE_FOUND

for %%F in ("!MAKE_EXE!") do set "MAKE_DIR=%%~dpF"
set "MAKE_DIR=!MAKE_DIR:~0,-1!"

:MAKE_DIR_READY

echo make.exe trouve dans :
echo !MAKE_DIR!

REM ============================================================
REM AJOUT PERMANENT AU PATH WINDOWS
REM ============================================================

echo.
echo Ajout de GNU Make au PATH Windows...

powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=[Environment]::GetEnvironmentVariable('Path','User'); $d='!MAKE_DIR!'; if (($p -split ';') -notcontains $d) { [Environment]::SetEnvironmentVariable('Path', (($p.TrimEnd(';') + ';' + $d).Trim(';')), 'User') }"

if errorlevel 1 (
echo.
echo ERREUR : impossible de modifier le PATH utilisateur.
pause
exit /b 1
)

REM Ajouter egalement Make au PATH de cette session
set "PATH=!MAKE_DIR!;%PATH%"

:MAKE_OK

where make >nul 2>&1

if errorlevel 1 (
echo.
echo ERREUR : make est toujours introuvable.
echo.
echo Ferme ce terminal et ouvre un NOUVEAU terminal.
echo Puis execute :
echo.
echo where make
echo make --version
echo.
pause
exit /b 1
)

echo.
echo GNU Make : OK

make --version

echo.

REM ============================================================
REM [2/6] UV
REM ============================================================

echo [2/6] Installation de uv...
echo.

where uv >nul 2>&1

if errorlevel 1 (
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
set "PATH=%USERPROFILE%.local\bin;%USERPROFILE%.cargo\bin;%PATH%"
)

where uv >nul 2>&1

if errorlevel 1 (
echo.
echo ERREUR : uv n'est pas disponible.
echo Ferme et rouvre le terminal puis relance le script.
pause
exit /b 1
)

for /f "delims=" %%v in ('uv --version') do echo uv : %%v

echo.

REM ============================================================
REM [3/6] PYTHON + DEPENDANCES
REM ============================================================

echo [3/6] Installation de Python et des dependances du projet...
echo.

uv python install 3.12

if errorlevel 1 (
echo ERREUR : installation de Python echouee.
pause
exit /b 1
)

uv sync

if errorlevel 1 (
echo ERREUR : uv sync a echoue.
pause
exit /b 1
)

echo.

REM ============================================================
REM [4/6] PLAYWRIGHT
REM ============================================================

echo [4/6] Installation de Chromium pour Playwright...
echo.

uv run python -m playwright install chromium

if errorlevel 1 (
echo ERREUR : installation de Chromium echouee.
pause
exit /b 1
)

echo.

REM ============================================================
REM [5/6] OLLAMA
REM ============================================================

echo [5/6] Installation de Ollama...
echo.

set "PATH=%LOCALAPPDATA%\Programs\Ollama;C:\Program Files\Ollama;%PATH%"

where ollama >nul 2>&1

if errorlevel 1 (
echo Installation de Ollama...

powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://ollama.com/install.ps1 | iex"

set "PATH=%LOCALAPPDATA%\Programs\Ollama;C:\Program Files\Ollama;%PATH%"


)

where ollama >nul 2>&1

if errorlevel 1 (
echo.
echo ERREUR : Ollama n'est pas disponible.
echo Ferme et rouvre le terminal puis relance le script.
pause
exit /b 1
)

for /f "delims=" %%v in ('ollama --version 2^>nul') do echo ollama : %%v

echo.

REM ============================================================
REM [6/6] MODELE LLAMA
REM ============================================================

echo [6/6] Installation du modele llama3.2:3b...
echo.

REM Verifier si Ollama tourne deja
curl -fsS http://127.0.0.1:11434/api/tags >nul 2>&1

if not errorlevel 1 (
echo Ollama est deja en cours d'execution.
goto OLLAMA_READY
)

REM Verifier si le port est occupe
netstat -ano | findstr ":11434" >nul 2>&1

if not errorlevel 1 (
echo Le port 11434 est deja utilise.
echo Attente du service Ollama...

for /L %%i in (1,1,10) do (
    curl -fsS http://127.0.0.1:11434/api/tags >nul 2>&1

    if not errorlevel 1 (
        goto OLLAMA_READY
    )

    timeout /t 1 /nobreak >nul
)

echo.
echo ERREUR : le port 11434 est utilise mais Ollama ne repond pas.
echo.
pause
exit /b 1


)

REM Lancer Ollama
echo Lancement de Ollama...

start "" /B ollama serve

echo Attente du demarrage de Ollama...

for /L %%i in (1,1,20) do (
curl -fsS http://127.0.0.1:11434/api/tags >nul 2>&1

if not errorlevel 1 (
    goto OLLAMA_READY
)

timeout /t 1 /nobreak >nul


)

echo.
echo ERREUR : Ollama ne repond pas apres 20 secondes.
echo.
echo Lance manuellement :
echo ollama serve
echo.
pause
exit /b 1

:OLLAMA_READY

echo.
echo Ollama est pret.
echo Installation du modele llama3.2:3b...
echo.

ollama pull llama3.2:3b

if errorlevel 1 (
echo.
echo ERREUR : impossible d'installer llama3.2:3b.
echo.
echo Verifie avec :
echo ollama list
echo.
pause
exit /b 1
)

echo.
echo ========================================
echo Installation terminee avec succes
echo ========================================
echo.
echo Verifications :
echo make : OK
echo uv : OK
echo ollama : OK
echo modele : llama3.2:3b
echo.
echo IMPORTANT :
echo Ferme ce terminal et ouvre un NOUVEAU terminal.
echo.
echo Puis teste :
echo make --version
echo.
echo Ensuite :
echo make help
echo.
pause
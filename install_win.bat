@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ========================================
echo   Prospection_IA - Installation Windows
echo ========================================
echo.

REM --- Vérifier winget ---
where winget >nul 2>&1
if errorlevel 1 (
    echo ERREUR : winget n'est pas disponible.
    echo Installe/active "App Installer" de Microsoft puis relance install_win.bat.
    pause
    exit /b 1
)

REM --- Vérifier curl ---
where curl >nul 2>&1
if errorlevel 1 (
    echo ERREUR : curl est requis.
    pause
    exit /b 1
)

echo [1/6] Verification des outils systeme...
where make >nul 2>&1
if errorlevel 1 (
    echo - Installation de GNU Make...
    winget install --id GnuWin32.Make -e --accept-source-agreements --accept-package-agreements
) else (
    echo   make deja installe.
)

REM Rafraichir PATH
set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"
set "PATH=%LOCALAPPDATA%\Programs\Ollama;%PATH%"
set "PATH=C:\Program Files\Ollama;%PATH%"

echo.
echo [2/6] Installation de uv...

where uv >nul 2>&1
if errorlevel 1 (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"
)

where uv >nul 2>&1
if errorlevel 1 (
    echo ERREUR : uv n'a pas pu etre installe ou n'est pas dans le PATH.
    pause
    exit /b 1
)

for /f "delims=" %%v in ('uv --version') do echo   uv : %%v

echo.
echo [3/6] Installation de Python et des dependances du projet...

uv python install 3.12
uv sync

echo.
echo [4/6] Installation de Chromium pour Playwright...

uv run python -m playwright install chromium

echo.
echo [5/6] Installation de Ollama...

where ollama >nul 2>&1
if errorlevel 1 (
    echo - Installation de Ollama pour Windows...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://ollama.com/install.ps1 | iex"
    set "PATH=%LOCALAPPDATA%\Programs\Ollama;%PATH%"
    set "PATH=C:\Program Files\Ollama;%PATH%"
)

where ollama >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERREUR : Ollama est installe mais la commande n'est pas dans le PATH.
    echo Ferme et rouvre ton terminal puis relance install_win.bat.
    pause
    exit /b 1
)

for /f "delims=" %%v in ('ollama --version 2^>nul') do echo   ollama : %%v

echo.
echo [6/6] Installation du modele llama3.2:3b...

REM Verifier si Ollama tourne
curl -fsS http://127.0.0.1:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo - Lancement de Ollama...
    start "" /B ollama serve
    timeout /t 3 /nobreak >nul
)

curl -fsS http://127.0.0.1:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo ERREUR : Ollama ne repond pas sur http://127.0.0.1:11434.
    echo Lance "ollama serve" manuellement puis relance :
    echo     ollama pull llama3.2:3b
    pause
    exit /b 1
)

ollama pull llama3.2:3b

echo.
echo ========================================
echo   Installation terminee avec succes
echo ========================================
echo.
echo Verifications :
echo   uv      : (voir ci-dessus)
echo   make    : (voir ci-dessus)
echo   ollama  : (voir ci-dessus)
echo   modele  : llama3.2:3b
echo.
echo Tu peux maintenant utiliser :
echo   make run FILE=test.xlsx
echo.
pause

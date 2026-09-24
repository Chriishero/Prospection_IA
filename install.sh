#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "========================================"
echo "  Prospection_IA - Installation"
echo "========================================"
echo

is_windows=false
case "${OSTYPE:-}" in
    msys*|mingw*|cygwin*) is_windows=true ;;
esac

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

refresh_path() {
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

    if $is_windows; then
        local uv_dir="$HOME/.local/bin"
        local uv_win="$USERPROFILE/.local/bin"
        [ -d "$uv_win" ] && export PATH="$uv_win:$PATH"
        [ -d "/c/Users/$USERNAME/.local/bin" ] && export PATH="/c/Users/$USERNAME/.local/bin:$PATH"
        [ -d "/c/Program Files/Ollama" ] && export PATH="/c/Program Files/Ollama:$PATH"
        [ -d "$LOCALAPPDATA/Programs/Ollama" ] && export PATH="$LOCALAPPDATA/Programs/Ollama:$PATH"
    fi
}

echo "[1/6] Vérification de l'environnement..."

if $is_windows; then
    echo "→ Windows détecté (Git Bash / MSYS / Cygwin)."

    if ! command_exists winget; then
        echo
        echo "ERREUR : winget n'est pas disponible."
        echo "Installe/active 'App Installer' de Microsoft puis relance install.sh."
        exit 1
    fi

    if ! command_exists make; then
        echo "→ Installation de GNU Make..."
        winget install --id GnuWin32.Make -e --accept-source-agreements --accept-package-agreements
    else
        echo "✓ make déjà installé."
    fi

    if ! command_exists curl; then
        echo "ERREUR : curl est requis dans Git Bash."
        exit 1
    fi

else
    echo "→ Linux détecté."

    if command_exists apt-get; then
        echo "→ Vérification des outils système..."
        sudo apt-get update
        sudo apt-get install -y curl ca-certificates make
    elif ! command_exists make || ! command_exists curl; then
        echo "ERREUR : ce système n'est pas Debian/Ubuntu et make/curl manquent."
        echo "Installe make et curl avec le gestionnaire de paquets de ta distribution."
        exit 1
    fi
fi

refresh_path

echo
echo "[2/6] Installation de uv..."

if ! command_exists uv; then
    if $is_windows; then
        powershell.exe -NoProfile -ExecutionPolicy Bypass -Command \
            "irm https://astral.sh/uv/install.ps1 | iex"
    else
        curl -LsSf https://astral.sh/uv/install.sh | sh
    fi
    refresh_path
fi

if ! command_exists uv; then
    echo "ERREUR : uv n'a pas pu être installé ou n'est pas dans le PATH."
    exit 1
fi

echo "✓ uv : $(uv --version)"

echo
echo "[3/6] Installation de Python et des dépendances du projet..."

uv python install 3.12
uv sync

echo
echo "[4/6] Installation de Chromium pour Playwright..."

uv run playwright install chromium

echo
echo "[5/6] Installation de Ollama..."

if ! command_exists ollama; then
    if $is_windows; then
        echo "→ Installation de Ollama pour Windows..."
        powershell.exe -NoProfile -ExecutionPolicy Bypass -Command \
            "irm https://ollama.com/install.ps1 | iex"
        refresh_path
    else
        echo "→ Installation de Ollama pour Linux..."
        curl -fsSL https://ollama.com/install.sh | sh
        refresh_path
    fi
fi

if ! command_exists ollama; then
    echo
    echo "ERREUR : Ollama est installé mais la commande n'est pas encore dans le PATH."
    echo "Ferme et rouvre ton terminal puis relance install.sh."
    exit 1
fi

echo "✓ Ollama : $(ollama --version 2>/dev/null || true)"

echo
echo "[6/6] Installation du modèle llama3.2:3b..."

if $is_windows; then
    if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        echo "→ Ollama n'est pas encore accessible, lancement de ollama serve..."
        nohup ollama serve >/tmp/prospection_ia_ollama.log 2>&1 &
        sleep 3
    fi
else
    if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        echo "→ Lancement de Ollama..."
        nohup ollama serve >/tmp/prospection_ia_ollama.log 2>&1 &
        sleep 3
    fi
fi

if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    echo "ERREUR : Ollama ne répond pas sur http://127.0.0.1:11434."
    echo "Lance 'ollama serve' manuellement puis relance :"
    echo "    ollama pull llama3.2:3b"
    exit 1
fi

ollama pull llama3.2:3b

echo
echo "========================================"
echo "  Installation terminée avec succès"
echo "========================================"
echo
echo "Vérifications :"
echo "  uv      : $(uv --version)"
echo "  make    : $(make --version | head -n 1)"
echo "  ollama  : $(ollama --version 2>/dev/null || true)"
echo "  modèle  : llama3.2:3b"
echo
echo "Tu peux maintenant utiliser :"
echo "  make run FILE=test.xlsx"
echo
echo "Sous Windows, lance ce fichier depuis Git Bash."

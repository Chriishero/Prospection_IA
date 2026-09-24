#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "========================================"
echo "  Prospection_IA - Installation Linux"
echo "========================================"
echo

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

refresh_path() {
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
}

echo "[1/6] Vérification des outils système..."

if command_exists apt-get; then
    echo "→ Debian/Ubuntu détecté."
    sudo apt-get update
    sudo apt-get install -y curl ca-certificates make
elif command_exists dnf; then
    echo "→ Fedora/RHEL détecté."
    sudo dnf install -y curl ca-certificates make
elif command_exists pacman; then
    echo "→ Arch détecté."
    sudo pacman -Sy --noconfirm curl ca-certificates make
else
    if ! command_exists make || ! command_exists curl; then
        echo "ERREUR : distribution non reconnue et make/curl manquants."
        echo "Installe make et curl avec ton gestionnaire de paquets."
        exit 1
    fi
fi

refresh_path

echo
echo "[2/6] Installation de uv..."

if ! command_exists uv; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
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

uv run python -m playwright install chromium

echo
echo "[5/6] Installation de Ollama..."

if ! command_exists ollama; then
    curl -fsSL https://ollama.com/install.sh | sh
    refresh_path
fi

if ! command_exists ollama; then
    echo "ERREUR : Ollama est installé mais la commande n'est pas dans le PATH."
    echo "Ferme et rouvre ton terminal puis relance install_linux.sh."
    exit 1
fi

echo "✓ Ollama : $(ollama --version 2>/dev/null || true)"

echo
echo "[6/6] Installation du modèle llama3.2:3b..."

if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    echo "→ Lancement de Ollama..."
    nohup ollama serve >/tmp/prospection_ia_ollama.log 2>&1 &
    sleep 3
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

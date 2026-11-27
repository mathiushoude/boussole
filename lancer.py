"""Lance Boussole et l'ouvre aussi aux téléphones et tablettes du même réseau Wi-Fi.

    python lancer.py            # ordinateur + appareils du réseau local
    python lancer.py --local    # cet ordinateur uniquement

Fonctionne sous Windows, macOS et Linux.
"""
from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path

PORT = 8501


def ip_locale() -> str | None:
    """Adresse de cet ordinateur sur le réseau local (aucune donnée n'est envoyée)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))      # aucun paquet n'est émis : sert à choisir l'interface réseau
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def main() -> None:
    local = "--local" in sys.argv
    adresse = "127.0.0.1" if local else "0.0.0.0"
    print(f"\n  Boussole sur cet ordinateur : http://localhost:{PORT}")
    ip = None if local else ip_locale()
    if ip:
        print(f"  Sur votre téléphone ou tablette (même Wi-Fi) : http://{ip}:{PORT}")
        print("  Puis « Ajouter à l'écran d'accueil » pour l'installer comme une application.\n")
    app = Path(__file__).with_name("app.py")
    subprocess.call([sys.executable, "-m", "streamlit", "run", str(app), "--server.address", adresse,
                     "--server.port", str(PORT)])


if __name__ == "__main__":
    main()

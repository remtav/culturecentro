"""Accès réseau partagé : session ``requests`` et téléchargement.

Toutes les sources téléchargent leurs pages via ces fonctions, avec des
en-têtes « navigateur » et des reprises automatiques sur erreurs réseau.
"""

from __future__ import annotations

import requests
from urllib3.util.retry import Retry

#: En-têtes HTTP communs. Un User-Agent « navigateur » évite les blocages basiques.
ENTETES = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}


def creer_session() -> requests.Session:
    """Session ``requests`` avec en-têtes navigateur et reprises réseau."""
    session = requests.Session()
    session.headers.update(ENTETES)
    reprises = Retry(
        total=3,
        backoff_factor=1.0,  # 0s, 1s, 2s, 4s
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
    )
    adaptateur = requests.adapters.HTTPAdapter(max_retries=reprises)
    session.mount("https://", adaptateur)
    session.mount("http://", adaptateur)
    return session


def telecharger(url: str, timeout: float, session: requests.Session | None = None) -> str:
    """Télécharge ``url`` et renvoie le corps de la réponse (texte)."""
    client = session or requests
    reponse = client.get(url, headers=ENTETES, timeout=timeout)
    reponse.raise_for_status()
    return str(reponse.text)

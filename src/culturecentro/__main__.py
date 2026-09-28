"""Point d'entrée ``python -m culturecentro`` : la CLI unifiée."""

from __future__ import annotations

from culturecentro.cli import principal

if __name__ == "__main__":
    raise SystemExit(principal())

"""Verbindungstest fuer die Whatnot Seller API (nur lesend: GET /users/me).

Liest den Token aus der .env im selben Ordner und gibt ihn nirgends aus.
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "https://api.whatnot.com/seller-api/rest/v2"


def load_token() -> str:
    env_file = Path(__file__).with_name(".env")
    if not env_file.exists():
        sys.exit("Fehler: .env nicht gefunden.")
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line.startswith("WHATNOT_API_TOKEN="):
            token = line.split("=", 1)[1].strip().strip('"').strip("'")
            if not token or token == "HIER_TOKEN_EINFUEGEN":
                sys.exit("Fehler: In der .env ist noch kein Token eingetragen.")
            return token
    sys.exit("Fehler: WHATNOT_API_TOKEN fehlt in der .env.")


def main() -> None:
    token = load_token()
    kind = "persoenlicher Token" if token.startswith("wn_pat_tk_") else "unbekanntes Token-Format"
    print(f"Token gefunden ({kind}, {len(token)} Zeichen).")

    req = urllib.request.Request(
        f"{BASE_URL}/users/me",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            status, headers, body = resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as e:
        status, headers, body = e.code, e.headers, e.read()

    print(f"HTTP-Status: {status}")
    for h in ("RateLimit-Limit", "RateLimit-Remaining"):
        if headers.get(h):
            print(f"{h}: {headers.get(h)}")
    try:
        print(json.dumps(json.loads(body), indent=2, ensure_ascii=False))
    except ValueError:
        print(body.decode("utf-8", "replace")[:1000])


if __name__ == "__main__":
    main()

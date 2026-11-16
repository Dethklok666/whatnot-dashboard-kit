"""Kleiner Client fuer die Whatnot Seller API v2 (nur Standardbibliothek).

Liest den Token aus der .env im selben Ordner und gibt ihn nirgends aus.
"""
import json
import sys
import time
import urllib.error
import urllib.parse
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


class ApiError(Exception):
    def __init__(self, status: int, body):
        self.status, self.body = status, body
        super().__init__(f"HTTP {status}: {body}")


class WhatnotClient:
    def __init__(self, token: str | None = None):
        self._token = token or load_token()

    def request(self, method: str, path: str, params: dict | None = None, body=None):
        url = BASE_URL + path
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        for attempt in range(5):
            req = urllib.request.Request(url, data=data, method=method, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = resp.read()
                    return json.loads(raw) if raw else None
            except urllib.error.HTTPError as e:
                raw = e.read()
                if e.code == 429 and attempt < 4:
                    time.sleep(float(e.headers.get("Retry-After") or 1) + 0.2 * attempt)
                    continue
                try:
                    parsed = json.loads(raw)
                except ValueError:
                    parsed = raw.decode("utf-8", "replace")[:500]
                raise ApiError(e.code, parsed) from None

    def get(self, path: str, **params):
        return self.request("GET", path, params)

    def post(self, path: str, body):
        return self.request("POST", path, body=body)

#!/usr/bin/env python3
"""
Pantheon na Mão — gera o arquivo criptografado de dados do app.

Uso:
    python3 tools/montar_dados.py CAMINHO/dados.json PIN

Lê o dados.json (que NUNCA deve ir para o GitHub) e grava data.enc.json
na raiz do app. O app só consegue abrir esse arquivo com o PIN informado.

Para trocar o PIN: rode de novo com o PIN novo e publique o data.enc.json.
Requer: pip install cryptography
"""
import base64
import json
import os
import sys

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ITER = 310_000


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, pin = sys.argv[1], sys.argv[2].strip()
    if not (pin.isdigit() and 4 <= len(pin) <= 8):
        sys.exit("O PIN deve ter de 4 a 8 números.")
    with open(src, encoding="utf8") as f:
        data = json.load(f)
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf8")
    salt, iv = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER).derive(pin.encode())
    ct = AESGCM(key).encrypt(iv, raw, None)
    b64 = lambda b: base64.b64encode(b).decode()
    out = {"v": 1, "iter": ITER, "n": len(pin), "salt": b64(salt), "iv": b64(iv), "ct": b64(ct),
           "atualizado": data.get("atualizado", "")}
    dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data.enc.json")
    with open(dst, "w") as f:
        json.dump(out, f)
    print(f"OK: {os.path.normpath(dst)} ({len(ct):,} bytes criptografados)")


if __name__ == "__main__":
    main()

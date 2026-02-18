cat > baixar_geoserver.py <<'PY'
import os
import json
import time
import hashlib
import datetime as dt
from typing import Dict, Any, Optional

import requests
import pandas as pd

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(PROJECT_DIR, "downloads")
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.json")
STATE_PATH = os.path.join(OUT_DIR, "_state.json")
LOG_PATH = os.path.join(OUT_DIR, "_daily_log.txt")

def sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()

def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")

def ensure_dirs() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

def load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: str, obj: Any) -> None:
    ensure_dirs()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def log(line: str) -> None:
    ensure_dirs()
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[{ts}] {line}"
    print(msg)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def wfs_getfeature(base_ows: str, typeNames: str, outputFormat: str, timeout=180) -> bytes:
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": typeNames,
        "outputFormat": outputFormat,
    }
    r = requests.get(base_ows, params=params, timeout=timeout)
    r.raise_for_status()
    return r.content

def main():
    ensure_dirs()
    config = load_json(CONFIG_PATH, default=None)
    if not config:
        raise RuntimeError("config.json não encontrado.")

    base_ows = config["base_ows"]
    jobs = config["jobs"]
    state: Dict[str, Any] = load_json(STATE_PATH, default={})
    stamp = now_stamp()

    log(f"Início da rotina diária. Camadas: {len(jobs)}")

    for job in jobs:
        typeNames = job["typeNames"]
        outputFormat = job["outputFormat"]
        ext = job["ext"]

        safe_name = typeNames.replace(":", "__").replace("/", "_")
        latest_path = os.path.join(OUT_DIR, f"{safe_name}.{ext}")
        versioned_path = os.path.join(OUT_DIR, f"{safe_name}_{stamp}.{ext}")

        try:
            content = wfs_getfeature(base_ows, typeNames, outputFormat)
            new_hash = sha256_bytes(content)
            prev = state.get(typeNames, {})
            old_hash = prev.get("sha256")

            if old_hash == new_hash and old_hash is not None:
                log(f"{typeNames}: sem mudança.")
            else:
                with open(versioned_path, "wb") as f:
                    f.write(content)
                with open(latest_path, "wb") as f:
                    f.write(content)

                log(f"{typeNames}: ALTEROU.")
                state[typeNames] = {
                    "sha256": new_hash,
                    "last_path": versioned_path,
                    "updated_at": dt.datetime.now().isoformat(timespec="seconds"),
                }

            time.sleep(1)

        except Exception as e:
            log(f"{typeNames}: ERRO: {type(e).__name__}: {e}")

    save_json(STATE_PATH, state)
    log("Fim da rotina diária.")

if __name__ == "__main__":
    main()
PY

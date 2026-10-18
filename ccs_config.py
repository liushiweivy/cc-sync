# -*- coding: utf-8 -*-
"""Local private config: token / peer addresses / data dirs are read from
ccs.local.json (gitignored) or CCS_* environment variables. Source code never
carries real values. See ccs.local.example.json for the file shape.
"""
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load():
    try:
        with open(os.path.join(ROOT, "ccs.local.json"), encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return {}


_CFG = _load()


def get(key, default=""):
    """Priority: env CCS_<KEY> > ccs.local.json > default."""
    return os.environ.get("CCS_" + key.upper()) or _CFG.get(key) or default


TOKEN = get("token", "change-me")
RELAY_BASE = get("relay_base", "http://127.0.0.1:8898")
PUSH_URL = get("push_url", "")  # peer push receiver (optional, relay is the fallback)
DATA_DIR = get("data_dir", os.path.join(ROOT, "chat"))
INBOX_DIR = get("inbox_dir", os.path.join(ROOT, "inbox"))

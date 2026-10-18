# -*- coding: utf-8 -*-
"""UserPromptSubmit hook: surface unread laptop-Claude messages into context.

Prints unread messages (from=laptop) from the local relay and advances the
last-read cursor. Must be fast and never break the prompt flow: any error
exits silently with code 0 and no output.
"""
import json
import os
import sys
import urllib.request

from ccs_config import DATA_DIR, RELAY_BASE, TOKEN

RELAY = RELAY_BASE + "/messages?token=" + TOKEN + "&since=%d"
CURSOR = os.path.join(DATA_DIR, ".lastread-desktop")
MAX_SHOW = 1500


def main():
    try:
        last = 0
        if os.path.exists(CURSOR):
            with open(CURSOR, "r", encoding="ascii") as f:
                last = int(f.read().strip() or "0")
        with urllib.request.urlopen(RELAY % last, timeout=1.5) as r:
            msgs = json.load(r).get("messages", [])
        fresh = [m for m in msgs if m.get("from") == "laptop"]
        if not fresh:
            return
        lines = ["[cc-relay] %d unread message(s) from laptop Claude:" % len(fresh)]
        for m in fresh:
            text = m.get("text", "")
            if len(text) > MAX_SHOW:
                text = text[:MAX_SHOW] + " ...[truncated]"
            lines.append("--- id=%s %s ---\n%s" % (m["id"], m["ts"], text))
        print("\n".join(lines))
        with open(CURSOR, "w", encoding="ascii") as f:
            f.write(str(max(m["id"] for m in fresh)))
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()

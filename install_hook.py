# -*- coding: utf-8 -*-
"""One-shot: add relay_unread.py as a UserPromptSubmit hook in settings.json."""
import json
import os
import shutil
import sys
import time

P = os.path.expanduser(os.path.join("~", ".claude", "settings.json"))
SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "relay_unread.py")
CMD = '"%s" -X utf8 "%s"' % (sys.executable, SCRIPT)

shutil.copy(P, P + ".bak-relayhook-" + time.strftime("%Y%m%d%H%M"))
with open(P, "r", encoding="utf-8") as f:
    cfg = json.load(f)
ups = cfg.setdefault("hooks", {}).setdefault("UserPromptSubmit", [])
if any("relay_unread" in json.dumps(e) for e in ups):
    print("already installed")
else:
    ups.append({"hooks": [{"type": "command", "command": CMD}]})
    with open(P, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print("hook added; UserPromptSubmit entries now:", len(ups))

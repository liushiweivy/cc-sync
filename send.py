# -*- coding: utf-8 -*-
"""Send a message to the peer Claude (push) with relay fallback.

Primary: POST <push_url>            {"from","text"}         (peer push receiver)
Fallback: POST <relay_base>/send    {"token","from","text"} (relay, peer polls)
Addresses/token come from ccs_config (ccs.local.json / CCS_* env).

Usage: python send.py <from> <textfile>
"""
import json
import sys
import time
import urllib.request

from ccs_config import PUSH_URL, RELAY_BASE, TOKEN as RELAY_TOKEN

RELAY_URL = RELAY_BASE + "/send"


def post(url, payload, timeout=8):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def main():
    sender, path = sys.argv[1], sys.argv[2]
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    if PUSH_URL:  # 未配置直推地址时直接走中继
        for attempt in (1, 2):
            try:
                resp = post(PUSH_URL, {"from": sender, "text": text})
                print("pushed to peer:", resp)
                return
            except Exception as e:
                print("push attempt %d failed: %s" % (attempt, e))
                time.sleep(3)

    resp = post(RELAY_URL, {"token": RELAY_TOKEN, "from": sender, "text": text})
    print("fell back to relay 8898:", resp)


if __name__ == "__main__":
    main()

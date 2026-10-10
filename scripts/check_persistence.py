import json
import os
import urllib.request

keys = json.loads(os.environ.get("AGENTFORGE_KEYS", "{}"))
if not keys:
    from pathlib import Path

    line = next(x for x in Path(".env").read_text().splitlines() if x.startswith("AGENTFORGE_KEYS="))
    keys = json.loads(line.split("=", 1)[1].strip("'"))
key = next(k for k, v in keys.items() if v["role"] == "operator")
request = urllib.request.Request("http://localhost:8000/runs", headers={"Authorization": "Bearer " + key})
with urllib.request.urlopen(request) as response:
    runs = json.load(response)
completed = {r["request"]["scenario"] for r in runs if r["status"] == "completed"}
assert completed == {"incident", "sdlc", "knowledge", "workflow", "reliability"}, completed
print("All five completed workflow records survived API restart")

"""Offline smoke test only: fill the judging pages with simulated grades (a hidden 'true'
grade per document plus annotator noise) and write exports in the page's format."""
import glob
import hashlib
import json
import random
import re
import sys
from pathlib import Path

pages, out = sys.argv[1], Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
for p in sorted(glob.glob(f"{pages}/judge_*.html")):
    html = Path(p).read_text()
    data = json.loads(re.search(r"const DATA = (\{.*?\});\n", html, re.S).group(1).replace("<\\/", "</"))
    rng = random.Random(data["annotator"])
    js = []
    for it in data["items"]:
        h = int(hashlib.md5((it["qid"] + it["docid"]).encode()).hexdigest(), 16)
        true = [0, 0, 1, 2, 3][h % 5]
        g = min(3, max(0, true + rng.choice([0, 0, 0, 0, 1, -1])))
        js.append({"qid": it["qid"], "docid": it["docid"], "grade": g})
    (out / f"judgments_{data['annotator']}_main.json").write_text(
        json.dumps({"annotator": data["annotator"], "round": "main", "judgments": js}))
    print(data["annotator"], len(js))

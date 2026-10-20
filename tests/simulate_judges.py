"""Offline smoke test only: fill the judging pages with SIMULATED grades (a hidden 'true'
grade per document plus annotator noise) and write exports in the page's format.
Never used for real data: outputs go to the smoke-test work folder."""
import glob
import hashlib
import json
import random
import sys
from pathlib import Path

from irproj.judging import parse_page

pages, out = sys.argv[1], Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
for p in sorted(glob.glob(f"{pages}/judge_*.html")):
    meta, items = parse_page(p)
    rng = random.Random(meta["annotator"])
    js = []
    for it in items:
        h = int(hashlib.md5((it["qid"] + it["docid"]).encode()).hexdigest(), 16)
        true = [0, 0, 1, 2, 3][h % 5]
        g = min(3, max(0, true + rng.choice([0, 0, 0, 0, 1, -1])))
        js.append({"qid": it["qid"], "docid": it["docid"], "grade": g})
    (out / f"judgments_{meta['annotator']}_{meta['round']}.json").write_text(json.dumps(
        {"annotator": meta["annotator"], "round": meta["round"], "pool_id": meta["pool-id"], "judgments": js}))
    print(meta["annotator"], len(js))

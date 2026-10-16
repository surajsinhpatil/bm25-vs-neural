"""Write a fake arXiv metadata snapshot (same JSON-lines schema as the Kaggle file) so the
whole cs.CR pipeline can be exercised offline. Text comes from a BEIR-format corpus; a few
security-flavoured records, duplicates, withdrawn papers and LaTeX are added on purpose."""
import json
import random
import sys

src, dst = sys.argv[1], sys.argv[2]
rng = random.Random(0)
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def rec(i, title, abstract, cats, year, comments=None):
    return {"id": f"{year % 100:02d}{rng.randint(1, 12):02d}.{i:05d}", "submitter": "x", "authors": "A. Author",
            "title": title, "comments": comments, "journal-ref": None, "doi": None, "report-no": None,
            "categories": cats, "license": None, "abstract": abstract,
            "versions": [{"version": "v1", "created": f"Mon, {rng.randint(1, 28)} {rng.choice(MONTHS)} {year} 10:00:00 GMT"},
                         {"version": "v2", "created": f"Tue, 1 Jan {year + 1} 10:00:00 GMT"}],
            "update_date": f"{year + 1}-01-01", "authors_parsed": [["Author", "A.", ""]]}


rows = []
for i, line in enumerate(open(src)):
    d = json.loads(line)
    cats = rng.choice(["cs.CR", "cs.CR cs.LG", "cs.LG cs.CR", "cs.LG", "cs.NI"])
    year = rng.randint(2013, 2026)
    rows.append(rec(i, d["title"], d["text"], cats, year))
special = [
    ("Spectre Attacks: Exploiting Speculative Execution", "Modern processors use branch prediction and speculative execution. We show CVE-2017-5753 bounds check bypass.", 2018),
    ("TRRespass: Exploiting the Many Sides of Target Row Refresh", "Rowhammer on DDR4 despite TRR mitigations.", 2020),
    ("Attacks on TLS~1.3 0-RTT: a study of \\emph{early data}", "We analyse TLS 1.3 replay of $0$-RTT early data and the Log4Shell CVE-2021-44228 case.", 2019),
    ("Spectre attacks: exploiting speculative execution", "Duplicate title with different case, later version.", 2019),
]
for j, (t, ab, y) in enumerate(special):
    rows.append(rec(90000 + j, t, ab, "cs.CR", y))
rows.append(rec(90100, "A withdrawn paper", "This paper has been withdrawn by the author.", "cs.CR", 2020))
rows.append(rec(90101, "Another withdrawn", "Some abstract.", "cs.CR", 2020, comments="Withdrawn due to an error"))
rng.shuffle(rows)
with open(dst, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
print(len(rows), "records")

"""Browser test of the judging page (headless Chromium via Playwright; skipped if unavailable).
Grades are entered here only inside a temporary browser profile to test the page itself;
nothing is written to judging/exports/."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")

from irproj.judging import load_pool, parse_page  # noqa: E402
from irproj.pool import load_exports  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
from test_judging_pages import POOL, TOPICS, stand_in_corpus  # noqa: E402


@pytest.fixture(scope="module")
def pages(tmp_path_factory):
    d = tmp_path_factory.mktemp("browser")
    stand_in_corpus(d / "corpus.jsonl", load_pool(POOL))
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_judging_pages.py"), "--pool", str(POOL),
                        "--topics", str(TOPICS), "--corpus", str(d / "corpus.jsonl"), "--out", str(d / "round1"),
                        "--allow-sha-mismatch"], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr
    return d / "round1"


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:  # pragma: no cover
            pytest.skip(f"no Chromium: {e}")
        yield b
        b.close()


def url(path):
    return "file://" + str(path)


def current(page):
    return page.locator("article.item.current")


def test_grade_save_reload_export_import(pages, browser, tmp_path):
    page_file = pages / "judge_Suraj.html"
    _, items = parse_page(page_file)
    n = len(items)
    ctx = browser.new_context(accept_downloads=True)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(url(page_file))

    # one item visible, with all its content
    assert pg.locator("article.item:visible").count() == 1
    cur = current(pg)
    for cls, field in (("query", "query"), ("desc", "desc"), ("narr", "narr"), ("title", "title"),
                       ("abstract", "abstract")):
        txt = " ".join(cur.locator("." + cls).inner_text().split())
        assert txt and txt == items[0][field], cls
    assert pg.locator(".nojs-only").is_hidden()
    assert pg.locator("#storageWarning").is_hidden()          # storage works here, so no warning
    assert pg.locator("#count").inner_text() == f"0 of {n} judged"

    # grade item 1 with the keyboard and item 2 with a button
    pg.keyboard.press("2")
    assert current(pg).get_attribute("data-i") == "1"
    current(pg).locator('.grades button[data-g="3"]').click()
    assert current(pg).get_attribute("data-i") == "2"
    assert pg.locator("#count").inner_text() == f"2 of {n} judged"

    # saved across a reload; the page reopens at the first unjudged item
    pg.reload()
    assert pg.locator("#count").inner_text() == f"2 of {n} judged"
    assert current(pg).get_attribute("data-i") == "2"
    pg.click("#prev")
    assert current(pg).locator(".saved-grade").inner_text() == "Saved grade: 3"
    assert current(pg).locator('.grades button.sel').get_attribute("data-g") == "3"

    # export
    with pg.expect_download() as dl:
        pg.click("#export")
    out = tmp_path / "judgments_Suraj_main.json"
    dl.value.save_as(out)
    data = json.loads(out.read_text())
    assert data["annotator"] == "Suraj" and data["round"] == "main"
    assert data["pool_id"] == load_pool(POOL)["pool_id"]
    assert len(data["judgments"]) == n
    graded = {(j["qid"], j["docid"]): j["grade"] for j in data["judgments"] if j["grade"] is not None}
    assert graded == {(items[0]["qid"], items[0]["docid"]): 2, (items[1]["qid"], items[1]["docid"]): 3}
    assert load_exports([out]) == {"Suraj": graded}       # merge_judgments reads it
    assert not errors
    ctx.close()

    # import into a fresh browser profile
    ctx2 = browser.new_context()
    pg2 = ctx2.new_page()
    pg2.goto(url(page_file))
    assert pg2.locator("#count").inner_text() == f"0 of {n} judged"
    pg2.set_input_files("#import", str(out))
    pg2.wait_for_function(f"document.getElementById('count').textContent === '2 of {n} judged'")

    # importing someone else's file is refused
    pg3 = ctx2.new_page()
    msgs = []
    pg3.on("dialog", lambda d: (msgs.append(d.message), d.accept()))
    pg3.goto(url(pages / "judge_Tejas.html"))
    n3 = len(parse_page(pages / "judge_Tejas.html")[1])
    pg3.set_input_files("#import", str(out))
    pg3.wait_for_timeout(300)
    assert msgs and "belongs to Suraj" in msgs[0]
    assert pg3.locator("#count").inner_text() == f"0 of {n3} judged"
    ctx2.close()


def test_time_query_shows_date(pages, browser):
    page_file = pages / "judge_Saksham.html"
    _, items = parse_page(page_file)
    k = next(i for i, it in enumerate(items) if it["date"])
    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.goto(url(page_file))
    for _ in range(k):
        pg.click("#next")
    assert current(pg).get_attribute("data-i") == str(k)
    assert items[k]["date"] in current(pg).locator(".doc-date").inner_text()
    ctx.close()


def test_without_javascript_everything_is_readable(pages, browser):
    page_file = pages / "judge_Swayam.html"
    _, items = parse_page(page_file)
    ctx = browser.new_context(java_script_enabled=False)
    pg = ctx.new_page()
    pg.goto(url(page_file))
    assert pg.locator(".nojs-only").is_visible()
    arts = pg.locator("article.item")
    assert arts.count() == len(items)
    for idx in (0, len(items) - 1):
        a = arts.nth(idx)
        assert a.is_visible()
        assert a.locator(".title").inner_text().strip() and a.locator(".abstract").inner_text().strip()
        assert a.locator(".query").inner_text().strip() and a.locator(".narr").inner_text().strip()
        assert a.locator(".grades").is_hidden()
    ctx.close()


def test_phone_width_has_no_horizontal_scroll(pages, browser):
    ctx = browser.new_context(viewport={"width": 390, "height": 800})
    pg = ctx.new_page()
    pg.goto(url(pages / "practice_Tejas.html"))
    assert pg.evaluate("document.scrollingElement.scrollWidth <= window.innerWidth + 1")
    assert current(pg).locator(".title").is_visible()
    ctx.close()


def test_storage_warning_when_browser_blocks_storage(pages, browser):
    ctx = browser.new_context()
    ctx.add_init_script("Object.defineProperty(window, 'localStorage', {get() { throw new Error('blocked'); }});")
    pg = ctx.new_page()
    pg.goto(url(pages / "judge_Tejas.html"))
    assert pg.locator("#storageWarning").is_visible()
    pg.keyboard.press("1")                                    # grading still works within the tab
    assert pg.locator("#count").inner_text().startswith("1 of ")
    ctx.close()

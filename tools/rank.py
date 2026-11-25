#!/usr/bin/env python3
"""Re-rank every certification by published rules and lay the chart out again.

usage: rank.py <built.html> <out.html> <ranked.csv>

Every per-certification fact (exam format, prerequisite, tier, price, source, status) is read from
data/certs.csv, and the upgrade paths used by rule 3 from data/ladders.txt. This script holds the
rules and the layout only. See CONTRIBUTING.md for what each column means.

Input is the page produced by build.py. Columns (domains) are kept; rows are
recomputed from a score:

    score = FORMAT + 8 * TIER + PREREQ + INTENSITY (+3 if a board/application review)

FORMAT     P practical exam / graded report ............ 30
           X practical + written or interview .......... 26
           S scenario, essay, oral or thesis ........... 22
           E graded practical exercises, no exam ....... 20
           B multiple choice + performance-based items . 16
           Q multiple choice ........................... 12
           C attendance / completion ...................  4
TIER       0 foundation, 1 associate, 2 professional, 3 expert/lead, 4 top of track
           (3 and 4 only count when backed by a required prior cert/experience, a 24h+ exam or a board;
           otherwise the issuer's label is treated as professional)
PREREQ     0 none, 1 recommended experience or a mandatory vendor course (3),
           2 required lower cert or 1-2 yrs (6), 3 3-4 yrs or a chain of two certs (10), 4 5+ yrs (16)
INTENSITY  0 <=1h, 1 ~2h (2), 2 3-4h (5), 3 6-12h (8), 4 24h or longer (11)
           (multi-day take-home exams score the same as 24-48h ones)

BASIS      V  checked against the issuer's page in the November 2026 pass
           K  from the issuer's general, published exam format (not fetched per cert)
           U  issuer page could not be read; tier falls back to the 2024 chart band
"""
import csv, html, os, re, sys
from urllib.parse import urlparse

src_path, out_path, csv_path = sys.argv[1:4]
src = open(src_path, encoding="utf-8").read()

F_PTS = dict(P=30, X=26, S=22, E=20, B=16, Q=12, C=4)
R_PTS = [0, 3, 6, 10, 16]
I_PTS = [0, 2, 5, 8, 11, 11]
F_ZH = dict(P="實作考", X="實作加筆試／面試", S="情境題、論述或口試", E="實作練習審核（無考試）",
            B="選擇題加實作題", Q="選擇題", C="修課結業")
R_ZH = ["無門檻", "僅建議經驗，或須先修官方課程", "須前置證照或 1–2 年經驗", "須 3–4 年經驗或兩層前置證照", "須 5 年以上經驗"]
I_ZH = ["1 小時內", "約 2 小時", "3–4 小時", "6–12 小時", "24–48 小時", "3 天以上（計分同 24–48 小時）"]
T_ZH = ["入門", "初階", "專業", "專家", "頂"]
B_ZH = dict(V="本次已讀取該發證單位官方頁面", K="依發證單位公開的通用考試形式", U="官方頁面讀不到或尚未查")


# ------------------------------------------------------------------ parse the built page
spans = {}
for m in re.finditer(r"\.([\w-]+)\s*\{([^}]*)\}", src):
    s = re.search(r"grid-column:\s*span\s*(\d+)", m.group(2))
    spans[m.group(1)] = int(s.group(1)) if s else 1
a = src.index('<div class="certcontainer">')
body_start = a + len('<div class="certcontainer">')
tok = re.compile(r'<div class="{0,2}(spacer\d*|skilllevelitem)"[^>]*>.*?</div>|<a class="([\w-]+)"[^>]*?>(.*?)</a>|<!--(.*?)-->', re.S)
NC, NR = 47, 27
items, levels = [], []
row = col = 1
pos = body_start
end_container = None
for m in tok.finditer(src, body_start):
    if "</div>" in src[pos:m.start()]:
        end_container = pos
        break
    if m.group(4) is not None:
        pos = m.end()
        continue
    cls = m.group(1) or m.group(2)
    sp = 1 if cls == "skilllevelitem" else spans.get(cls, 1)
    if col + sp - 1 > NC:
        row += 1; col = 1
    if m.group(2):
        items.append(dict(html=m.group(0), cls=cls, label=re.sub(r"<.*?>", "", m.group(3)).strip(), row=row, col=col, span=sp))
    elif cls == "skilllevelitem":
        levels.append((row, m.group(0)))
    col += sp
    if col > NC:
        row += 1; col = 1
    pos = m.end()
assert end_container, "container end not found"


# ------------------------------------------------------------------ data
DDIR = os.path.dirname(os.path.abspath(csv_path))
SEP = " / "
CERTS = {}          # (label, issuer host) -> row of data/certs.csv
with open(os.path.join(DDIR, "certs.csv"), encoding="utf-8", newline="") as f:
    CERT_ROWS = list(csv.DictReader(f))
for _n, _r in enumerate(CERT_ROWS, start=2):
    _k = (_r["label"], _r["issuer_host"])
    if _k in CERTS:
        sys.exit(f"data/certs.csv line {_n}: {_k[0]} ({_k[1]}) is listed twice")
    CERTS[_k] = _r
    if _r["status"] not in ("", "flagged", "soon", "retired"):
        sys.exit(f"data/certs.csv line {_n}: status must be empty, flagged, soon or retired, not {_r['status']!r}")
    if _r["status"] != "retired":
        try:
            assert _r["format"] in F_PTS and 0 <= int(_r["intensity"]) <= 5 and 0 <= int(_r["prereq"]) <= 4
            assert 0 <= int(_r["tier"]) <= 4 and _r["board"] in ("0", "1") and _r["basis"] in B_ZH
        except (AssertionError, ValueError):
            sys.exit(f"data/certs.csv line {_n} ({_r['label']}): format/intensity/prereq/tier/board/basis has a value "
                     "outside the allowed set, see CONTRIBUTING.md")
LADDERS = open(os.path.join(DDIR, "ladders.txt"), encoding="utf-8").read()
OFFICIAL = "官方頁面"

COL_CLS = [(2, 4, "networkitem1"), (6, 6, "iamitem1"), (8, 14, "engineeritem1"), (16, 17, "assetitem1"),
           (19, 27, "mgmtitem1"), (29, 31, "testitem1"), (33, 33, "softwareitem1"), (35, 40, "blueopsitem1"),
           (41, 47, "redopsitem1")]
# certifications the chart did not have: rows of certs.csv that carry a column number
for _r in CERT_ROWS:
    if _r["column"] and _r["status"] != "retired":
        label, col_ = _r["label"], int(_r["column"])
        cls = next(c for lo_, hi_, c in COL_CLS if lo_ <= col_ <= hi_)
        css = ("font-size:0.48vw;" if len(label) > 8 else "") + ("opacity:0.55;border-style:dashed;" if _r["status"] == "soon" else "")
        st = f' style="{css}"' if css else ""
        h = (f'<a class="{cls}"{st} href="{_r["link"]}" tooltiptext="{html.escape(_r["name"], quote=True)}\n    '
             f'" tabindex="0" target="_blank" >{label}</a>')
        items.append(dict(html=h, cls=cls, label=label, row=14, col=col_, span=1))


def _href_host(h):
    m = re.match(r'<a class="[^"]+"(?: style="[^"]*")? href="([^"]*)" (tooltip\w+)="([^"]*)"', h, re.S)
    return m, urlparse(m.group(1)).netloc.replace("www.", "")


for it in items:
    m, host = _href_host(it["html"])
    row_ = CERTS.get((it["label"], host))
    if row_ is None:
        sys.exit(f"{it['label']} ({host}) is on the chart but has no row in data/certs.csv")
    it["data"] = row_
dropped = [i for i in items if i["data"]["status"] == "retired"]
items = [i for i in items if i["data"]["status"] != "retired"]
DISPLAY = {r["label"]: r["display_label"] for r in CERT_ROWS if r["display_label"]}


def attrs(it):
    m, host = _href_host(it["html"])
    href, tipattr, tip = m.groups()
    d = it["data"]
    name = html.unescape(tip.split("\n")[0].strip())
    F, I, R, B, board = d["format"], int(d["intensity"]), int(d["prereq"]), d["basis"], int(d["board"])
    T, tsrc = int(d["tier"]), d["tier_source"] or "官方級別"
    # A tier above "professional" has to be backed by something: a required prior certification or
    # experience (R >= 2), an exam of 24 hours or more (I >= 4), or a board/interview. Otherwise the
    # issuer's own "expert" label counts as professional.
    claimed = T
    if T > 2 and not (R >= 2 or I >= 4 or board):
        T = 2
        tsrc += f"；自稱{T_ZH[claimed]}級，因無強制門檻且考試未達 24 小時，以專業級計"
    score = F_PTS[F] + 8 * T + R_PTS[R] + I_PTS[I] + 3 * board
    return dict(claimed=claimed, href=href, host=host, name=name, F=F, I=I, R=R, T=T, B=B, board=board, tsrc=tsrc, score=score,
                tipattr=tipattr, tip=tip)


for it in items:
    it.update(attrs(it))

# Rule 3 (2026-11-25): inside one issuer's own track, a higher rung never scores below the rung under it.
# Chains live in data/ladders.txt, written low -> high; they only join certifications of the same kind
# (same issuer, same track). "a > b|c" means both b and c sit above a.
_by = {}
for it in items:
    _by.setdefault(it["label"], []).append(it)
PAIRS = []
for _line in [l for l in LADDERS.splitlines() if l.strip() and not l.lstrip().startswith("#")]:
    _rungs = [[x.strip() for x in r.split("|")] for r in _line.split(">")]
    for _lo, _hi in zip(_rungs, _rungs[1:]):
        PAIRS += [(a_, b_) for a_ in _lo for b_ in _hi]
_missing = sorted({l for pr in PAIRS for l in pr if l not in _by})
if _missing:
    print("ladder labels not on chart:", _missing)
lifted = []
for _ in range(10):
    _changed = False
    for a_, b_ in PAIRS:
        if a_ in _by and b_ in _by and len(_by[a_]) == 1 and len(_by[b_]) == 1:
            lo_it, hi_it = _by[a_][0], _by[b_][0]
            if hi_it["score"] < lo_it["score"]:
                hi_it.setdefault("raw_score", hi_it["score"])
                hi_it["score"] = lo_it["score"]
                hi_it["lift"] = a_
                _changed = True
    if not _changed:
        break
lifted = [i for i in items if "lift" in i]
print("rule 3 lifted:", [(i["label"], i["raw_score"], i["score"], i["lift"]) for i in lifted])

lo = min(i["score"] for i in items)
hi = max(i["score"] for i in items)
for it in items:
    it["target"] = max(2, min(NR, NR - round((it["score"] - lo) / (hi - lo) * (NR - 2))))

# ------------------------------------------------------------------ layout
ZONES = [(2, 4), (6, 6), (8, 11), (12, 12), (13, 13), (14, 14), (16, 17), (19, 21), (22, 25), (26, 27),
         (29, 31), (33, 33), (35, 36), (37, 38), (39, 40), (41, 45), (46, 47)]
DOMAINS = [(2, 4), (6, 6), (8, 14), (16, 17), (19, 27), (29, 31), (33, 33), (35, 40), (41, 47)]


def within(col, ranges):
    for lo_, hi_ in ranges:
        if lo_ <= col <= hi_:
            return lo_, hi_
    return col, col


grid = {}           # (row, col) -> item


def free(r, c, sp):
    return 2 <= r <= NR and all((r, c + k) not in grid for k in range(sp))


def put(it, r, c):
    for k in range(it["span"]):
        grid[(r, c + k)] = it
    it["nrow"], it["ncol"] = r, c


def rows_near(t):
    yield t
    for d in range(1, NR):
        for r in (t + d, t - d):
            if 2 <= r <= NR:
                yield r


order = sorted(items, key=lambda i: (-i["span"], -i["score"], i["label"]))
for it in order:
    if it["span"] > 1:                                   # cross-domain boxes keep their columns
        for r in rows_near(it["target"]):
            if free(r, it["col"], it["span"]):
                put(it, r, it["col"]); break
        continue
    zlo, zhi = within(it["col"], ZONES)
    dlo, dhi = within(it["col"], DOMAINS)
    placed = False
    for r in rows_near(it["target"]):
        if abs(r - it["target"]) > 2:
            break
        for c in sorted(range(zlo, zhi + 1), key=lambda c: abs(c - it["col"])):
            if free(r, c, 1):
                put(it, r, c); placed = True; break
        if placed:
            break
    if not placed:                                       # zone is full nearby: use the rest of the domain
        for r in rows_near(it["target"]):
            for c in sorted(range(dlo, dhi + 1), key=lambda c: abs(c - it["col"])):
                if free(r, c, 1):
                    put(it, r, c); placed = True; break
            if placed:
                break
    assert placed, it["label"]

# Rule 3 on the page too: packing can push an equal-score higher rung a row or two below the lower rung.
# Where that happens the two boxes trade places (both stay inside the same domain).
swapped = []
for _ in range(10):
    _changed = False
    for a_, b_ in PAIRS:
        if a_ in _by and b_ in _by and len(_by[a_]) == 1 and len(_by[b_]) == 1:
            lo_it, hi_it = _by[a_][0], _by[b_][0]
            if lo_it["span"] == 1 and hi_it["span"] == 1 and hi_it["nrow"] > lo_it["nrow"] \
                    and within(lo_it["col"], DOMAINS) == within(hi_it["col"], DOMAINS):
                (r1, c1), (r2, c2) = (lo_it["nrow"], lo_it["ncol"]), (hi_it["nrow"], hi_it["ncol"])
                grid[(r1, c1)], grid[(r2, c2)] = hi_it, lo_it
                hi_it["nrow"], hi_it["ncol"], lo_it["nrow"], lo_it["ncol"] = r1, c1, r2, c2
                swapped.append((b_, a_)); _changed = True
    if not _changed:
        break
print("rule 3 swapped on the page:", swapped)
moved_up = []
for _ in range(10):
    _changed = False
    for a_, b_ in PAIRS:                                  # different domains: lift the higher rung to a free cell
        if a_ in _by and b_ in _by and len(_by[a_]) == 1 and len(_by[b_]) == 1:
            lo_it, hi_it = _by[a_][0], _by[b_][0]
            if hi_it["span"] == 1 and hi_it["nrow"] > lo_it["nrow"]:
                done = False
                dlo, dhi = within(hi_it["col"], DOMAINS)
                for r in range(lo_it["nrow"], max(1, lo_it["nrow"] - 3), -1):     # higher rung up, at most two rows above
                    cs = [c for c in sorted(range(dlo, dhi + 1), key=lambda c: abs(c - hi_it["col"])) if free(r, c, 1)]
                    if cs:
                        del grid[(hi_it["nrow"], hi_it["ncol"])]
                        put(hi_it, r, cs[0]); moved_up.append(b_); done = True
                        break
                if not done and lo_it["span"] == 1:                                # otherwise the lower rung moves down
                    dlo, dhi = within(lo_it["col"], DOMAINS)
                    for r in range(hi_it["nrow"], NR + 1):
                        cs = [c for c in sorted(range(dlo, dhi + 1), key=lambda c: abs(c - lo_it["col"])) if free(r, c, 1)]
                        if cs:
                            del grid[(lo_it["nrow"], lo_it["ncol"])]
                            put(lo_it, r, cs[0]); moved_up.append(a_ + " (down)"); done = True
                            break
                _changed = _changed or done
    if not _changed:
        break
print("rule 3 moved up on the page:", moved_up)
still = [(b_, _by[b_][0]["nrow"], a_, _by[a_][0]["nrow"]) for a_, b_ in PAIRS
         if a_ in _by and b_ in _by and len(_by[a_]) == 1 and len(_by[b_]) == 1 and _by[b_][0]["nrow"] > _by[a_][0]["nrow"]]
print("still inverted on the page:", still)

# ------------------------------------------------------------------ emit
def retip(it):
    h = it["html"]
    lab = it["label"]
    d = it["data"]
    if d["display_label"] or d["display_name"]:
        h = h.replace(">" + lab + "</a>", ">" + (d["display_label"] or lab) + "</a>")
        if d["display_name"]:
            h = h.replace(html.escape(it["name"], quote=True), html.escape(d["display_name"], quote=True), 1)
    if d["link"] and d["link"] != it["href"]:
        h = h.replace(it["href"], d["link"], 1)
    basis = f"排序依據：{F_ZH[it['F']]}｜{I_ZH[it['I']]}｜{R_ZH[it['R']]}｜{T_ZH[it['T']]}級（{it['tsrc']}）"
    if it["board"]:
        basis += "｜須審查委員會或面試"
    if "lift" in it:
        basis += f"｜同系列進階證照，原始分數 {it['raw_score']}，依規則不低於 {DISPLAY.get(it['lift'], it['lift'])}"
    flagged = d["status"] == "flagged"
    if flagged:
        if ' style="' in h[:h.index("href=")]:
            h = h.replace(' style="', ' style="opacity:0.55;border-style:dashed;', 1)
        else:
            h = h.replace(" href=", ' style="opacity:0.55;border-style:dashed;" href=', 1)
    if d["price_text"]:
        lines = d["price_text"].split(SEP)

        def swap(m):
            first = m.group(2).split("\n")[0]
            return f' {m.group(1)}="' + first + "".join("\n    " + html.escape(l, quote=True) for l in lines) + '"'
        h = re.sub(r' (tooltip\w+)="([^"]*)"', swap, h, count=1)
        src_line = f"價格來源：{d['confidence'] or OFFICIAL}｜{d['checked']}"
    else:
        src_line = ""
    extra = ("\n    " + html.escape(d["status_note"], quote=True) if flagged else "")
    extra += ("\n    " + html.escape(src_line, quote=True) if src_line else "") + "\n    " + html.escape(basis, quote=True) + "\n    " + html.escape(f"評分 {it['score']}｜{B_ZH[it['B']]}", quote=True)
    # tooltips open toward the centre so the longer text stays on screen
    side = "tooltipleft" if it["ncol"] <= 12 else "tooltipright" if it["ncol"] >= 36 else "tooltiptext"
    return re.sub(r' (tooltip\w+)="([^"]*)"', lambda m: f' {side}="{m.group(2)}{extra}"', h, count=1)


level_rows = {r: h for r, h in levels}
out_rows = []
for r in range(1, NR + 1):
    cells_, c = [], 1
    while c <= NC:
        it = grid.get((r, c))
        if c == 1 and r in level_rows:
            cells_.append(level_rows[r]); c += 1
        elif it:
            cells_.append(retip(it)); c += it["span"]
        else:
            cells_.append('<div class="spacer"></div>'); c += 1
    out_rows.append(f"<!-- Row {r} -->\n                    " + "\n                    ".join(cells_))
new_body = "\n                    " + "\n                    ".join(out_rows) + "\n            "
out = src[:body_start] + new_body + src[end_container:]

n = len(items) - 1
out = re.sub(r"共 \d+ 張證照", f"共 {n} 張證照", out)
out = re.sub(r"共 \d+ 張（原版 481）", f"共 {n} 張（原版 481）", out)

by_b = {b: sum(1 for i in items if i["B"] == b) for b in "VKU"}
n_band = sum(1 for i in items if i["tsrc"].startswith("沿用"))
rules = f"""
<section class="notes">
  <h2>排序規則（2026-11 版）</h2>
  <p>原圖作者沒有公開評分標準。本版改以公開規則計分，分數越高位置越上方；左右欄位（領域）不變。
  滑鼠移到任一張證照上，可以看到它的各項判定與分數。</p>
  <ul>
    <li><strong>考試形式</strong>：實作考 30、實作加筆試或面試 26、情境題／論述／口試 22、實作練習審核 20、選擇題加實作題 16、選擇題 12、修課結業 4。</li>
    <li><strong>官方級別</strong>：入門 0、初階 8、專業 16、專家 24、頂級 32。專家與頂級必須有東西支撐才算數：有強制的前置證照或年資、考試達 24 小時以上、或須經審查委員會或面試，三者至少其一；否則發證單位自稱的級別一律以專業級計。</li>
    <li><strong>報考門檻</strong>：無 0、僅建議經驗或須先修官方課程 3、須前置證照或 1–2 年經驗 6、3–4 年或兩層前置證照 10、5 年以上 16；另須審查委員會或面試加 3。</li>
    <li><strong>考試強度</strong>：1 小時內 0、約 2 小時 2、3–4 小時 5、6–12 小時 8、24 小時以上 11（多日制不再加分）。</li>
    <li><strong>同系列不倒掛</strong>：同一發證單位、同一路線內，進階證照的分數不低於它下面那一階（例如 CREST 的 CPSA → CRT → CCT）。不同路線、不同發證單位之間不套用。被調整的證照，提示文字會顯示原始分數。</li>
  </ul>
  <p>資料來源：{by_b['V']} 張屬於本次已讀取官方頁面的發證單位（多數是讀該單位的代表頁面，不是逐張查證）；{by_b['K']} 張依發證單位公開的通用考試形式判定，本次未讀取官方頁面；
  {by_b['U']} 張的官方頁面讀不到或尚未查，考試形式暫用該單位的預設值。另有 {n_band} 張無法從官方名稱判定級別，級別沿用 2024 原圖所在區段。
  同分或該列已滿時會落在相鄰列。
  本次另移除 {len(dropped)} 張停考、退役或已不在官方目錄的證照：{'、'.join(d['label'] for d in dropped)}（各自的原因與來源見 data/retired.csv）；
  另有 {sum(1 for i in items if i['data']['status'] == 'flagged')} 張現況有疑問，以虛線框標示並在提示文字說明；
  並補上官方已有、原圖未收的 {sum(1 for r in CERT_ROWS if r['column'] and r['status'] != 'retired')} 張。
  價格與費用已全部改為 2026 年 11 月查到的資料；官方未公開或讀不到的標示「無價格資訊」，不沿用 2024 年舊價。</p>
</section>
"""
out = out.replace('<section class="notes">', rules + '<section class="notes">', 1)
open(out_path, "w", encoding="utf-8").write(out)

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow("label name host format intensity prereq tier_claimed tier tier_source board score basis old_row new_row col url".split())
    for i in sorted(items, key=lambda i: -i["score"]):
        w.writerow([i["label"], i["name"], i["host"], i["F"], i["I"], i["R"], i["claimed"], i["T"], i["tsrc"], i["board"], i["score"],
                    i["B"], i["row"], i["nrow"], i["ncol"], i["href"]])
ddir = DDIR
with open(os.path.join(ddir, "prices.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["label", "name", "price_text", "price_kind", "source_url", "checked", "confidence"])
    for i in sorted(items, key=lambda i: i["label"]):
        d = i["data"]
        if d["price_text"]:
            w.writerow([i["label"], i["name"], d["price_text"], d["price_kind"], d["source_url"], d["checked"], d["confidence"]])
with open(os.path.join(ddir, "flagged.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["label", "name", "note"])
    for i in items:
        if i["data"]["status"] == "flagged":
            w.writerow([i["label"], i["name"], i["data"]["status_note"]])
with open(os.path.join(ddir, "retired.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["label", "name", "reason", "source", "checked", "confidence"])
    for d_ in dropped:
        d = d_["data"]
        w.writerow([d["label"], d["name"], d["status_note"], d["source_url"], d["checked"], d["confidence"]])
moved = sum(1 for i in items if i["nrow"] != i["row"])
off = sum(1 for i in items if i["nrow"] != i["target"])
print(f"items {len(items)} | score {lo}-{hi} | basis {by_b} | moved rows {moved} | placed off-target {off} | dropped {len(dropped)}")
print("tier from 2024 band:", sum(1 for i in items if i["tsrc"].startswith("沿用")))

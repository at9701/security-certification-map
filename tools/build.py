#!/usr/bin/env python3
"""Build the November 2026 community update of Paul Jerimy's Security
Certification Roadmap from the July 2024 source HTML.

usage: build.py <orig.html> <cells.json> <out.html>
"""
import json, re, sys, html

orig_path, cells_path, out_path = sys.argv[1:4]
src = open(orig_path, encoding="utf-8").read()
cells = json.load(open(cells_path))

VENDOR_PAGES = {
    "offsec": "https://www.offsec.com/courses",
    "htb": "https://help.hackthebox.com/en/articles/12741732-academy-certifications",
    "tcm": "https://certifications.tcm-sec.com/product-category/exams",
    "thm": "https://tryhackme.com/resources/blog/cyber-security-certification-roadmap-2026",
    "pan": "https://www.paloaltonetworks.com/services/education/certification",
    "giac": "https://www.giac.org/pricing/",
}

ZONE_CLASS = [
    (2, 4, "networkitem1"), (6, 6, "iamitem1"), (8, 14, "engineeritem1"),
    (16, 17, "assetitem1"), (19, 27, "mgmtitem1"), (29, 31, "testitem1"),
    (33, 33, "softwareitem1"), (35, 40, "blueopsitem1"), (41, 47, "redopsitem1"),
]


def cls_for(col):
    for lo, hi, c in ZONE_CLASS:
        if lo <= col <= hi:
            return c
    raise ValueError(col)


def tip_attr(col):
    if col <= 4:
        return "tooltipleft"
    if col >= 45:
        return "tooltipright"
    return "tooltiptext"


def anchor(cls, href, tipattr, lines, label, style=""):
    tip = "\n    ".join(html.escape(l, quote=True) for l in lines)
    st = f' style="{style}"' if style else ""
    return (f'<a class="{cls}"{st} href="{href}" {tipattr}="{tip}" '
            f'tabindex="0" target="_blank" >{label}</a>')


def find(label, row=None):
    hits = [c for c in cells if c["label"] == label and (row is None or c["row"] == row)]
    if len(hits) != 1:
        raise SystemExit(f"label {label!r} row={row}: {len(hits)} matches")
    return hits[0]


def slot(row, col):
    hits = [c for c in cells if c["row"] == row and c["col"] == col]
    if len(hits) != 1 or hits[0]["cls"] != "spacer" or hits[0]["span"] != 1:
        raise SystemExit(f"slot r{row}c{col} is not a free single cell: {hits}")
    return hits[0]


edits = []      # (off, end, newtext)
log = {"renamed": [], "added": [], "removed": [], "price": []}

# ---------------------------------------------------------------- in-place
# (old label, row or None, new label, href or None (= keep), tooltip lines, note)
REPLACE = [
    ("CASP+", None, "<b>SecurityX</b>",
     "https://www.comptia.org/en-us/certifications/securityx/",
     ["CompTIA SecurityX (formerly CASP+)", "Exam CAS-005 since Dec 17, 2024"],
     "CASP+ → SecurityX（CompTIA，2024-12-17 起，考試代碼 CAS-005）"),
    ("OSCP", None, "OSCP+", "https://www.offsec.com/pwk-oscp",
     ["OffSec Certified Professional (OSCP / OSCP+)", "$1,749 course + exam bundle",
      "$1,699 exam only", "OSCP+ expires after 3 years; OSCP is for life"],
     "OSCP → OSCP+（OffSec，2024-11-01 起；OSCP+ 三年效期，OSCP 終身）"),
    ("HTB CBBH", None, "HTB CWES", "https://www.hackthebox.com/blog/htb-cwes-announcement",
     ["Hack The Box Certified Web Exploitation Specialist", "Formerly HTB CBBH (renamed Oct 1, 2025)",
      "Exam voucher via HTB Academy subscription"],
     "HTB CBBH → HTB CWES（2025-10-01 更名）"),
    ("PJMR", None, "PMRP", "https://certifications.tcm-sec.com/pmrp/",
     ["TCM Security Practical Malware Research Professional", "Formerly PJMR (renamed Nov 2024)", "$399 exam"],
     "PJMR → PMRP（TCM Security，2024-11 更名並改列專業級）"),
    ("PNPT", None, "PNPT", None,
     ["TCM Security Practical Network Penetration Tester", "$399 exam"],
     None),
    ("CRTO II", None, "CRTL", "https://training.zeropointsecurity.co.uk/pages/exams",
     ["Zero-Point Security Certified Red Team Lead", "Red Team Ops II exam", "Zero-Point joined Fortra in 2026"],
     "CRTO II → CRTL（標籤更正為正式證照名 Certified Red Team Lead）"),
    ("SC-400", None, "SC-401",
     "https://learn.microsoft.com/en-us/credentials/certifications/information-security-administrator/",
     ["Microsoft Certified: Information Security Administrator Associate", "Exam SC-401; replaced SC-400 in 2025",
      "Price varies by country"],
     "SC-400 → SC-401（Microsoft，2025 年取代）"),
    ("AZ-500", None, "SC-500", "https://learn.microsoft.com/certifications/retired-courses",
     ["Microsoft SC-500: Build a secure Cloud and AI solution", "Successor to AZ-500 (retired Aug 31, 2026)",
      "Price varies by country"],
     "AZ-500 → SC-500（AZ-500 已於 2026-08-31 停考）"),
    ("PCNSE", None, "PA NGFW", VENDOR_PAGES["pan"],
     ["Palo Alto Networks Certified Next-Generation Firewall Engineer",
      "Role-based successor to PCNSE (retired Jul 31, 2025)"],
     "PCNSE → Next-Generation Firewall Engineer（PCNSE 2025-07-31 停考）"),
    ("PCNSA", None, "PA NetSec", VENDOR_PAGES["pan"],
     ["Palo Alto Networks Certified Network Security Professional", "Role-based successor to PCNSA"],
     "PCNSA → Network Security Professional"),
    ("PCCET", None, "PA Cyber", VENDOR_PAGES["pan"],
     ["Palo Alto Networks Certified Cybersecurity Practitioner", "Foundational level; replaces PCCET"],
     "PCCET → Cybersecurity Practitioner"),
    ("PCSAE", None, "PA XSOAR", VENDOR_PAGES["pan"],
     ["Palo Alto Networks Certified XSOAR Engineer", "Role-based successor to PCSAE"],
     "PCSAE → XSOAR Engineer"),
    ("PCCSE", None, "PA Cloud", VENDOR_PAGES["pan"],
     ["Palo Alto Networks Certified Cloud Security Engineer", "Role-based successor to PCCSE"],
     "PCCSE → Cloud Security Engineer"),
    ("PCDRA", None, "PA XDR", VENDOR_PAGES["pan"],
     ["Palo Alto Networks Certified XDR Analyst", "Role-based successor to PCDRA"],
     "PCDRA → XDR Analyst"),
    ("Cisco COP", None, "CCNP Cyber", None,
     ["Cisco CCNP Cybersecurity", "Formerly CyberOps Professional (renamed Feb 3, 2026)", "Two exams"],
     "Cisco CyberOps Professional → CCNP Cybersecurity（2026-02-03）"),
    ("Cisco COA", None, "CCNA Cyber", None,
     ["Cisco CCNA Cybersecurity", "Formerly CyberOps Associate (renamed Feb 3, 2026)", "Exam 200-201"],
     "Cisco CyberOps Associate → CCNA Cybersecurity（2026-02-03）"),
    ("DevNet Pro", None, "CCNP Auto", None,
     ["Cisco CCNP Automation", "Formerly DevNet Professional (renamed Feb 3, 2026)", "Two exams"],
     "Cisco DevNet Professional → CCNP Automation（2026-02-03）"),
    ("DevNet A", None, "CCNA Auto", None,
     ["Cisco CCNA Automation", "Formerly DevNet Associate (renamed Feb 3, 2026)", "Exam 200-901"],
     "Cisco DevNet Associate → CCNA Automation（2026-02-03）"),
    ("CC", None, "CC", None,
     ["ISC2 Certified in Cybersecurity", "$199 exam", "Free-exam programme closed to new enrolments May 20, 2026"],
     None),
]

for old, row, new, href, lines, note in REPLACE:
    c = find(old, row)
    seg = src[c["off"]:c["end"]]
    m = re.match(r'<a class="([^"]+)"((?: style="[^"]*")?) href="([^"]*)" (tooltip\w+)="', seg)
    if not m:
        raise SystemExit(f"cannot parse anchor for {old}: {seg[:80]}")
    cls, style, old_href, tipattr = m.groups()
    style_val = re.search(r'style="([^"]*)"', style).group(1) if style else ""
    edits.append((c["off"], c["end"], anchor(cls, href or old_href, tipattr, lines, new, style_val)))
    if note:
        log["renamed"].append(note)

log["price"].append("PNPT：$299 → $399")
log["price"].append("ISC2 CC：免費 → $199（免費方案 2026-05-20 停止新報名）")

# ---------------------------------------------------------------- removals
REMOVE = [
    ("MS-100", "MS-100（2023-09-30 停考；後繼的 MS-102 也排定 2026-11-30 停考，故不遞補）"),
    ("AZ-220", "AZ-220 Azure IoT Developer（2023-07-31 停考）"),
    ("CSX-P", "ISACA CSX-P（ISACA 已列為 Retired Credential；ISACA CCOA 原圖已有）"),
]
SPACER = '<div class="spacer"></div>'
JOIN = "\n                    "
placed = {}          # (off, end, col0, span) -> {col: anchor html}
for label, note in REMOVE:
    c = find(label)
    placed[(c["off"], c["end"], c["col"], c["span"])] = {}     # freed; may be reused below
    log["removed"].append(note)


def place(row, col, html_anchor):
    """Put an anchor into a free cell: a spacer (of any width) or a cell freed by REMOVE."""
    hits = [c for c in cells if c["row"] == row and c["col"] <= col < c["col"] + c["span"]]
    if len(hits) != 1:
        raise SystemExit(f"r{row}c{col}: {len(hits)} cells")
    c = hits[0]
    key = (c["off"], c["end"], c["col"], c["span"])
    if not c["cls"].startswith("spacer") and key not in placed:
        raise SystemExit(f"r{row}c{col} is occupied by {c['label']}")
    if col in placed.setdefault(key, {}):
        raise SystemExit(f"r{row}c{col} placed twice")
    placed[key][col] = html_anchor


# ---------------------------------------------------------------- additions
# (row, col, label, href, tooltip lines[, {"cls": ..., "style": ...}])
ADD = [
    (19, 36, "OSTH", VENDOR_PAGES["offsec"], ["OffSec Threat Hunter", "TH-200 course + exam"]),
    (17, 35, "OSIR", VENDOR_PAGES["offsec"], ["OffSec Incident Responder", "IR-200 course + exam"]),
    (27, 16, "OSCC", VENDOR_PAGES["offsec"], ["OffSec CyberCore Certified (OSCC-SEC)", "SEC-100 course + exam"],
     {"cls": "mgmtitem1"}),
    (6, 44, "OSAI", VENDOR_PAGES["offsec"], ["OffSec AI Red Teamer", "AI-300 course + exam"]),
    (9, 43, "HTB CAPE", VENDOR_PAGES["htb"],
     ["Hack The Box Certified Active Directory Pentesting Expert", "Exam voucher via HTB Academy subscription"]),
    (10, 42, "HTB CWPE", VENDOR_PAGES["htb"],
     ["Hack The Box Certified Wi-Fi Pentesting Expert", "Exam voucher via HTB Academy subscription"]),
    (11, 44, "HTB COAE", VENDOR_PAGES["htb"],
     ["Hack The Box Certified Offensive AI Expert", "Exam voucher via HTB Academy subscription"]),
    (10, 36, "HTB CDEP", VENDOR_PAGES["htb"],
     ["Hack The Box Certified Detection Engineering Principal", "Exam voucher via HTB Academy subscription"]),
    (23, 41, "PJPT", VENDOR_PAGES["tcm"], ["TCM Security Practical Junior Penetration Tester", "$199 exam"]),
    (23, 35, "PSAA", VENDOR_PAGES["tcm"], ["TCM Security Practical SOC Analyst Associate", "$199 exam"]),
    (24, 41, "PWPA", VENDOR_PAGES["tcm"], ["TCM Security Practical Web Pentest Associate", "$199 exam"]),
    (15, 41, "PWPP", VENDOR_PAGES["tcm"], ["TCM Security Practical Web Pentest Professional", "$399 exam"]),
    (24, 42, "PAPA", VENDOR_PAGES["tcm"], ["TCM Security Practical AI Pentest Associate", "$199 exam"]),
    (25, 40, "THM SAL1", VENDOR_PAGES["thm"],
     ["TryHackMe Security Analyst Level 1", "Live SOC simulator with graded incident reports"]),
    (26, 35, "THM SEC1", VENDOR_PAGES["thm"],
     ["TryHackMe Cyber Security 101 Certification", "Practical assessment"]),
    (23, 45, "THM PT1", VENDOR_PAGES["thm"],
     ["TryHackMe Junior Penetration Tester", "48-hour practical exam + report"]),
    (22, 38, "THM SAL2", VENDOR_PAGES["thm"],
     ["TryHackMe Security Analyst Level 2", "Multi-stage SOC investigation scenarios"]),
    (22, 21, "SecAI+", "https://www.comptia.org/en-us/certifications/secai/",
     ["CompTIA SecAI+", "Exam CY0-001, launched Feb 17, 2026"]),
    (6, 24, "AAISM", "https://www.isaca.org/credentialing/aaism",
     ["ISACA Advanced in AI Security Management", "$599 exam ($459 members)", "Active CISM or CISSP required"]),
    (8, 25, "AAIR", "https://www.isaca.org/credentialing/aair", ["ISACA Advanced in AI Risk"]),
    (8, 30, "AAIA", "https://www.isaca.org/credentialing/aaia", ["ISACA Advanced in AI Audit"]),
    (12, 44, "GOAA", VENDOR_PAGES["giac"],
     ["GIAC Offensive AI Analyst", "$999 exam", "SANS SEC535 recommended"]),
    (12, 14, "GAIPS", "https://www.giac.org/certifications/ai-security-platform-security-gaips",
     ["GIAC AI Platform Security", "$999 exam", "SANS SEC545 recommended"]),
    (12, 35, "GASAE", "https://www.giac.org/certifications/ai-security-automation-engineer-gasae",
     ["GIAC AI Security Automation Engineer", "$999 exam", "SANS SEC598 recommended"]),
    (13, 39, "GSOA", VENDOR_PAGES["giac"],
     ["GIAC Strategic OSINT Analyst", "SANS SEC587 recommended"]),
]
for row, col, label, href, lines, *extra in ADD:
    opt = extra[0] if extra else {}
    place(row, col, anchor(opt.get("cls") or cls_for(col), href, tip_attr(col), lines, label, opt.get("style", "")))
    log["added"].append(f"{label} — {lines[0]}")

# HTB CJCA goes on the blue/red boundary of the eJPT row. That row has no free cell
# there, so the five certs to its right slide one column into the free cell at col 46.
CJCA = anchor("redopsitem1", VENDOR_PAGES["htb"], "tooltiptext",
              ["Hack The Box Certified Junior Cybersecurity Associate", "Covers both offensive and defensive work",
               "Exam voucher via HTB Academy subscription"], "HTB CJCA",
              "background:linear-gradient(90deg,var(--blue) 50%,var(--red) 50%);")
first = find("CSTM", 20)
assert first["col"] == 41, first
gap = slot(20, 46)
edits.append((first["off"], first["off"], CJCA + JOIN))                 # insert before CSTM
ws = len(src[:gap["off"]]) - len(src[:gap["off"]].rstrip())
edits.append((gap["off"] - ws, gap["end"], ""))                          # drop the spacer it displaces
log["added"].append("HTB CJCA — Hack The Box Certified Junior Cybersecurity Associate")

# ---------------------------------------------------------------- Taiwan
IPAS = "https://www.ipas.org.tw/ISE/AbilityIndex.aspx"
NICS = "https://ctts.nics.nat.gov.tw/"
TW = [
    (27, 22, "iPAS 初級", IPAS,
     ["iPAS 資訊安全工程師 初級能力鑑定", "Taiwan MOEA iPAS Information Security Engineer (Basic)"], "word-break:keep-all;"),
    (26, 17, "資安職能 核心", NICS,
     ["資通安全職能評量證書：核心科目「資通安全概論」", "Taiwan NICS cybersecurity competency certificate (core)",
      "3-day course NT$8,000 incl. one assessment (2024 rate)"], "font-size:0.5vw;"),
    (24, 20, "iPAS 中級", IPAS,
     ["iPAS 資訊安全工程師 中級能力鑑定", "Taiwan MOEA iPAS Information Security Engineer (Intermediate)",
      "2 papers; NT$1,500 per sitting (NT$1,000 individual rate)"], "word-break:keep-all;"),
    (24, 21, "資安職能 專業", NICS,
     ["資通安全職能評量證書：專業科目", "Taiwan NICS cybersecurity competency certificate (professional subjects)",
      "Requires the core 資通安全概論 certificate", "3-day course NT$8,000 incl. one assessment (2024 rate)"],
     "font-size:0.5vw;"),
]
log["taiwan"] = []
for row, col, label, href, lines, style in TW:
    place(row, col, anchor("mgmtitem1", href, tip_attr(col), lines, label, style))
    log["taiwan"].append(f"{label.replace(' ', '')} — {lines[0]}")

for (off, end, col0, span), anchors in placed.items():
    edits.append((off, end, JOIN.join(anchors.get(col0 + i, SPACER) for i in range(span))))

# apply back to front so offsets stay valid
edits.sort(key=lambda e: -e[0])
offs = [e[0] for e in edits]
assert len(set(offs)) == len(offs), "overlapping edits"
out = src
for off, end, new in edits:
    out = out[:off] + new + out[end:]

# ---------------------------------------------------------------- global text fixes
n_giac = out.count("$979")
out = out.replace("$979", "$999")
log["price"].append(f"GIAC Practitioner 考試費：$979 → $999（共 {n_giac} 處）")
n_isc = out.count("(ISC)2")
out = out.replace("(ISC)2", "ISC2")
n_off = out.count('="Offensive Security ')
out = out.replace('="Offensive Security ', '="OffSec ')
log["renamed"].append(f"提示文字：Offensive Security → OffSec（{n_off} 處）、(ISC)2 → ISC2（{n_isc} 處）")

# malformed tag in the source
out = out.replace('<div class=""spacer"></div>', '<div class="spacer"></div>')

# ---------------------------------------------------------------- 中文化
DOMAINS_ZH = [
    ("Communication and Network Security", "通訊與網路安全",
     "通訊與網路安全：保護通訊管道與網路的能力，涵蓋網路架構、傳輸協定、網路設備與遠端存取的安全設計與維運。"),
    ("IAM", "身分\n存取",
     "身分與存取管理：身分識別、驗證、授權與帳號生命週期管理，以及針對人員入口的攻擊與防護。"),
    ("Security Architecture and Engineering", "安全架構與工程",
     "安全架構與工程：安全設計原則、系統與雲端架構、作業系統、密碼學，以及工控與物聯網環境的安全工程。"),
    ("Asset Security", "資產安全",
     "資產安全：資料的蒐集、儲存、維護、保存與銷毀，包含資料分類、隱私保護與實體資產保護。"),
    ("Security and Risk Management", "安全與風險管理",
     "安全與風險管理：資安治理、風險評估、法規遵循、營運持續、資安意識，以及專案與服務管理。"),
    ("Security Assessment and Testing", "安全評估與測試",
     "安全評估與測試：稽核、控制措施查核、弱點評估與持續監控，用來找出系統弱點並驗證防護是否有效。"),
    ("Software Security", "軟體\n安全",
     "軟體安全：安全的軟體開發生命週期、安全程式設計、應用程式安全測試與 DevSecOps。"),
    ("Security Operations", "安全維運",
     "安全維運：監控與偵測、事件處理、數位鑑識、威脅情資，以及滲透測試、紅隊與漏洞利用。"),
]
for en, zh, tip in DOMAINS_ZH:
    pat = re.compile(r'(<div class="domaintitle" style="[^"]*" )(tooltiptexttitle(?:left)?)="[^"]*">' + re.escape(en) + "</div>")
    out, n = pat.subn(lambda m: f'{m.group(1)}{m.group(2)}="     {tip}">{zh}</div>', out)
    assert n == 1, en
for en, zh in [("Cloud/SysOps", "雲端／系統維運"), ("ICS/IoT", "工控"), ("Forensics", "數位鑑識"),
               ("Incident Handling", "事件處理"), ("Penetration Testing", "滲透測試"), ("Exploitation", "漏洞利用")]:
    assert f">{en}</div>" in out, en
    out = out.replace(f">{en}</div>", f">{zh}</div>")
for en, zh in [("Expert", "專\n家"), ("Intermediate", "中\n階"), ("Beginner", "入\n門")]:
    assert f">{en}</span></div>" in out, en
    out = out.replace(f">{en}</span></div>", f">{zh}</span></div>")

# 提示文字的常見片語（證照名稱維持官方英文）
PHRASES = [
    (r"^(~?[\$£€][\d,\.]+(?:-[\$£€]?[\d,\.]+)?\+?) [Ee]xam$", r"考試費 \1"),
    (r"^(~?[\$£€][\d,\.]+) (?:two|2) exams$", r"兩科考試共 \1"),
    (r"^(~?[\$£€][\d,\.]+) (?:for )?(\d+) exams$", r"\2 科考試共 \1"),
    (r"^(~?[\$£€][\d,\.]+) written exam$", r"筆試 \1"),
    (r"^(~?[\$£€][\d,\.]+) practical exam$", r"實作考試 \1"),
    (r"^(~?[\$£€][\d,\.]+) (?:labs?|[Hh]ands-on [Ll]ab)$", r"實作考試 \1"),
    (r"^(~?[\$£€][\d,\.]+) exam (?:&|and) lab$", r"筆試加實作 \1"),
    (r"^(~?[\$£€][\d,\.]+) course exam$", r"課程含考試 \1"),
    (r"^(~?[\$£€][\d,\.]+) course \+ exam$", r"課程加考試 \1"),
    (r"^(~?[\$£€][\d,\.]+) course$", r"課程 \1"),
    (r"^(~?[\$£€][\d,\.]+) certification programme$", r"認證課程 \1"),
    (r"^(~?[\$£€][\d,\.]+) [Ii]nterview$", r"面試審查 \1"),
    (r"^(~?[\$£€][\d,\.]+) annual sub(?:scription)?$", r"年訂閱 \1"),
    (r"^(~?[\$£€][\d,\.]+) exam \((~?[\$£€][\d,\.]+) members\)$", r"考試費 \1（會員 \2）"),
    (r"^(\d+)% practical\. No expiry\.$", r"\1% 實作，證照永久有效"),
    (r"^SANS course (?:recommended|encouraged)$", "建議搭配 SANS 課程"),
    (r"^SANS (SEC\d+) recommended$", r"建議搭配 SANS \1"),
    (r"^(?:Branded )?[Cc]ourse [Rr]equired$", "須修官方課程"),
    (r"^Application essay$", "須提交申請論述"),
    (r"^Application(?: also)? req\.?$", "須另外申請審查"),
    (r"^Learning subscription required$", "須訂閱學習方案"),
    (r"^Exam voucher via HTB Academy subscription$", "考試券隨 HTB Academy 訂閱方案提供"),
    (r"^Price varies by country$", "價格依國家而異"),
    (r"^Unknown exam cost$", "考試費用不明"),
    (r"^Two exams$", "兩科考試"),
    (r"^Exam and training bundled$", "考試與課程綁售"),
    (r"^[Pp]lus travel$", "另需差旅費"),
    (r"^In person in the UK$", "須至英國現場應考"),
    (r"^Hands on exam in UK$", "須至英國現場實作考"),
    (r"^(\d+) exam attempts? included$", r"含 \1 次考試機會"),
    (r"^Active CISM or CISSP required$", "須持有有效的 CISM 或 CISSP"),
    (r"^Covers both offensive and defensive work$", "同時涵蓋攻擊與防禦"),
]
PHRASES = [(re.compile(p), r) for p, r in PHRASES]
n_tip = n_tip_zh = 0


def tip_zh(m):
    global n_tip, n_tip_zh
    lines = m.group(2).split("\n")
    for i in range(1, len(lines)):
        t = html.unescape(lines[i].strip())
        if not t:
            continue
        n_tip += 1
        for pat, repl in PHRASES:
            if pat.match(t):
                lines[i] = "    " + html.escape(pat.sub(repl, t), quote=True)
                n_tip_zh += 1
                break
    return f'{m.group(1)}="' + "\n".join(lines) + '"'


a0 = out.index('<div class="certcontainer">')
out = out[:a0] + re.sub(r'(tooltip(?:text|left|right))="([^"]*)"', tip_zh, out[a0:])

# ---------------------------------------------------------------- page chrome
a = out.index('<div class="certcontainer">')
n_cert = len(re.findall(r"<a class=", out[a:])) - 1      # minus the "Programming Language" box
out = out.replace("481 certifications listed | July 2024",
                  f"共 {n_cert} 張證照｜2026 年 11 月（非官方版）")

# scale with the viewport width only, so the chart always fits a narrow panel
out = out.replace("vmax", "vw")
# the static PNG fallback is a remote image of the 2022 chart; always show the live chart
out = re.sub(r'<div id="static">.*?</div>', "", out, count=1, flags=re.S)
out = re.sub(r"@media screen and \(max-width: 897px\) \{.*?\n    \}\n", "", out, count=1, flags=re.S)
out = out.replace(
    '<div style="text-align:left;font-size:200%;font-weight:500;padding-bottom:0.2vw;">Security Certification Roadmap',
    '<div style="text-align:left;font-size:1.5vw;line-height:1.8vw;height:1.8vw;font-weight:500;white-space:nowrap;position:relative;top:-2.6vw;">資安證照地圖'
    ' <span style="font-size:50%;font-weight:400;color:#666;">依公開規則重新排序｜衍生自 Paul Jerimy 的 Security Certification Roadmap｜2026 年 11 月</span>')


def ul(items):
    return "<ul>" + "".join(f"<li>{html.escape(i)}</li>" for i in items) + "</ul>"


notes = f"""
<section class="notes">
  <h2>關於這個版本</h2>
  <p>原圖作者為 Paul Jerimy（<a href="https://pauljerimy.com/security-certification-roadmap/" target="_blank">pauljerimy.com/security-certification-roadmap</a>，
  原始碼 <a href="https://github.com/PaulJerimy/SecCertRoadmap" target="_blank">PaulJerimy/SecCertRoadmap</a>），最後一次內容更新是 2024 年 7 月。
  本頁是<strong>非官方衍生版</strong>：沿用原版的版面與領域分欄，更新了 2024-07 之後的證照變動，並把難度位置依上方規則全部重排，
  所以上下位置<strong>不是</strong>原作者的評級；與原作者無關，也未經其背書。
  依原授權 <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank">CC BY-SA 4.0</a> 釋出。</p>
  <p>共 {n_cert} 張（原版 481）。未列在下方的證照，其連結與價格多數仍是 2024 年 7 月的內容，尚未逐一重驗。</p>
  <h3>更名／取代（{len(log['renamed'])}）</h3>{ul(log['renamed'])}
  <h3>新增（{len(log['added'])}）</h3>{ul(log['added'])}
  <h3>台灣證照（{len(log['taiwan'])}）</h3>{ul(log['taiwan'])}
  <h3>移除（{len(log['removed'])}）</h3>{ul(log['removed'])}
  <h3>價格</h3>{ul(log['price'])}
</section>
"""

page_css = """
<style>
  html { color-scheme: light; }
  body { margin: 0; background: #ffffff; color: #323232;
         font-family: "Segoe UI", "Calibri", Tahoma, "Geneva", Verdana, "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif; }
  .chartwrap { position: relative; overflow: hidden; }
  .skilllevelitem { transform: none !important; justify-items: center !important; align-items: center !important; line-height: 130%; }
  #interactive { display: block !important; float: none; margin: 3.6vw 0 0 1vw; }
  .certcontainer { top: 7.4vw !important; }
  .notes { max-width: 900px; margin: 0 auto; padding: 24px 20px 48px; font-size: 15px; line-height: 1.7; }
  .notes h2 { font-size: 20px; margin: 0 0 8px; }
  .notes h3 { font-size: 16px; margin: 20px 0 4px; }
  .notes ul { margin: 4px 0; padding-left: 22px; }
  .notes a { color: #2e5688; }

  /* Mobile: scrollable chart */
  @media (max-width: 1024px) {
    .chartwrap { overflow-x: auto !important; overflow-y: hidden; -webkit-overflow-scrolling: touch; }
    .notes { padding: 20px 16px 40px; font-size: 14px; }
    .notes h2 { font-size: 18px; }
    .notes h3 { font-size: 15px; }
  }

  /* Touch: show tooltip on tap (focus) */
  [tooltiptext]:focus:before,
  [tooltipleft]:focus:before,
  [tooltipright]:focus:before { display: block; z-index: 10; }

  /* Swipe hint */
  .mobile-hint { display: none; text-align: center; padding: 10px 16px; background: #f0f4f8; color: #666;
                 font-size: 13px; line-height: 1.5; border-bottom: 1px solid #e0e4e8; }
  @media (max-width: 1024px) { .mobile-hint { display: block; } }
</style>
"""

mobile_js = """
<script>
(function() {
  var chart = document.getElementById('interactive');
  if (!chart) return;
  var MIN_W = 1200;
  function adjust() {
    var vw = window.innerWidth;
    if (vw < 1024) {
      chart.style.zoom = (MIN_W / vw).toFixed(3);
    } else {
      chart.style.zoom = '';
    }
  }
  adjust();
  window.addEventListener('resize', adjust);

  // dismiss tooltip on tap elsewhere
  document.addEventListener('click', function(e) {
    if (!e.target.closest('[tooltiptext],[tooltipleft],[tooltipright]')) {
      var f = document.activeElement;
      if (f && (f.hasAttribute('tooltiptext') || f.hasAttribute('tooltipleft') || f.hasAttribute('tooltipright')))
        f.blur();
    }
  });

  // hide swipe hint after first scroll
  var wrap = document.querySelector('.chartwrap');
  var hint = document.querySelector('.mobile-hint');
  if (wrap && hint) {
    wrap.addEventListener('scroll', function() { hint.style.display = 'none'; }, {once: true});
  }
})();
</script>
"""

doc = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>資安證照地圖 Security Certification Roadmap（2026-11 非官方更新版）</title>
{page_css}
</head>
<body>
<div class="mobile-hint">← 左右滑動查看完整地圖 →　｜　點擊證照可顯示詳細資訊</div>
<div class="chartwrap">
{out}
</div>
{notes}
{mobile_js}
</body>
</html>
"""
open(out_path, "w", encoding="utf-8").write(doc)
print("certs:", n_cert, "| edits:", len(edits), "| bytes:", len(doc), "| tooltip lines zh:", n_tip_zh, "/", n_tip)
for k, v in log.items():
    print(k, len(v))

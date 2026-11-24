#!/usr/bin/env python3
"""Re-rank every certification by published rules and lay the chart out again.

usage: rank.py <built.html> <out.html> <ranked.csv>

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
PREREQ     0 none, 1 recommended experience or a mandatory vendor course (3),
           2 required lower cert or 1-2 yrs (6), 3 3-4 yrs or a chain of two certs (10), 4 5+ yrs (16)
INTENSITY  0 <=1h, 1 ~2h (2), 2 3-4h (5), 3 6-12h (8), 4 24h or longer (11)
           (multi-day take-home exams score the same as 24-48h ones)

BASIS      V  checked against the issuer's page in the November 2026 pass
           K  from the issuer's general, published exam format (not fetched per cert)
           U  issuer page could not be read; tier falls back to the 2024 chart band
"""
import csv, html, re, sys
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

# ------------------------------------------------------------------ issuer defaults
# host -> (format, intensity, prereq, basis)
HOST = {
    "giac.org": ("B", 2, 1, "K"), "mile2.com": ("Q", 1, 0, "K"), "mosse-institute.com": ("E", 3, 0, "V"),
    "crest-approved.org": ("X", 2, 1, "K"), "exin.com": ("Q", 1, 0, "U"), "embed.exin.totalservices.io": ("Q", 1, 0, "U"),
    "gaqm.org": ("Q", 1, 0, "V"), "eccouncil.org": ("Q", 2, 1, "K"), "cert.eccouncil.org": ("Q", 2, 1, "K"),
    "ciso.eccouncil.org": ("Q", 2, 1, "K"), "seco-institute.org": ("Q", 1, 0, "U"),
    "training.fortinet.com": ("Q", 1, 0, "K"), "comptia.org": ("B", 1, 1, "K"), "cisco.com": ("Q", 1, 0, "K"),
    "itgovernance.co.uk": ("Q", 1, 1, "V"), "isaca.org": ("Q", 2, 4, "K"), "cybersecurity.isaca.org": ("Q", 2, 4, "K"),
    "identitymanagementinstitute.org": ("Q", 1, 1, "V"), "secops.group": ("P", 2, 0, "K"),
    "pecb.com": ("Q", 2, 1, "K"), "offensive-security.com": ("P", 4, 0, "K"), "offsec.com": ("P", 4, 0, "K"),
    "help.offensive-security.com": ("P", 4, 3, "K"), "app.infosecinstitute.com": ("Q", 1, 1, "K"),
    "isc2.org": ("Q", 2, 4, "V"), "docs.microsoft.com": ("B", 1, 0, "K"), "learn.microsoft.com": ("B", 1, 0, "K"),
    "certifications.tcm-sec.com": ("P", 5, 0, "K"), "axelos.com": ("Q", 1, 0, "U"), "scrum.org": ("Q", 0, 0, "K"),
    "security.ine.com": ("P", 4, 0, "K"), "ine.com": ("P", 4, 0, "K"), "elearnsecurity.com": ("P", 4, 0, "K"),
    "paloaltonetworks.com": ("Q", 1, 0, "K"), "apmg-international.com": ("Q", 1, 0, "K"),
    "isecom.org": ("X", 2, 1, "U"), "vmware.com": ("Q", 1, 1, "U"), "help.hackthebox.com": ("P", 5, 1, "K"),
    "academy.hackthebox.com": ("P", 5, 1, "K"), "hackthebox.com": ("P", 5, 1, "K"), "isa.org": ("Q", 1, 1, "V"),
    "drii.org": ("Q", 1, 2, "V"), "0xdarkvortex.dev": ("C", 0, 0, "U"), "pmi.org": ("Q", 2, 3, "K"),
    "juniper.net": ("Q", 1, 0, "U"), "aws.amazon.com": ("Q", 1, 1, "K"), "view.ceros.com": ("Q", 1, 0, "U"),
    "cncf.io": ("P", 1, 0, "V"), "trailhead.salesforce.com": ("Q", 1, 0, "K"), "tryhackme.com": ("P", 2, 0, "K"),
    "redhat.com": ("P", 2, 0, "K"), "sabsa.org": ("Q", 1, 1, "V"), "ncsc.gov.uk": ("S", 0, 3, "K"),
    "asisonline.org": ("Q", 2, 3, "V"), "zachman.com": ("Q", 1, 1, "V"), "lpi.org": ("Q", 1, 0, "V"),
    "cloud.google.com": ("Q", 1, 1, "V"), "training-certifications.checkpoint.com": ("Q", 1, 0, "K"),
    "bcs.org": ("Q", 1, 0, "U"), "ecfirst.biz": ("Q", 1, 1, "U"), "certipedia.com": ("Q", 1, 1, "U"),
    "certnexus.com": ("Q", 1, 0, "V"), "limessecurity.com": ("Q", 1, 1, "U"), "iacis.com": ("X", 5, 1, "V"),
    "opengroup.org": ("Q", 1, 0, "K"), "opentext.com": ("X", 3, 1, "K"), "securityblue.team": ("P", 4, 0, "V"),
    "suse.com": ("Q", 1, 0, "U"), "exidacace.com": ("Q", 1, 1, "U"), "iapp.org": ("Q", 2, 0, "K"),
    "practical-devsecops.com": ("P", 3, 0, "K"), "training.linuxfoundation.org": ("P", 1, 0, "V"),
    "sharedassessments.org": ("Q", 1, 1, "U"), "tuv.com": ("Q", 1, 1, "U"), "thecyberscheme.org": ("X", 2, 1, "V"),
    "cloudsecurityalliance.org": ("Q", 1, 0, "K"), "cyberstruggle.org": ("P", 5, 1, "V"), "oceg.org": ("Q", 1, 0, "V"),
    "ismi.org.uk": ("Q", 1, 1, "U"), "mitre-engenuity.org": ("B", 1, 0, "U"), "certiport.filecamp.com": ("Q", 0, 0, "K"),
    "ipas.org.tw": ("Q", 1, 0, "K"), "ctts.nics.nat.gov.tw": ("Q", 1, 1, "V"),
}
DEFAULT = ("Q", 1, 0, "U")

# ------------------------------------------------------------------ per-cert overrides
# label -> dict(F=, I=, R=, T=, B=, board=)
O = {}


def o(labels, **kw):
    for l in labels.split("|"):
        O.setdefault(l, {}).update(kw)


# OffSec
o("OSCP+", T=2, I=4, B="V"); o("OSEP|OSWE|OSED|OSMR", T=3, I=4, R=1); o("OSEE", T=4, I=5, R=2)
o("OSCE3", T=4, R=3); o("OSWA|OSDA|OSTH|OSIR", T=2, I=4); o("OSAI", T=3, I=4, R=1)
o("OSWP", T=1, I=2); o("KLCP", F="Q", I=1, T=0); o("OSCC", T=0, I=2)
# Hack The Box
o("HTB CJCA", T=1, B="V"); o("HTB CPTS|HTB CWES|HTB CDSA", T=2, B="V")
o("HTB CWEE|HTB CAPE|HTB CWPE|HTB CDEP", T=3, B="V")
o("HTB COAE", T=2, B="V")      # priced with the $490 tier (CPTS, CDSA), not the $1,260 expert tier
# TCM
o("PJPT|PSAA|PWPA|PAPA", T=1, I=4, B="V"); o("PNPT|PWPP|PMRP", T=2, B="V")
# TryHackMe
o("THM SEC1", T=0, I=1); o("THM SAL1", T=1, I=2); o("THM PT1", T=1, I=4, B="V"); o("THM SAL2", T=2, I=3)
# INE
o("eJPT", T=1); o("eCPPT|eWPT|eCTHP|eCDFP|eCIR|eMAPT|eNDP", T=2); o("eWPTX", T=3, I=5)
# Zero-Point / Altered / others practical
o("CRTO", F="P", I=4, R=0, T=2, B="K"); o("CRTL", F="P", I=5, R=2, T=3, B="K")
o("PACES", F="P", I=4, R=1, T=3, B="U"); o("BSCP", F="P", I=2, R=1, T=2, B="K")
o("CCD", F="P", I=4, R=0, T=2, B="V"); o("BTL1", T=1, I=4, B="K"); o("BTL2", T=3, I=5, B="V")
o("CSFA", F="P", I=5, R=2, T=3, B="U"); o("OSIP", F="P", I=3, R=2, T=1, B="U")
o("CSR", T=3); o("CSAE", T=1, I=2)
o("CFCE", T=3); o("CAWFE", T=3, I=3)
o("PDSO CDP", T=2, I=3); o("PDSO CDE", T=3, I=4, R=2)
o("CSTM", T=2); o("CSTL", T=3, B="V")
# SecOps Group (pentestingexams.com): essentials are multiple choice
o("SOG CAP|SOG CCSP-AWS|SOG NSP", F="Q", I=0, T=0, B="V")
o("SOG CAPen|SOG CNPen|SOG CMPen And|SOG CMPen iOS", T=2, B="V"); o("SOG CAPenX|CCPenX-AWS", T=3, I=3, R=1, B="V")
# GIAC
o("GSE", F="P", I=4, R=3, T=4); o("GSP", R=3, T=3)
o("GX-PT|GX-FA", F="P", I=2, R=2, T=3, B="V")
o("GXPN|GREM|GDAT|GCFA|GNFA|GCIA|GCTI|GDSA|GSTRT|GCPN|GRTP|GIME|GASF|GEIR|GCFR|GMLE|GAWN", T=3)
o("GISF|GFACT", T=0); o("GSEC|GICSP|GCLD", T=1)
o("GOAA|GAIPS|GASAE|GSOA", F="P", T=2, B="V")
# ISC2
o("CC", R=0, I=1, T=0, B="V"); o("SSCP", R=2, I=2, T=1, B="V"); o("CGRC", R=2, T=2, B="V")
o("CSSLP", R=3, T=3, B="V"); o("CISSP|CCSP", R=4, T=3, B="V"); o("CISSP Concentrations", R=4, T=4, B="V")
# ISACA
o("CISA|CISM|CRISC|CGEIT", T=3); o("CDPSE", R=3, T=2); o("CCOA", F="B", I=2, R=0, T=1, B="V"); o("CISM", B="V")
o("AAISM", T=4, B="V"); o("AAIR|AAIA", T=4)
# CompTIA
o("A+|Net+|Cloud Essnt|Project+", T=0, R=0); o("Security+|Linux+|Server+|Cloud+", T=1)
o("CySA+|Pentest+|SecAI+", T=2); o("SecurityX", T=3, I=2)
o("SecAI+", I=0, B="V")
# EC-Council
o("LPT", F="P", I=5, R=2, T=3, B="V"); o("CPENT", F="P", I=4, T=3); o("CEH", T=2); o("CHFI|ECIH|CTIA|CND|CASE|EDRP|CSA", T=2)
o("CCISO", R=4, T=3); o("EISM", T=2, R=0); o("CNDA", T=2); o("CSCU|ECSS|ECES", T=0, I=1, R=0); o("CCSE", T=2)
# Cisco
o("CCNA|CCNA Cyber|CCNA Auto", T=1, I=1); o("CCNP Sec|CCNP Ent|CCNP Cyber|CCNP Auto", T=2, I=2)
o("CCIE Sec|CCIE Ent", F="X", I=3, R=1, T=4, B="V"); o("CCDE", F="X", I=3, R=1, T=4)
# Fortinet / Palo Alto / Juniper / Check Point / F5
# Fortinet went back to NSE 1-8 on 2026-07-15; keys are the old labels, see RELABEL
o("FCF", F="Q", I=0, R=0, T=0, B="V"); o("FCA", T=1, B="V")
o("FCP NS|FCP PCS|FCP SO", R=2, T=2, B="V")                       # NSE 5/6 need NSE 4
o("FCSS SASE|FCSS PCS|FCSS SO|FCSS OT|FCSS NS", R=3, T=3, B="V")   # NSE 7 needs NSE 4 and NSE 5 or 6
o("FCX", F="X", I=3, R=3, T=4, B="V")                              # NSE 8 needs the whole chain plus two exams
o("PA Cyber", T=0); o("PA NetSec|PA Cloud", T=2); o("PA NGFW|PA XSOAR|PA XDR", T=3)
o("JNCIA Sec", T=1); o("JNCIS Sec", T=2); o("JNCIP Sec", T=3); o("JNCIE Sec", F="P", I=3, R=2, T=4)
o("CCSA", T=1); o("CCSE", T=2); o("CCSM", T=3, R=2)
o("F5 CA", T=1); o("F5 CTS APM|F5 CTS DNS", T=2); o("F5 CSE Sec", T=3, R=2)
# Microsoft / AWS / Google / cloud native
o("AZ-900|SC-900", T=0, I=0); o("AZ-104|SC-200|SC-300|SC-401|SC-500", T=1); o("AZ-305|SC-100", T=3, R=2)
o("AWS CP", T=0, B="V"); o("AWS SAA", T=1, B="V"); o("AWS SAP|AWS CSS", T=3, I=2, B="V")
o("Google ACE", T=1); o("Google PCSA|Google PCSE", T=2)
o("KCNA", F="Q", T=0, B="V"); o("CKA|CKAD", T=2, B="V"); o("CKS", T=3, R=2, B="V")
o("LFCA", F="Q", T=0); o("LFCS", T=1)
o("RHCSA", T=1); o("RHCE", T=2, R=2); o("RHCA", T=4, R=3, B="V")
o("LPIC-1", T=1); o("LPIC-2", T=2, R=2); o("LPIC-3", T=3, R=2)
o("VCP DCV|VCP NV", T=2); o("VCIX DCV|VCIX NV", F="P", I=2, T=3); o("VCDX DCV", F="S", I=2, R=3, T=4, board=1)
o("SFCTA", F="S", I=2, R=3, T=4, board=1)
# Governance / management
o("PMP", T=3, R=3); o("PgMP", T=4, R=4, board=1); o("CAPM", T=1, R=0); o("PMI ACP", T=2, R=2)
o("ITIL Fdn", T=0); o("ITIL MP|ITIL SL", T=2, R=2); o("ITIL Master", F="S", T=4, R=3)
o("PSM I", T=0, B="V"); o("PSM II", T=2, I=1, B="V"); o("Scrum PSD|Scrum PAL|Scrum SPS", T=2, I=1); o("PSM III", F="S", I=2, T=3, B="V")
o("TOGAF Fdn", T=0); o("TOGAF", T=2, I=1)
o("SABSA SCF", T=1, B="V"); o("SABSA SCP", F="S", T=3, R=2, B="V"); o("SABSA SCM", F="S", T=4, R=3, B="V")
o("Zach EAA", T=1); o("Zach EAP", F="S", T=2); o("Zach EAPro", F="S", T=3, R=3)
o("NCSC CCPP", T=2, board=1); o("NCSC CCPSP", T=3, R=4, board=1); o("NCSC CCPLP", T=4, R=4, board=1)
o("ASIS CPP", R=4, T=3, B="V"); o("ASIS APP", R=2, T=1); o("ASIS PCI", R=3, T=2)
o("IIA CIA", F="Q", I=3, R=3, T=3, B="K"); o("PCI QSA", F="Q", I=1, R=4, T=3, B="K")
o("CIPP|CIPT", T=2); o("CSA CCSK", T=1, B="V"); o("CSA CGC", T=1)
o("GRCP", T=1); o("GRCA", T=2, R=2)
o("DCCRP", R=2, T=2, board=1, B="V"); o("DACRP|DCBCA", R=0, T=1); o("DCBCLA", R=3, T=3, board=1); o("DCRMP", R=2, T=2, board=1)
o("PECB 27001F|PECB 27005F|PECB 27032F", I=1, R=2, T=0); o("PECB 27005RM", T=2)
# PECB grades run Provisional / Lead / Senior Lead / Master, so "Lead" is the middle tier
o("PECB 27001LA|PECB 27001LI|PECB 27005LM|PECB 27032CM|CLCSM", R=4, T=2, B="V")
o("ISA CFS", T=1); o("ISA CRAS|ISA CDS|ISA CAP", T=2); o("ISA CE", T=3, R=3)
o("CREST CPSA|CREST CPIA|CREST CPTIA", F="Q", I=1, R=0, T=1); o("CREST CRT|CREST CRIA|CREST CRTIA", T=2)
o("CREST CCTINF|CREST CCTAPP|CREST CCSAS|CREST CSAM|CREST CCTIM|CREST CCHIA|CREST CCNIA", T=3, I=3, R=2)
o("CREST CRTSA", F="S", I=2, R=1, T=3, B="V"); o("CREST CSAS", F="Q", T=1)
o("SPLK-3001", I=0, T=2, B="V"); o("CWSP", T=2, R=2); o("CIDPRO", T=1)
o("EnCE", T=2); o("CFSR", T=3); o("ACE", F="Q", I=1, R=0, T=0, B="U")
o("MAD SOCA|MAD CTI", T=1)
# Taiwan
o("iPAS 初級", T=0, R=0, I=1); o("iPAS 中級", T=1, R=1, I=2)
o("資安職能 核心", T=0, B="V"); o("資安職能 專業", T=1, B="V")
o("Programming Language", F="C", I=0, R=0, T=1, B="K")
# second pass, November 2026
o("SC-100", R=1, B="V")                                  # associate certs are recommended, not required
o("PDSO CDE", I=4, R=2, T=3, B="V"); o("PDSO CDP", B="K")
o("CWSP", R=2, T=2, B="V"); o("KLCP", B="V")
o("OSIP", F="P", I=5, R=1, T=1, B="V")                   # 10-day practical case file, course required
o("DV RTOS|DV OTD|DV MoS|DV AOPH|DV MILF", F="C", I=0, R=0, B="V")   # course with certificate of completion
o("CCE", F="X", I=5, R=1, T=2, B="V"); o("SACP", I=2, B="V"); o("DCA", T=1, B="V"); o("WCNA", B="V")
o("EITCA/IS", I=2, B="V"); o("SCE", R=2, T=2, B="V"); o("SCA", T=1, B="K")
o("PCI QSA", R=2, board=1, B="V")
# fourth pass: The SecOps Group tiers (Essentials 1h, Professional 4h, eXpert 7h) and Mile2
o("CBP|CBTP|CSEDP", F="Q", I=0, R=0, T=0, B="V")
o("C-AI/MLPen|C-APIPen|CRTeamer|CBFRPro|CKBPro|CBTeamer|CDAPen|C-AgAIPen", F="P", I=2, R=0, T=2, B="V")
o("C-ADPenX|CRTeamerX|CCPenX-Az|CBTeamerX", F="P", I=3, R=1, T=3, B="V")
o("C)ISSO", R=2, B="V"); o("C)AICSO|C)OL", T=2, B="V"); o("C)NIS2", T=3, B="V"); o("C)CFTA", T=2, B="V")
o("C)ISSA|C)ISSM|C)NFE|C)PSH|C)ISCAP|C)ISMS-LA", B="V")
# third pass
o("F5 CA", T=1, B="V"); o("F5 CTS APM|F5 CTS DNS", T=2, R=2, B="V"); o("F5 CSE Sec", T=3, R=3, B="V")   # exams chain 101 > 201 > specialist > expert
o("TUV COSP", T=1, B="V"); o("TUV COSTE", T=2, R=1, B="V"); o("TUV COSM", T=3, R=1, B="V")
o("TUV ITSM", R=2, T=2, B="V")                            # needs the IT Security Representative (TUV) first
o("CACE", F="S", I=2, R=4, T=3, B="V"); o("CACS", R=3, T=2, B="K")       # CACE: 10 years, MCQ + short answer + case study
o("Apple ACSP", T=1, B="V"); o("DCPP", T=2, B="V"); o("SSAP", R=0, I=1, T=1, B="V")                    # SSAP: 50 questions, 2 hours, open book
o("GCAD|GLIR", T=2, B="V"); o("GCIL|GSOM", T=3, B="V"); o("GX-CS|GX-FE|GX-IH|GX-IA", F="P", I=2, R=2, T=3, B="V")

KEY_T = [
    (0, r"Foundation|Fundamental|Essentials|Introduction|Entry|Awareness|\bFdn\b|User"),
    (1, r"Associate|Junior|Assistant"),
    (4, r"\bMaster\b|Fellow"),
    (3, r"Expert|Advanced|\bLead\b|Leader|Senior|Architect|Director|Officer"),
    (2, r"Professional|Practitioner|Specialist|Engineer|Analyst|Examiner|Manager|Auditor|Tester|Administrator"),
]

# ------------------------------------------------------------------ prices read from issuer pages, November 2026
# label -> detail lines that replace the 2024 ones
PRICE = {}


def price(labels, *lines):
    for l in labels.split("|"):
        PRICE[l] = list(lines)


price("CC", "考試費 $199", "免費方案已於 2026-05-20 停止新報名")
price("SSCP", "考試費 $249"); price("CGRC|CSSLP|CCSP", "考試費 $599"); price("CISSP", "考試費 $749")
price("CISSP Concentrations", "ISSAP、ISSEP、ISSMP 各 $599", "須 CISSP 加 2 年經驗，或累計 7 年")
price("CISM", "考試費 $760（會員 $575）"); price("CCOA", "考試費 $499（會員 $399）", "選擇題加實作題，4 小時")
price("OSEP|OSWE|OSED|OSWA|OSDA|OSTH|OSIR|OSAI", "課程加考試 $1,749（90 天）")
price("GFACT", "考試費 $399"); price("GISF", "考試費 $499")
price("GX-PT", "考試費 $1,299（持有 GPEN 為 $499）"); price("GX-FA", "考試費 $1,299（持有 GCFA 為 $499）")
price("CREST CRTSA", "£395 + VAT", "選擇題加長篇情境筆試")
price("LPT", "考試包 $899", "5 天實作滲透測試加報告")
price("PSM III", "每次 $500", "24 題論述，150 分鐘")
price("AWS SAP", "考試費 $300", "75 題，180 分鐘"); price("CKS", "考試費 $445（含一次重考）", "實作 2 小時，須先通過 CKA")
price("LFCS", "考試費 $445", "實作 2 小時"); price("ASIS CPP", "考試費 $450（會員 $300）", "須 7–9 年經驗")
price("CWSP", "考試費 $349.99", "60 題 90 分鐘，須有效 CWNA"); price("KLCP", "考試費 $299", "80 題 90 分鐘")
price("OSIP", "$300", "10 天實作個案報告，須先完成官方訓練")
price("CCE", "$485", "線上筆試加三份實作鑑識報告")
price("DCA", "考試費 $199", "55 題 90 分鐘"); price("SPLK-3001", "考試費 $130", "48 題 60 分鐘；官方已列為 legacy")
price("Google PCSA", "考試費 $200", "50–60 題，2 小時"); price("CIDPRO", "考試費 $750（會員另有折扣）")
price("PDSO CDE", "$1,199", "24 小時實作加報告，須先有 CDP")
price("BTL2", "£1,999（含訓練）", "最長 72 小時實作加報告")
price("CCIE Sec", "核心筆試 $400 加實作考 $1,600", "實作考 8 小時")
price("MTIA", "$699", "無考試，完成實作練習由講師審核")
price("SACP", "申請費 $369", "120 題"); price("DCPP", "INR 15,000 加稅", "選擇題含個案，65% 及格")
price("EITCA/IS", "€950", "12 科線上測驗"); price("SOG CAPenX", "原價 $521", "7 小時實作考")
price("CISSM", "考試券 $190（含兩次機會）", "100 題 90 分鐘")
price("CIMP", "$295（會員價，含三次機會）", "線上選擇題 100 題")
price("DV RTOS", "課程 $2,500", "3 天線上課程，無考試，發結業證書")
price("Security+", "建議報考 V8；英文版 V7 於 2027-06-11 停考")
price("HTB CJCA", "考試券 $490", "須完成 Junior Cybersecurity Analyst 路徑", "同時涵蓋攻擊與防禦")
price("HTB CPTS", "考試券 $490", "須完成 Penetration Tester 路徑"); price("HTB CWES", "考試券 $490", "須完成 Web Penetration Tester 路徑", "原名 HTB CBBH")
price("HTB CDSA", "考試券 $490", "須完成 SOC Analyst 路徑"); price("HTB COAE", "考試券 $490", "須完成 AI Red Teamer 路徑")
price("HTB CWEE", "考試券 $1,260", "須完成 Senior Web Penetration Tester 路徑"); price("HTB CAPE", "考試券 $1,260", "須完成 Active Directory Penetration Tester 路徑")
price("HTB CWPE", "考試券 $1,260", "須完成 Wi-Fi Penetration Tester 路徑"); price("HTB CDEP", "考試券 $1,260", "須完成 Detection Engineer 路徑")
price("CCNA", "考試費 $300"); price("CCNP Sec|CCNP Ent|CCNP Cyber|CCNP Auto", "核心考試 $400 加專精考試 $300")
price("CCIE Ent", "核心筆試 $400 加實作考 $1,600", "實作考 8 小時")
price("C)ISSO", "選擇題 100 題，2 小時", "須 1 年相關經驗")
price("SOG CAPen|SOG CNPen", "$328，4 小時實作")
price("AWS CP", "考試費 $100", "65 題，90 分鐘"); price("AWS SAA", "考試費 $150", "65 題，130 分鐘")
price("AWS CSS", "考試費 $300", "65 題，170 分鐘")
price("CKA", "考試費 $445（含一次重考）", "實作 2 小時"); price("KCNA", "考試費 $250（含一次重考）", "選擇題")
price("Google PCSE", "考試費 $200", "50–60 題，2 小時")
price("PSM I", "每次 $200", "80 題，60 分鐘，85% 及格"); price("PSM II", "每次 $250", "30 題，90 分鐘，85% 及格")
price("CSA CCSK", "$445（含兩次機會）", "開書線上考，60 題，120 分鐘")
price("SSAP", "50 題 2 小時，開書", "無報考資格"); price("CACE", "須 10 年經驗", "選擇、簡答與個案分析兩階段考試")

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

# ------------------------------------------------------------------ data fixes found in the November 2026 pass
DROP = {"GCPM": "GIAC 標示 In Abeyance（停止報考）", "GCWN": "GIAC 標示 In Abeyance（停止報考）",
        "GLEG": "GIAC 標示 In Abeyance（停止報考）", "GSNA": "GIAC 標示 In Abeyance（停止報考）",
        "FCSS ZTA": "Fortinet 新制 NSE 1–8 已無 Zero Trust 路線"}
RELABEL = {"CM)DFI": ("CM)CFI", "Mile2 Certified Master Cyber Forensics Investigator"),
           "CCD": ("CCDL2", "CyberDefenders Certified CyberDefender Level 2 (formerly CCD)"),
           "C)ISSA": ("C)CSSA", "Mile2 Certified Cybersecurity Systems Auditor (formerly C)ISSA)"),
           "C)ISSM": ("C)CSSM", "Mile2 Certified Cybersecurity Systems Manager (formerly C)ISSM)"),
           "FCF": ("NSE 1-3", "Fortinet NSE 1-3 Cybersecurity (online course and test)"),
           "FCA": ("NSE 4", "Fortinet NSE 4 FortiOS"),
           "FCP NS": ("NSE 5-6 SN", "Fortinet NSE 5 / NSE 6 Secure Networking"),
           "FCP PCS": ("NSE 5-6 Cloud", "Fortinet NSE 5 / NSE 6 Cloud Security"),
           "FCP SO": ("NSE 5-6 SecOps", "Fortinet NSE 5 / NSE 6 Security Operations"),
           "FCSS NS": ("NSE 7 SN", "Fortinet NSE 7 Secure Networking"),
           "FCSS PCS": ("NSE 7 Cloud", "Fortinet NSE 7 Cloud Security"),
           "FCSS SO": ("NSE 7 SecOps", "Fortinet NSE 7 Security Operations"),
           "FCSS SASE": ("NSE 7 SASE", "Fortinet NSE 7 SASE"),
           "FCSS OT": ("Forti OT", "Fortinet OT Security (industry certification)"),
           "FCX": ("NSE 8", "Fortinet NSE 8")}
REHOST = [("https://secops.group/", "https://pentestingexams.com/"),
          ("https://training.fortinet.com/", "https://www.fortinet.com/training-certification"),
          ("https://securityblue.team/btl2/", "https://www.centri.org/certifications/blue-team-level-2"),
          ("https://www.itgovernance.co.uk/shop/product/certified-iso-27001-isms-lead-implementer-training-course",
           "https://uk.grcsolutions.io/product/certified-iso-270012022-isms-lead-implementer-training-course")]
GIAC_PRICING = "https://www.giac.org/pricing/"
PTE = "https://pentestingexams.com/"
MILE2 = "https://www.mile2.com/master-certifications/"
COL_CLS = [(2, 4, "networkitem1"), (6, 6, "iamitem1"), (8, 14, "engineeritem1"), (16, 17, "assetitem1"),
           (19, 27, "mgmtitem1"), (29, 31, "testitem1"), (33, 33, "softwareitem1"), (35, 40, "blueopsitem1"),
           (41, 47, "redopsitem1")]
# certifications the issuer lists today that the chart lacked: (label, column, name, detail line, link)
EXTRA = [
    ("GCAD", 9, "GIAC Cloud Security Architecture and Design", "考試費 $999", GIAC_PRICING),
    ("GCIL", 39, "GIAC Cyber Incident Leader", "考試費 $999", GIAC_PRICING),
    ("GLIR", 40, "GIAC Linux Incident Responder", "考試費 $999", GIAC_PRICING),
    ("GSOM", 26, "GIAC Security Operations Manager", "考試費 $999", GIAC_PRICING),
    ("GX-CS", 24, "GIAC Experienced CyberSecurity Specialist", "考試費 $1,299（持有 GSEC 為 $499）", GIAC_PRICING),
    ("GX-FE", 37, "GIAC Experienced Forensics Examiner", "考試費 $1,299（持有 GCFE 為 $499）", GIAC_PRICING),
    ("GX-IH", 39, "GIAC Experienced Incident Handler", "考試費 $1,299（持有 GCIH 為 $499）", GIAC_PRICING),
    ("GX-IA", 30, "GIAC Experienced Intrusion Analyst", "考試費 $1,299（持有 GCIA 為 $499）", GIAC_PRICING),
    # The SecOps Group (pentestingexams.com)
    ("CBP", 33, "The SecOps Group Certified Blockchain Practitioner", "Essentials 級，1 小時", PTE),
    ("CBTP", 35, "The SecOps Group Certified Blue Team Practitioner", "Essentials 級，1 小時", PTE),
    ("CSEDP", 21, "The SecOps Group Certified Social Engineering Defense Practitioner", "Essentials 級，1 小時", PTE),
    ("C-AI/MLPen", 43, "The SecOps Group Certified AI/ML Pentester (C-AI/MLPen)", "$328，4 小時", PTE),
    ("C-APIPen", 42, "The SecOps Group Certified API Pentester (C-APIPen)", "Professional 級，4 小時", PTE),
    ("CRTeamer", 44, "The SecOps Group Certified Red Teamer", "$328，4 小時", PTE),
    ("CBFRPro", 46, "The SecOps Group Certified Binary Fuzzing & Reversing Professional", "Professional 級，4 小時", PTE),
    ("CKBPro", 45, "The SecOps Group Certified Kiosk Breakout Professional", "Professional 級，4 小時", PTE),
    ("CBTeamer", 36, "The SecOps Group Certified Blue Teamer", "$328，4 小時", PTE),
    ("CDAPen", 41, "The SecOps Group Certified Desktop Application Pentester", "Professional 級，4 小時", PTE),
    ("C-AgAIPen", 43, "The SecOps Group Certified Agentic AI Pentester (C-AgAIPen)", "Professional 級，4 小時", PTE),
    ("C-ADPenX", 44, "The SecOps Group Certified Active Directory Pentesting eXpert (C-ADPenX)", "$525，7 小時", PTE),
    ("CRTeamerX", 45, "The SecOps Group Certified Red Teamer - eXpert", "eXpert 級，7 小時", PTE),
    ("CCPenX-Az", 10, "The SecOps Group Certified Cloud Pentesting eXpert - Azure", "eXpert 級，7 小時", PTE),
    ("CBTeamerX", 35, "The SecOps Group Certified Blue Teamer - eXpert", "eXpert 級，7 小時", PTE),
    # Mile2
    ("C)AICSO", 23, "Mile2 Certified AI Cybersecurity Officer", "選擇題 100 題，2 小時", MILE2),
    ("C)NIS2", 25, "Mile2 Certified NIS2 Lead Auditor/Implementer", "選擇題 100 題，2 小時", MILE2),
    ("C)CFTA", 38, "Mile2 Certified Cyber Forensics Threat Analyst", "選擇題 100 題，2 小時", MILE2),
    ("C)OL", 20, "Mile2 Certified Organizational Leader", "選擇題 100 題，2 小時", MILE2),
]
for label, col_, name, detail, link in EXTRA:
    cls = next(c for lo_, hi_, c in COL_CLS if lo_ <= col_ <= hi_)
    st = ' style="font-size:0.48vw;"' if len(label) > 8 else ""
    h = (f'<a class="{cls}"{st} href="{link}" tooltiptext="{html.escape(name, quote=True)}\n    '
         f'{html.escape(detail, quote=True)}" tabindex="0" target="_blank" >{label}</a>')
    items.append(dict(html=h, cls=cls, label=label, row=14, col=col_, span=1))
dropped = [i for i in items if i["label"] in DROP]
items = [i for i in items if i["label"] not in DROP]


def attrs(it):
    m = re.match(r'<a class="[^"]+"(?: style="[^"]*")? href="([^"]*)" (tooltip\w+)="([^"]*)"', it["html"], re.S)
    href, tipattr, tip = m.groups()
    host = urlparse(href).netloc.replace("www.", "")
    name = html.unescape(tip.split("\n")[0].strip())
    F, I, R, B = HOST.get(host, DEFAULT)
    ov = O.get(it["label"], {})
    F, I, R, B = ov.get("F", F), ov.get("I", I), ov.get("R", R), ov.get("B", B)
    board = ov.get("board", 0)
    if "T" in ov:
        T, tsrc = ov["T"], "官方級別"
    else:
        T = None
        for t, pat in KEY_T:
            if re.search(pat, name):
                T, tsrc = t, "名稱所示級別"
                break
        if T is None:
            r0 = it["row"]
            T = 4 if r0 <= 6 else 3 if r0 <= 11 else 2 if r0 <= 17 else 1 if r0 <= 22 else 0
            tsrc = "沿用 2024 原圖區段"
    score = F_PTS[F] + 8 * T + R_PTS[R] + I_PTS[I] + 3 * board
    return dict(href=href, host=host, name=name, F=F, I=I, R=R, T=T, B=B, board=board, tsrc=tsrc, score=score,
                tipattr=tipattr, tip=tip)


for it in items:
    it.update(attrs(it))

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

# ------------------------------------------------------------------ emit
def retip(it):
    h = it["html"]
    lab = it["label"]
    if lab in RELABEL:
        new_label, new_name = RELABEL[lab]
        h = h.replace(">" + lab + "</a>", ">" + new_label + "</a>")
        h = h.replace(html.escape(it["name"], quote=True), html.escape(new_name, quote=True), 1)
    for old, new in REHOST:
        if old in h:
            h = h.replace(it["href"], new if not new.endswith("/") else new, 1) if it["href"].startswith(old) else h
    basis = f"排序依據：{F_ZH[it['F']]}｜{I_ZH[it['I']]}｜{R_ZH[it['R']]}｜{T_ZH[it['T']]}級（{it['tsrc']}）"
    if it["board"]:
        basis += "｜須審查委員會或面試"
    if lab in PRICE:
        def swap(m):
            first = m.group(2).split("\n")[0]
            return f' {m.group(1)}="' + first + "".join("\n    " + html.escape(l, quote=True) for l in PRICE[lab]) + '"'
        h = re.sub(r' (tooltip\w+)="([^"]*)"', swap, h, count=1)
    extra = "\n    " + html.escape(basis, quote=True) + "\n    " + html.escape(f"評分 {it['score']}｜{B_ZH[it['B']]}", quote=True)
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
    <li><strong>官方級別</strong>：入門 0、初階 8、專業 16、專家 24、頂級 32。</li>
    <li><strong>報考門檻</strong>：無 0、僅建議經驗或須先修官方課程 3、須前置證照或 1–2 年經驗 6、3–4 年或兩層前置證照 10、5 年以上 16；另須審查委員會或面試加 3。</li>
    <li><strong>考試強度</strong>：1 小時內 0、約 2 小時 2、3–4 小時 5、6–12 小時 8、24 小時以上 11（多日制不再加分）。</li>
  </ul>
  <p>資料來源：{by_b['V']} 張屬於本次已讀取官方頁面的發證單位（多數是讀該單位的代表頁面，不是逐張查證）；{by_b['K']} 張依發證單位公開的通用考試形式判定，本次未讀取官方頁面；
  {by_b['U']} 張的官方頁面讀不到或尚未查，考試形式暫用該單位的預設值。另有 {n_band} 張無法從官方名稱判定級別，級別沿用 2024 原圖所在區段。
  同分或該列已滿時會落在相鄰列。
  本次另移除 {len(dropped)} 張已停止報考的證照：{'、'.join(d['label'] for d in dropped)}；
  並補上官方已有、原圖未收的 {len(EXTRA)} 張（GIAC 8 張、The SecOps Group 15 張、Mile2 4 張）。
  價格方面，GIAC 全系列與另外 {len(PRICE)} 張已改為 2026 年 11 月官方頁面的數字，其餘仍是 2024 年的內容。</p>
</section>
"""
out = out.replace('<section class="notes">', rules + '<section class="notes">', 1)
open(out_path, "w", encoding="utf-8").write(out)

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow("label name host format intensity prereq tier tier_source board score basis old_row new_row col url".split())
    for i in sorted(items, key=lambda i: -i["score"]):
        w.writerow([i["label"], i["name"], i["host"], i["F"], i["I"], i["R"], i["T"], i["tsrc"], i["board"], i["score"],
                    i["B"], i["row"], i["nrow"], i["ncol"], i["href"]])
moved = sum(1 for i in items if i["nrow"] != i["row"])
off = sum(1 for i in items if i["nrow"] != i["target"])
print(f"items {len(items)} | score {lo}-{hi} | basis {by_b} | moved rows {moved} | placed off-target {off} | dropped {len(dropped)}")
print("tier from 2024 band:", sum(1 for i in items if i["tsrc"].startswith("沿用")))

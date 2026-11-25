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
o("GCFA|GCIA|GICSP|GPEN", F="B", B="V")      # named on giac.org/cyberlive as having hands-on CyberLive items
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
o("LPT", F="P", I=5, R=2, T=3, B="V"); o("CPENT", F="P", I=4, T=3); o("CEH", T=2, B="V"); o("CHFI|ECIH|CND", T=2, B="V"); o("CTIA|CASE|EDRP|CSA", T=2)
o("CCISO", R=4, T=3); o("EISM", T=2, R=0); o("CNDA", T=2); o("CSCU|ECSS|ECES", T=0, I=1, R=0); o("CCSE", T=2)
# Cisco
o("CCNA|CCNA Cyber|CCNA Auto", T=1, I=1); o("CCNP Sec|CCNP Ent|CCNP Cyber|CCNP Auto", T=2, I=2)
o("CCIE Sec|CCIE Ent", F="X", I=3, R=2, T=4, B="V"); o("CCDE", F="X", I=3, R=2, T=4)   # core exam required before the lab
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
o("eEDA", F="P", I=4, R=0, T=2, B="U"); o("eAIPT", F="P", I=4, R=0, T=2, B="U"); o("eCRA", F="Q", I=1, R=0, T=2, B="U")
o("SecOT+", F="B", I=1, R=1, T=2, B="V"); o("CSA", I=2); o("CPENT", B="V")
# fourth pass: The SecOps Group tiers (Essentials 1h, Professional 4h, eXpert 7h) and Mile2
o("CBP|CBTP|CSEDP", F="Q", I=0, R=0, T=0, B="V")
o("C-AI/MLPen|C-APIPen|CRTeamer|CBFRPro|CKBPro|CBTeamer|CDAPen|C-AgAIPen", F="P", I=2, R=0, T=2, B="V")
o("C-ADPenX|CRTeamerX|CCPenX-Az|CBTeamerX", F="P", I=3, R=1, T=3, B="V")
o("C)ISSO", R=2, B="V"); o("C)AICSO|C)OL", T=2, B="V"); o("C)NIS2", T=3, B="V"); o("C)CFTA", T=2, B="V")
o("C)ISSA|C)ISSM|C)NFE|C)PSH|C)ISCAP|C)ISMS-LA", B="V")
# OffSec course pages and CREST exam pages, read 2026-11-25
o("OSEP|OSWE|OSED", I=4, R=1, T=3, B="V")            # 48h proctored; prerequisites recommended only
o("OSEE", I=5, R=1, T=4, B="V")                       # 72h proctored, in person only
o("OSWA|OSDA|OSAI", I=4, B="V")                       # 24h
o("OSTH|OSIR", I=3, B="V")                            # 8h
o("OSCC", F="P", I=3, R=0, T=0, B="V")                # 6h: attack, defend, build
o("OSWP", I=2, B="V")                                 # 4h
o("CREST CCTINF", F="X", I=3, R=0, T=3, B="V")        # MCQ 1h + scenario 2h + practical 3h, no prerequisite
o("CREST CSAM", F="S", I=2, R=1, T=3, B="V")          # MCQ + long-form + scenario, two parts
o("CREST CCTIM", F="S", I=2, R=1, T=3, B="V")         # short-form, long-form, scenario, two parts
o("CREST CRT", F="X", I=2, R=2, T=2, B="V")           # 2.5h practical with MCQ/flags; valid CPSA required
# CREST pages read one at a time, 2026-11-25 (second batch); the certification index lists 12 current certifications
o("CREST CPSA|CREST CPIA", F="Q", I=1, R=0, T=1, B="V")   # 120 MCQ, 2h, no prerequisite
o("CREST CPTIA", F="Q", I=1, R=0, T=1, B="V")             # MCQ; length not on the page
o("CREST CRIA", F="B", I=2, R=2, T=2, B="V")              # 150 MCQ in 2.5h with Kali/Windows environment; valid CPIA required
o("CREST CRTIA", F="S", I=2, R=1, T=2, B="V")             # MCQ + long-form; two years "expected"
o("CREST CCTAPP|CREST CCSAS", F="X", I=3, R=0, T=3, B="V")  # written 3h + practical 3h, no prerequisite
o("CREST CCIM", F="S", I=2, R=1, T=3, B="V")              # MCQ + long-form/scenario, two parts within three months
# Cisco certification pages and Mile2 pages, read 2026-11-25
o("CCDE", B="V"); o("CCNP Sec|CCNP Ent|CCNP Cyber|CCNP Auto|CCNA|CCNA Cyber|CCNA Auto|CCT", B="V")
o("CM)ISSO|CM)DFI|CM)IPS|CM)ISRM|CM)DRE|CM)CTA|CM)CSSA", F="Q", I=1, R=3, T=3, B="V")   # title awarded for four certifications; no exam of its own
o("C)PTE", F="Q", I=1, R=1, T=2, B="V")                   # 100 MCQ, 2h, online
# ISACA credential pages and CompTIA certification pages, read 2026-11-25
o("CISA|CRISC|CGEIT|CDPSE|AAIR|AAIA", B="V")
o("SecurityX|Net+|Linux+|Cloud+|Server+|Project+", B="V"); o("Pentest+", I=2, B="V")
# Microsoft Learn, EC-Council, Palo Alto and Infosec pages, read 2026-11-25
o("SC-401|SC-200|SC-300|AZ-104|AZ-305|SC-900|AZ-900", B="V")
o("EISM", F="Q", I=1, R=1, T=2, B="V")       # 150 MCQ, 2h, 70%; official CCISO training required
o("CCSE@cert.eccouncil.org", F="Q", I=2, R=1, T=2, B="V")       # 125 MCQ, 4h, 70%; 2 years or official training
o("PA Cloud", T=3)                           # listed as Specialist, same level as the other engineer exams
# cert.eccouncil.org certification pages, read 2026-11-25
o("CPENT|LPT", F="P", I=4, R=0, T=3, B="V")   # one 24h exam (or two 12h sessions); LPT (Master) = 90% or above on it
o("CCISO", F="Q", I=2, R=4, T=3, B="V")       # 150 questions, 2.5h; five years in the domains
o("CSA|EDRP", F="Q", I=2, R=1, T=2, B="V")    # CSA 100 q 3h; EDRP 150 q 4h
o("CTIA|CASE", F="Q", I=1, R=1, T=2, B="V")   # 50 q, 2h
o("CNDA", R=2, B="V")                         # CEH plus government or military employment
o("CSCU|ECES", F="Q", I=1, R=0, T=0, B="V"); o("ECSS", F="Q", I=2, R=0, T=0, B="V")
o("PECB 27005RM|PECB 27001F", B="V")
# assorted issuer pages, read 2026-11-25
o("RHCSA|RHCE|PMP", B="V"); o("PDSO CDP", F="P", I=3, R=0, T=2, B="V"); o("Scrum PSD", F="Q", I=0, R=0, T=2, B="V")
o("GCPT|CASM", I=0)   # 60-minute exams
o("DCBCA", R=2); o("資安職能 專業", R=2)   # two years of experience; core certificate required before professional subjects
o("ISA CDS|ISA CRAS", R=2)   # Fundamentals Specialist certificate required first
o("CSM", I=0)
# iPAS 115 年度簡章 (official PDF on ipas.org.tw), read 2026-11-25
o("iPAS 初級", F="Q", I=2, R=0, T=0, B="V")   # two subjects, 75 min each, 50 single-choice questions each
o("iPAS 中級", F="Q", I=2, R=1, T=1, B="V")   # two subjects, 90 min each, 40 questions each incl. multi-select and case sets
o("IIA CIA", F="Q", I=3, R=2, T=3, B="V")    # three parts; 1-2 years with a degree
o("APMG 27001F", F="Q", I=0, R=0, T=0, B="V"); o("APMG 27001P", F="Q", I=2, R=0, T=2, B="V"); o("APMG 27001A", F="Q", I=1, R=0, T=2, B="V")
o("THM SEC1|THM SAL1|THM SAL2", B="V"); o("THM PT1", I=4, B="V")
o("SFSA", F="Q", I=1, R=3, T=2, B="V")       # granted once four prerequisite certifications are held
o("PMI ACP", F="Q", I=2, R=2, T=2, B="V"); o("Scrum SPS|Scrum PAL", F="Q", I=0, R=0, T=2, B="V"); o("SCA", F="Q", I=1, R=0, T=1, B="V")
o("CCFE|CMFE|CSSA|CDRP|CMWAPT|CRTOP|CREA|CSAP", B="U")   # portal pages show boot camps only, no certification facts
# GIAC, read cert by cert on 2026-11-25: (questions, hours, pass %, CyberLive hands-on items)
GIAC = {
    "GXPN": (60, 3, 67, 1), "GREM": (66, 3, 73, 1), "GCIH": (106, 4, 69, 1), "GSEC": (106, 4, 72, 1),
    "GWAPT": (82, 3, 71, 1), "GCTI": (82, 3, 71, 1), "GNFA": (66, 3, 70, 1), "GCFR": (82, 3, 64, 1),
    "GCFE": (82, 3, 70, 1), "GEIR": (82, 3, 72, 1), "GMON": (82, 3, 74, 1), "GRTP": (82, 3, 76, 1),
    "GMLE": (82, 3, 65, 1),
    "GIME": (75, 2, 67, 0), "GAWN": (75, 2, 70, 0), "GDAT": (75, 2, 70, 0), "GSTRT": (75, 3, 76, 0),
    "GISP": (150, 4, 70, 0), "GDSA": (75, 2, 63, 0), "GSLC": (115, 3, 70, 0), "GASF": (75, 2, 69, 0),
    "GCTD": (75, 2, 70, 0), "GCCC": (75, 2, 71, 0), "GWEB": (75, 3, 68, 0), "GCED": (115, 3, 69, 0),
    "GPCS": (75, 2, 64, 0), "GCSA": (75, 2, 66, 0), "GRID": (75, 2, 74, 0), "GCDA": (75, 2, 76, 0),
    "GPYC": (75, 2, 67, 0), "GCPN": (75, 2, 70, 0), "GMOB": (75, 2, 71, 0), "GSOC": (75, 2, 67, 0),
    "GBFA": (75, 2, 69, 0), "GCIP": (75, 3, 70, 0), "GCLD": (75, 2, 61, 0), "GOSI": (75, 2, 69, 0),
    "GFACT": (75, 2, 71, 0), "GISF": (75, 2, 69, 0),
}
for _l, (_q, _h, _p, _c) in GIAC.items():
    o(_l, F="B" if _c else "Q", I=1 if _h <= 2 else 2, B="V")
# portfolio certifications have no exam of their own
o("GSE", F="P", I=2, R=3, T=4, B="V"); o("GSP", F="P", I=2, R=3, T=3, B="V")
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
price("OSEP|OSWE|OSED", "課程加考試 $1,749（90 天）", "實作考 48 小時，全程監考")
price("OSWA|OSDA|OSAI", "課程加考試 $1,749（90 天）", "實作考 24 小時，全程監考")
price("OSTH|OSIR", "課程加考試 $1,749（90 天）", "實作考 8 小時，全程監考")
price("OSEE", "實作考 72 小時，全程監考", "僅實體授課；官方頁面未列價格")
price("OSWP", "實作考 4 小時，全程監考"); price("OSCC", "課程 $899", "實作考 6 小時：攻擊、防禦、建置各約 2 小時")
price("CREST CCTINF", "筆試（選擇題 1 小時加情境題 2 小時）加實作考 3 小時", "無報考資格；價格依國家，經 Pearson VUE 報名")
price("CREST CRT", "實作考 2.5 小時（選擇題、flag、簡答）", "須持有有效的 CPSA")
price("CREST CSAM", "選擇題加長篇與情境筆試，分兩階段"); price("CREST CCTIM", "簡答、長篇、情境三部分，分兩階段")
price("CREST CPSA|CREST CPIA", "選擇題 120 題，2 小時", "無報考資格；價格依國家，經 Pearson VUE 報名")
price("CREST CPTIA", "選擇題筆試，及格標準三分之二", "無報考資格；價格依國家，經 Pearson VUE 報名")
price("CREST CRIA", "選擇題 150 題，2.5 小時，考場提供 Kali 與 Windows 環境", "須持有有效的 CPIA；效期三年")
price("CREST CRTIA", "選擇題加長篇問答", "官方預期兩年以上威脅情資經驗，未列為硬性條件")
price("CREST CCTAPP", "筆試（選擇題 1 小時加情境題 2 小時）加實作考 3 小時", "無報考資格；價格依國家，經 Pearson VUE 報名")
price("CREST CCSAS", "筆試（選擇題 1 小時加情境題 2 小時）加實作考 3 小時", "無報考資格；原名 CCSAS，會員公司員工可享七折")
price("CREST CCIM", "選擇題加長篇與情境筆試，分兩階段，須於三個月內完成", "無報考資格；價格依國家，經 Pearson VUE 報名")
price("GFACT", "考試費 $399"); price("GISF", "考試費 $499")
price("GX-PT", "考試費 $1,299（持有 GPEN 為 $499）"); price("GX-FA", "考試費 $1,299（持有 GCFA 為 $499）")
price("CREST CRTSA", "£395 + VAT", "選擇題加長篇情境筆試")
price("LPT", "官方 LPT 頁面：5 天實作考加報告，考試包 $899", "維護者查核：CPENT 考 90% 以上即取得，不另計費（未能向官方頁面查證）")
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
price("MTIA", "$699", "無考試，完成實作練習由講師審核"); price("MGRC", "$699（促銷價 $595）", "無考試，完成實作練習由講師審核")
price("SACP", "申請費 $369", "120 題"); price("DCPP", "INR 15,000 加稅", "選擇題含個案，65% 及格")
price("EITCA/IS", "€950", "12 科線上測驗"); price("SOG CAPenX", "原價 $521", "7 小時實作考")
price("CISSM", "考試券 $190（含兩次機會）", "100 題 90 分鐘")
price("CIMP", "$295（會員價，含三次機會）", "線上選擇題 100 題")
price("DV RTOS", "課程 $2,500", "3 天線上課程，無考試，發結業證書")
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
# figures supplied by the repo owner on 2026-11-25; UNV marks the ones the issuer's page could not confirm
UNV3 = "美國個人零售參考價（第三方來源），未經 CompTIA 官方查證；台灣定價未確認"
price("Security+", "考試費 $439", "建議報考 V8；英文版 V7 於 2027-06-11 停考", UNV3)
price("A+", "兩科合計 $548", UNV3); price("Net+|Cloud+|Linux+|Server+|Project+", "考試費 $399", UNV3)
price("CySA+|Pentest+", "考試費 $439", UNV3); price("SecurityX", "考試費 $544", UNV3)
price("CRTO", "課程含一次考試 £365（官方課程頁）", "第三方紀錄為 £399（2026-11-10），未經官方驗證")
price("CRTL", "課程含考試 £449（第三方紀錄，2026-11-10）", "官方頁面本次未能讀取")
price("CEH", "考試券 $1,199（Pearson VUE 考場）", "自修考生須先通過資格審查")
price("CHFI", "考試券 $650（遠端監考）"); price("CND", "考試券 $550（遠端監考）"); price("ECIH", "考試券 $450（遠端監考）")
price("SC-200|SC-300|SC-100|AZ-104|AZ-305|SC-401|SC-500", "約 $165，依國家或地區定價")
price("SC-900|AZ-900", "約 $99，依國家或地區定價", "使用者提供，官方常見問題頁未列此數字")
UNVI = "使用者提供，官方結帳頁需登入，未能查證；多數須另有訂閱"
price("eJPT", "考試券 $250", UNVI); price("eCPPT|eWPT|eWPTX|eMAPT|eCIR|eCTHP|eCDFP", "考試券 $450", UNVI)
price("eEDA", "考試券 $450", UNVI)
price("CSA", "考試費 $450；電子教材含考試 $550", "312-39，100 題選擇題，180 分鐘", "維護者提供，官方頁面未列這些數字")
price("CPENT", "24 小時實作考試", "單獨考試費：須向官方詢價", "教材與 Lab 套裝 $899，不含考試（維護者提供）")
price("SecurityX", "考試費 $544", "CAS-005，最多 90 題，165 分鐘，選擇題加實作題，只分及格與不及格", UNV3)
price("Pentest+", "考試費 $439", "PT0-003，最多 90 題，165 分鐘，750 分及格", UNV3)
price("Net+", "考試費 $399", "N10-009，最多 90 題，90 分鐘，720 分及格", UNV3)
price("Linux+", "考試費 $399", "XK0-006，最多 90 題，90 分鐘，720 分及格", UNV3)
price("Cloud+", "考試費 $399", "CV0-004，最多 90 題，90 分鐘，750 分及格", UNV3)
price("Server+", "考試費 $399", "SK0-005，最多 90 題，90 分鐘，750 分及格", UNV3)
price("Project+", "考試費 $399", "PK0-005，最多 90 題，90 分鐘，710 分及格", UNV3)
price("CySA+", "考試費 $439", "V4 為新版；英文版 V3 於 2026-12-22 停考", UNV3)
price("A+", "兩科合計 $548", "須通過 Core 1 與 Core 2 兩科（V15）", UNV3)
price("CISA|CRISC|CGEIT|CDPSE", "考試費 $760（會員 $575）", "通過後另繳申請費 $50，並須提出經驗證明")
price("AAIR", "考試費 $599（會員 $459）", "須持有 CISA、CISM、CRISC、CGEIT、CDPSE 或官方列出的其他資格")
price("AAIA", "考試費 $599（會員 $459）", "須持有有效 CISA，或官方列出的稽核類資格")
price("SC-401|SC-200|SC-300|AZ-104", "約 $165，依國家或地區定價", "100 分鐘，中階，無報考資格；每 12 個月免費線上更新")
price("AZ-305", "約 $165，依國家或地區定價", "須先取得 Azure Administrator Associate（AZ-104）")
price("SC-900|AZ-900", "約 $99，依國家或地區定價", "45 分鐘，入門級", "價格為使用者提供，官方頁面只寫依國家或地區定價")
price("EISM", "選擇題 150 題，2 小時，70% 及格", "無年資要求，但須先完成官方 CCISO 訓練；官方頁面未列價格")
price("CCSE@cert.eccouncil.org", "選擇題 125 題，4 小時，70% 及格", "須 2 年資安經驗（申請費 $100），或參加官方訓練；考試券價格未列")
price("CPENT", "24 小時實作考試，可拆成兩場 12 小時", "無報考資格；須在考試儀表板啟用後 30 天內完成並交報告（延長 7 天 $100）", "考試費官方頁面未列；教材與 Lab 套裝 $899 不含考試（維護者提供）")
price("LPT", "與 CPENT 同一場 24 小時實作考，90% 以上即同時取得 LPT (Master)", "不是獨立考試；eccouncil.org 的舊 LPT 頁面仍寫五天考試與 $899 考試包")
price("CSA", "312-39，100 題，3 小時，70% 及格", "考試費 $450、電子教材含考試 $550 為維護者提供，官方頁面未列")
price("CCISO", "150 題，2.5 小時，及格線依題本 60%–85%", "須五個領域各 5 年經驗（上官方課程者為其中三個領域）；自行報考申請費 $100")
price("CTIA", "312-85，50 題，2 小時，70% 及格", "考試費官方頁面未列")
price("CASE", "50 題，2 小時，70% 及格（分 .NET 與 Java 兩種）", "須上官方課程、或 2 年相關經驗（申請費 $100）")
price("EDRP", "312-76，150 題，4 小時，70% 及格", "考試費官方頁面未列")
price("CNDA", "須先取得 CEH，且任職於政府、軍方或其承包商", "處理費 $200")
price("CSCU", "112-12，選擇題 50 題，2 小時，70% 及格", "無報考資格"); price("ECES", "50 題，2 小時，70% 及格")
price("ECSS", "100 題，3 小時，70% 及格")
price("PECB 27005RM", "考試與證照費含在訓練課程價格內", "Risk Manager 級別須 2 年工作經驗（其中 1 年風險管理）與 200 小時實務；Provisional 級別無經驗要求")
price("PECB 27001F", "考試與證照費含在訓練課程價格內", "須完成 Foundation 課程；未通過可於 12 個月內免費重考")
price("RHCSA", "EX200，實作考", "無報考資格；官方頁面未列時間與價格")
price("RHCE", "須通過 EX200 加一科進階考試（Enterprise Linux 為 EX342，Ansible 為 EX294）", "官方頁面未列時間與價格")
price("PMP", "考試費 $555（會員 $405）", "180 題；大學學歷須 36 個月專案經驗，否則 60 個月，另須 35 小時訓練或 CAPM")
price("PDSO CDP", "課程 $899（含一次考試）", "5 題實作挑戰 6 小時，之後 24 小時內交報告；無硬性報考資格")
price("Scrum PSD", "每次 $200", "80 題，60 分鐘，85% 及格")
price("BSCP", "證照效期五年", "應考須有有效的 Burp Suite Professional 訂閱；考試形式與價格在另一頁，未讀")
price("APMG 27001F", "選擇題 50 題，40 分鐘，50% 及格，閉卷", "價格依考試地點，官方頁面未列")
price("APMG 27001P", "情境題 4 大題（各 20 分），2.5 小時，50% 及格，開書", "價格依考試地點，官方頁面未列")
price("APMG 27001A", "選擇題含小型情境 40 題，120 分鐘，50% 及格", "價格依考試地點，官方頁面未列")
price("APMG 20000F|APMG 20000A", "及格標準 26/40（65%）", "題型、時間、價格官方頁面未列；Auditor 不開放自修報考")
price("APMG 20000P", "及格標準 40/80（50%）", "題型、時間、價格官方頁面未列")
price("THM SEC1", "實作評量，答案來自實際操作而非選擇題", "無正式報考資格；時間與價格官方文章未列")
price("THM SAL1", "在模擬 SOC 環境處理告警並撰寫事件報告", "無正式報考資格；時間與價格官方文章未列")
price("THM SAL2", "SAL1 形式的進階版，多階段調查情境", "無正式報考資格；時間與價格官方文章未列")
price("THM PT1", "48 小時實作（網頁、網路、AD）加報告", "無正式報考資格；價格官方文章未列")
price("SFSA", "無獨立考試", "取得四張指定的 Salesforce 架構與開發證照後自動授予")
price("PMI ACP", "考試費 $495（會員 $435）", "選擇題 120 題，3 小時；須 2,000 小時專案經驗加 1,500 小時敏捷經驗，另 21 小時訓練")
price("Scrum SPS", "每次 $250", "40 題，60 分鐘，85% 及格"); price("Scrum PAL", "每次 $200", "36 題，60 分鐘，85% 及格")
price("SCA", "考試費 $149", "70 題，90 分鐘，70% 及格，無報考資格")
price("IIA CIA", "三科考試：Part 1 $445、Part 2 $415、Part 3 $415，申請費 $240（會員 $310／$280／$280，申請費 $120）", "碩士須 1 年、學士須 2 年內部稽核經驗；2027-01-04 起調整價格")
price("iPAS 初級", "報名費每科 NT$1,200（新考生優惠 NT$800），共兩科", "每科單選 50 題、75 分鐘；兩科同考平均 70 分且單科不低於 60 分", "無報考資格；證書永久有效；115 年考試日 05/23、10/31")
price("iPAS 中級", "報名費每科 NT$1,500（新考生優惠 NT$1,000），共兩科", "每科 40 題（單選、複選、題組）、90 分鐘；兩科皆須 70 分", "無報考資格，可跳過初級；證書效期 5 年，換證須 48 小時資安訓練；115 年考試日 04/11、08/22")
# price pass, 2026-11-25: regular prices only; time-limited sale prices are noted but not used as the price
price("PJPT", "$249（含 12 個月訓練教材與一次免費重考）", "實作 2 天，另 2 天寫報告；無報考資格")
price("PNPT", "$499（含 12 個月訓練教材與一次免費重考）", "實作 5 天，另 2 天寫報告，再加 15 分鐘口頭簡報；無報考資格")
price("PWPP", "$499（含 12 個月訓練教材與一次免費重考）", "實作 3 天，另 2 天寫報告；促銷價 $399 至 11/30")
price("PWPA", "$249（含 12 個月訓練教材與一次免費重考）", "實作 2 天，另 2 天寫報告；促銷價 $199 至 11/30")
price("PSAA", "$249（含 12 個月訓練教材與一次免費重考）", "實作 2 天，另 2 天寫報告；促銷價 $199 至 11/30")
price("PAPA", "$249（含 12 個月訓練教材與一次免費重考）", "實作 2 天，另 2 天寫報告")
price("PMRP", "$499（含 12 個月訓練教材與一次免費重考）", "實作 5 天，另 2 天寫報告；促銷價 $399 至 11/30")
MOSSE_NOTE = "無考試，完成實作練習由講師審核；促銷碼另有折扣"
price("MOIS|MBT|MCPT|MDFIR|MRE|MDSO|MRT|MVRE", "$699", MOSSE_NOTE)
price("MCSE|MPT|MTH", "$699（促銷價 $595）", MOSSE_NOTE)
price("MCSF|MSAF", "$699（促銷價 $450）", MOSSE_NOTE)
price("MCPE", "$1,000（促銷價 $800）", MOSSE_NOTE); price("MRCI", "$249（促銷價 $199）", MOSSE_NOTE)
price("MICS", "目錄頁未列價格", MOSSE_NOTE)
SOG_BF = "官網目前有限時 90% 折扣，未採計"
price("C-AI/MLPen|CRTeamer|CBTeamer", "$328", "4 小時實作考", SOG_BF)
price("C-ADPenX", "$525", "7 小時實作考", SOG_BF)
price("C-APIPen|CBFRPro|CKBPro|CDAPen|C-AgAIPen|SOG CMPen And|SOG CMPen iOS", "原價官網首頁未列", "4 小時實作考", SOG_BF)
price("CRTeamerX|CCPenX-Az|CBTeamerX|CCPenX-AWS", "原價官網首頁未列", "7 小時實作考", SOG_BF)
price("CBP|CBTP|CSEDP|SOG CAP|SOG CCSP-AWS|SOG NSP", "原價官網首頁未列", "1 小時選擇題", SOG_BF)
GIAC_STD = "重考 $899，換證 $499，模擬考 $399"
price("GAIPS|GASAE|GOAA|GSOA|GCFA|GPEN|GCIA|GCAD|GCIL|GLIR|GSOM|GICSP", "考試費 $999", GIAC_STD)
price("GX-CS|GX-FE|GX-IH|GX-IA", "考試費 $1,299（持有對應的有效證照為 $499）", "重考 $1,199；換證 $499")
FTNT = "官方總覽頁未列考試價格與時間"
price("FCF", "NSE 1–3：完成線上課程與測驗", FTNT); price("FCA", "NSE 4：通過監考考試（Pearson）", FTNT)
price("FCP NS|FCP PCS|FCP SO", "NSE 5／6：須先有 NSE 4，再通過一科監考考試", FTNT)
price("FCSS NS|FCSS PCS|FCSS SO|FCSS SASE", "NSE 7：須先有 NSE 4 與同路線的 NSE 5 或 6", FTNT)
price("FCSS OT", "須先有 NSE 4、NSE 5 或 6、NSE 7，再通過監考考試", FTNT)
price("FCX", "NSE 8：核心考試加一科選修，含實作考（ProctorU）", "須先有同路線的 NSE 4、5 或 6、7；" + FTNT)
price("CSM", "考試券 $150（含線上課程的套裝 $170）", "選擇題 40 題，60 分鐘，70% 及格，無報考資格")
price("DCBCLA", "申請費 $400，年費 $225；考試費官方頁面未列", "須 5 年實務經驗（近十年內）、稽核考試 75% 及格、七篇專題論述與推薦人")
ISA_N = "官方總覽頁未列價格、題數與時間；不需換證"
price("ISA CFS", "完成 IC32 課程並通過考試", ISA_N)
price("ISA CRAS", "須先有 Fundamentals Specialist；完成 IC33 課程並通過考試", ISA_N)
price("ISA CDS", "須先有 Fundamentals Specialist；完成 IC34 課程並通過考試", ISA_N)
price("ISA CE", "無獨立考試：取得四張 ISA/IEC 62443 證書後自動授予", ISA_N)
SABSA_N = "價格官方頁面未列，須洽授權訓練單位"
price("SABSA SCF", "兩個選擇題模組，各 48 題 60 分鐘，各須 75%", "須先上官方 Foundation 課程；" + SABSA_N)
price("SABSA SCP", "申論作業：5 題選 2 題，四週內繳交，由兩位 SABSA Master 評分，75% 及格", "須有 SCF 並上一門進階課程；" + SABSA_N)
price("SABSA SCM", "再上第二門進階課程並通過其考試，另須提交碩士級論文並通過審查", "須有 SCP；" + SABSA_N)
# price pass 3, 2026-11-25
price("C)ISRM|IS20|C)ISSA|C)DRE|C)IHE|C)HISSP|C)CSA|C)ISSM|C)TIA|C)SLO|C)SWAE|C)CSO|C)PEH|C)DFE|C)AICSO|C)NIS2|C)CFTA|C)PSH|C)PTC|C)SP|C)VA", "考試組合 $500（標價 $795），含備考指南、模擬測驗與兩次考試機會", "不須先上 Mile2 課程")
price("C)OL", "考試組合 $150（標價 $500），含兩次考試機會", "不須先上 Mile2 課程")
price("C)PTE", "考試組合 $500（標準版）或 $600（ANSI／DoD 8140 監考版）", "選擇題 100 題，2 小時，含兩次考試機會；無報考資格")
price("C)ISMS-LA|C)NFE|C)ISCAP", "現行「考試組合」目錄（32 項）未列此科", "價格無法查證")
price("GCPEH|CISP", "考試券 $190（240 天內兩次機會）", "選擇題 100 題，2 小時，70% 及格，無報考資格")
price("DCCRP", "申請費 $400，年費 $225；考試費官方頁面未列", "須 2 年實務經驗（近十年內），Cyber Resilience 考試 75% 及格")
price("DCBCA", "申請費 $400，年費 $225；考試費官方頁面未列", "須 2 年實務經驗（近十年內），稽核考試 75% 及格，五篇專題論述")
price("CIS LI", "課程 £2,195（未稅），含 IBITGQ 線上考試", "考試 90 分鐘；無報考資格，建議先上 Foundation 課程")
price("資安職能 核心", "訓練費 NT$8,000（3 日課程，含一次評量）", "評量 70 分及格，電腦化即測即評；複測每次 NT$300", "115 年起部分科目開放免訓評量；訓練費為 114 年上半年訓練說明的數字")
price("資安職能 專業", "訓練費 NT$8,000（3 日課程）或 NT$6,000（2 日課程），含一次評量", "須先持有「資通安全概論」有效證書；評量 70 分及格；複測每次 NT$300", "訓練費為 114 年上半年訓練說明的數字")
# price pass 4, 2026-11-25
price("GCPT", "考試券 $150（240 天內兩次機會）", "選擇題 40 題，60 分鐘，70% 及格，無報考資格")
price("CASM", "考試券 $150（240 天內兩次機會）", "選擇題 50 題，60 分鐘，70% 及格，無報考資格")
LPI_N = "依國家分三級定價，括號內為第二、三級"
price("LPIC-1", "兩科（101、102），每科 $200（$165／$132）", LPI_N)
price("LPIC-2", "兩科（201、202），每科 $200（$165／$132）", LPI_N)
price("LPIC-3", "每個專長一科（303 為 Security），每科 $200（$165／$132）", LPI_N)
JNPR = "Juniper 認證計畫官方 FAQ（HPE Networking 訓練支援站）"
price("JNCIA Sec", "考試費 $200", JNPR); price("JNCIS Sec", "考試費 $300", JNPR); price("JNCIP Sec", "考試費 $400", JNPR)
price("JNCIE Sec", "實作考費用 $1,600", "須持有有效的 JNCIP-SEC；" + JNPR)
ITIL_N = "PeopleCert 於 2026-01 推出 ITIL（Version 5），ITIL 4 各模組預定 2027-12-31 停考（第三方報導，未向官方頁面查證）"
price("ITIL Fdn", "PeopleCert 美國商店考試組合約 $690（第三方整理）", ITIL_N)
price("ITIL MP|ITIL SL|ITIL Master", "Foundation 以上各模組須先上認可課程；價格官方頁面未能讀取", ITIL_N)
# price pass 5, 2026-11-25
price("OSCP+", "單考 $1,699；課程加一次考試 $1,499（90 天，標價 $1,749）；Learn One $2,199／年（標價 $2,749，含兩次考試）", "24 小時實作考，全程監考；OSCP+ 效期三年")
price("AAISM", "考試費 $599（會員 $459），通過後另繳申請費 $50", "須持有有效的 CISM 或 CISSP")
price("CCD", "48 小時實作考", "無正式報考資格，建議 1 年以上經驗；價格在購買頁，證照頁未列")
price("CKAD", "考試費 $445（含一次免費重考）", "線上監考實作，約 2 小時")
price("LFCA", "考試費 $250（含一次重考）", "線上監考選擇題，90 分鐘；效期兩年")
price("Google ACE", "報名費 $125", "50–60 題，2 小時，無報考資格；效期三年")
price("ASIS APP", "100 題計分加 25 題不計分的選擇題", "須 1 年以上相關經驗；費用在認證手冊，頁面未列")
price("GRCP", "無單獨考試費：須購買 All Access Pass（$875），含考試與重考", "100 題計分，2 小時，70 題答對及格；無學經歷要求")
price("CFCE", "同儕審查四個月，之後實作（最長 30 天）加筆試（最長 14 天），兩者皆須 80%", "須 72 小時鑑識訓練與背景查核；費用頁面未列，參加 BCFE 訓練者免證照費")
price("CSTM", "考試費 £500（未稅）", "選擇題 100 題 1 小時、筆試 1 小時、實作 2 小時、口試 15–30 分鐘")
price("SecAI+", "CY0-001，2026-02-17 推出", "最多 60 題（選擇題加實作題），60 分鐘，600 分及格；價格官方頁面未列")
price("CSTL", "實作滲透測試 4.5 小時，前有範疇訪談、後有口頭簡報與面談", "價格與報考資格官方頁面未列")
price("GRCA", "無單獨考試費：須購買 All Access Pass（$875），含考試與重考", "100 題計分，2 小時，70 題答對及格；建議先取得 GRCP，非必要")
price("Zach EAA", "須上 4 天 Level 1 課程並通過 2 小時線上考試", "證照費含在課程價格內，金額官方頁面未列")
price("Zach EAP", "繳交個案研究審查", "費用已含在 Level 1 課程內，金額官方頁面未列")
price("Zach EAPro", "官方頁面僅列出級別名稱，未說明要求與費用")
price("RHCA", "無獨立考試：持有 RHCE 加同一專長的三張 Specialist 證照後自動授予", "價格官方頁面未列")
price("SCE", "考試費 $195", "80 題，90 分鐘，70% 及格；須先有 SCA（SLES 12 或 15）")
price("WCNA", "每次 $299", "100 題是非與選擇題，2 小時，只分及格與否")
price("PCI QSA", "公司註冊費與個人訓練認證費見官方收費表，頁面未列金額", "須任職於合格的 QSA 公司並通過 QSA 訓練課程")
# issuers whose own pages did not give a price this pass: old 2024 figures removed rather than left as current
price("PECB 27005LM|PECB 27001LA|PECB 27001LI|PECB 27032CM|CLCSM|PECB 27032F|PECB 27005F", "考試與證照費含在訓練課程價格內，無單獨考試價", "依 PECB 同系列官方頁面；課程價依訓練單位而定")
price("PA NGFW|PA XSOAR|PA Cloud|PA XDR|PA NetSec|PA Cyber", "官方證照頁未列價格、題數與時間（在 PDF datasheet）", "2024 年舊價已移除")
price("S-ISME|S-CISO|S-CEHL|S-EHE|S-ISP|S-CSPL|S-TA|S-EHP|S-SA|S-EHF|S-ISF|S-SPF", "官方路線頁未列價格與考試細節", "2024 年舊價已移除")
price("EEXIN ISM|PEXIN ISM|EXIN 27001E|EXIN PCSA|EXIN 27001P|EXIN PCSerM|EXIN PCSM|EXIN PCD|EXIN PCA|EPDPF|EXIN CIT|EEHF|EPDPE|FEXIN|EXIN 27001F|EPDPP", "找不到官方價目；多數經訓練機構報名，價格依機構而定", "2024 年舊價已移除")
price("CIAM|CIPA|CIGE|CRFS|CAMS|CDP|CIST", "須為 Identity Management Institute 會員並通過線上考試", "官方頁面未列費用；2024 年舊價已移除")
price("CCFE|CMFE|CSSA|CDRP|CMWAPT|CRTOP|CREA|CSAP", "官方連結現只顯示訓練營梯次，查不到證照考試與價格", "2024 年舊價已移除")
price("OPST|CHAT|OPSA|OWSE|OPSE|CHA", "官方頁面讀取失敗，無法查證價格", "2024 年舊價已移除")
price("CIS LA|CIS RM|CIS IA|CISRM|CCRMP|CITGP|CSX-F|CIRM Fdn|C CS F|CIS F", "考試含在訓練課程內（IBITGQ 線上考試），本次僅查到 CIS LI 課程 £2,195 未稅", "各課程價格未逐一查證；2024 年舊價已移除")
# price pass 6 (final sweep), 2026-11-25
price("DV MoS", "課程 $2,500（含稅與結業證書）", "3 天線上課程，無考試，發結業證書")
price("DV OTD|DV AOPH|DV MILF", "同單位 Malware on Steroids 課程為 $2,500；本課程頁未讀", "無考試，發結業證書；2024 年舊價已移除")
price("CSAE", "25 天課程後接 48 小時實作考，含一次考試", "無報考資格；價格須經申請表取得，官方頁面未列")
price("DACRP", "申請費 $200，年費 $200；考試費官方頁面未列", "適用於經驗未滿 2 年者；Cyber Resilience 考試 75% 及格")
price("DCRMP", "官方頁面本次讀到空白內容", "同系列 DRI 證照申請費 $400、年費 $225；2024 年舊價已移除")
price("CISST", "考試券 $190（240 天內兩次機會）", "選擇題 100 題，2 小時，70% 及格")
price("CFA", "考試券 $150（240 天內兩次機會）", "選擇題 40 題，60 分鐘，70% 及格")
price("CPD|CASST|PPM|CSP|CSST|CAD|CAC", "GAQM 考試券依科目為 $150 或 $190（240 天內兩次機會）", "本科目頁面未逐一讀取；2024 年舊價已移除")
price("CAWFE", "筆試 125 題（開書、最長 8 小時、80% 及格），通過後 30 天內完成實作考", "須為 IACIS 會員或繳交方案費；金額官方頁面未列")
price("TUV COSTE", "課程 €3,470（未稅），含 TÜV Austria 人員認證考試", "3 天課程；考試形式官方頁面未說明")
price("TUV COSM|TUV COSP", "同單位 COSTE 課程為 €3,470 未稅含考試；本課程頁未讀", "2024 年舊價已移除")
price("ASIS PCI", "125 題計分加 15 題不計分的選擇題", "須 3–5 年調查經驗（其中 2 年案件管理）；費用在認證手冊，頁面未列")
UNREAD = "官方頁面讀取失敗、被擋或需登入，無法查證價格"
price("VCDX DCV|VCIX DCV|VCIX NV|VCP DCV|VCP NV|F5 CSE Sec|F5 CTS APM|F5 CTS DNS|F5 CA|BCS PCIRM|BCS PCIAA|BCS FISMP|CIISec ICSF|IIBA CCA|CTPRA|CTPRP|CSBA|CCP|CSCS|EnCE|CFSR|CACS|OSCE3|PgMP|CAPM|BTL1|Fair Fdn|Apple ACSP|TUV CyAware|TUV COTCP|TUV CySec|TUV ITSM|TUV MSA|TUV Auditor|ISMI CSMP|ISMI CSM|M_o_R P|M_o_R Fdn|CSFA|ITS-NS|ITS-C|SFCTA|SFCCCC|SF CIAMD|CCSM|MAD SOCA|MAD CTI|OSMR|PACES|ACE|CSR", UNREAD, "2024 年舊價已移除")
price("CCSA@training-certifications.checkpoint.com", UNREAD, "2024 年舊價已移除"); price("CCSE@training-certifications.checkpoint.com", UNREAD, "2024 年舊價已移除"); price("CCSA@ecfirst.biz", UNREAD, "2024 年舊價已移除")
price("CIOTSP|CCSC|CFR", "官方頁面現只顯示訓練梯次，未列考試代碼、題數與價格", "2024 年舊價已移除")
price("CIPT|CIPP", "官方頁面未列題數、時間與價格（在考生手冊與商店頁）", "2024 年舊價已移除")
price("TOGAF|TOGAF Fdn", "現行名稱為 TOGAF Enterprise Architecture Foundation／Practitioner（考試 OGEA-101、102、103）", "價格在官方收費表 PDF，未讀；2024 年舊價已移除")
price("CSA CGC|Cloud Essnt", "官方頁面現只介紹課程，未列考試與價格", "2024 年舊價已移除")
price("CREST CCHIA|CREST CCNIA|CREST CSAS", "不在 CREST 官方現行證照總表（12 張）", "2024 年舊價已移除")
price("ISA CAP", "ISA 62443 總覽頁未涵蓋此證照，未查", "2024 年舊價已移除")
price("SecOT+", "預購中，預計 2026-12 推出，考試代碼 SOT-001", "第三方預購價 $294，非官方定價")
price("eCRA", "即將推出，預計 2026 年秋冬", "維護者提供，未能向官方頁面查證")
price("eAIPT", "即將推出，預計 2026 年秋冬；專業級實作考試", "維護者提供，未能向官方頁面查證")
for _l, (_q, _h, _p, _c) in GIAC.items():
    _fee = {"GFACT": "$399", "GISF": "$499"}.get(_l, "$999")
    price(_l, f"考試費 {_fee}", f"{_q} 題，{_h} 小時，{_p}% 及格" + ("；含 CyberLive 實作題" if _c else "；無實作題"))
price("GSE", "無獨立考試", "須取得 6 張 Practitioner 與 4 張 Applied Knowledge 證照")
price("GSP", "無獨立考試", "須取得 3 張 Practitioner 與 2 張 Applied Knowledge 證照")
price("SSAP", "50 題 2 小時，開書", "無報考資格")

# every PRICE entry carries: kind of price, source, date read, confidence
META = {}


def meta(labels, **kw):
    for l in labels.split("|"):
        META.setdefault(l, {}).update(kw)


OFFICIAL = "官方頁面"; THIRD = "第三方"; OWNER = "維護者提供，未經官方驗證"
meta("Security+|A+|Net+|Cloud+|Linux+|Server+|Project+|CySA+|Pentest+|SecurityX", kind="第三方零售參考價", conf=THIRD,
     date="2026-11-23", url="")
meta("eJPT|eCPPT|eWPT|eWPTX|eMAPT|eCIR|eCTHP|eCDFP|eEDA", kind="官方考試券（未驗證）", conf=OWNER,
     url="https://checkout.ine.com/account")
meta("eCRA|eAIPT", kind="尚未開賣", conf=OWNER, url="")
meta("CRTO", kind="官方課程含考試", url="https://training.zeropointsecurity.co.uk/courses/red-team-ops")
meta("CRTL", kind="第三方價格", conf=THIRD, date="2026-11-10", url="https://training.zeropointsecurity.co.uk/courses/red-team-ops-ii")
meta("SC-900|AZ-900", conf=OWNER, url="https://learn.microsoft.com/zh-tw/credentials/certifications/frequently-asked-questions")
meta("SC-200|SC-300|SC-100|AZ-104|AZ-305|SC-401|SC-500", url="https://learn.microsoft.com/zh-tw/credentials/certifications/frequently-asked-questions")
meta("OSEP|OSWE|OSED|OSWA|OSDA|OSTH|OSIR|OSAI", kind="官方課程含考試", url="https://www.offsec.com/pricing/")
meta("HTB CJCA|HTB CPTS|HTB CWES|HTB CDSA|HTB COAE|HTB CWEE|HTB CAPE|HTB CWPE|HTB CDEP", kind="官方考試券",
     url="https://academy.hackthebox.com/preview/certifications")
meta("CC|SSCP|CGRC|CSSLP|CCSP|CISSP|CISSP Concentrations", url="https://www.isc2.org/register-for-exam/isc2-exam-pricing")
meta("CCNA|CCNP Sec|CCNP Ent|CCNP Cyber|CCNP Auto|CCIE Ent", url="https://www.cisco.com/site/us/en/learn/training-certifications/exams/index.html")
meta("CEH", kind="官方考試券", url="https://store.eccouncil.org/product/ceh-vue-exam-voucher/")
meta("CHFI", kind="官方考試券", url="https://store.eccouncil.org/product/chfi-ecc-exam-voucher/")
meta("CND", kind="官方考試券", url="https://store.eccouncil.org/product/cnd-ecc-exam-voucher/")
meta("ECIH", kind="官方考試券", url="https://store.eccouncil.org/product/ecih-ecc-exam-voucher/")
meta("SecOT+", kind="第三方預購價", conf="考試代碼與時程為官方頁面，價格為第三方", url="https://www.comptia.org/en-us/certifications/secot/")
meta("BTL2|MTIA|DV RTOS|PDSO CDE|OSIP|CCE|CCIE Sec", kind="官方課程或套裝價")
meta("SOG CAPenX|SOG CAPen|SOG CNPen", url="https://pentestingexams.com/")
meta("C)ISSO|SSAP|CACE|OSEE|OSWP|CREST CCTINF|CREST CRT|CREST CSAM|CREST CCTIM", kind="無價格資訊")
meta("OSCC", kind="官方課程價")
meta("DV OTD|DV AOPH|DV MILF|CSAE|DCRMP|CPD|CASST|PPM|CSP|CSST|CAD|CAC|CAWFE|TUV COSM|TUV COSP|ASIS PCI|VCDX DCV|VCIX DCV|VCIX NV|VCP DCV|VCP NV|F5 CSE Sec|F5 CTS APM|F5 CTS DNS|F5 CA|BCS PCIRM|BCS PCIAA|BCS FISMP|CIISec ICSF|IIBA CCA|CTPRA|CTPRP|CSBA|CCP|CSCS|EnCE|CFSR|CACS|OSCE3|PgMP|CAPM|BTL1|Fair Fdn|Apple ACSP|TUV CyAware|TUV COTCP|TUV CySec|TUV ITSM|TUV MSA|TUV Auditor|ISMI CSMP|ISMI CSM|M_o_R P|M_o_R Fdn|CSFA|ITS-NS|ITS-C|SFCTA|SFCCCC|SF CIAMD|CCSM|MAD SOCA|MAD CTI|OSMR|PACES|ACE|CSR|CCSA@training-certifications.checkpoint.com|CCSA@ecfirst.biz|CCSE@training-certifications.checkpoint.com|CIOTSP|CCSC|CFR|CIPT|CIPP|TOGAF|TOGAF Fdn|CSA CGC|Cloud Essnt|CREST CCHIA|CREST CCNIA|CREST CSAS|ISA CAP", kind="無價格資訊", conf="官方頁面未列或讀不到價格")
meta("DV MoS|TUV COSTE", kind="官方課程含考試"); meta("DACRP", kind="官方申請費（不含考試費）"); meta("CISST|CFA", kind="官方考試券")
meta("PECB 27005LM|PECB 27001LA|PECB 27001LI|PECB 27032CM|CLCSM|PECB 27032F|PECB 27005F|PA NGFW|PA XSOAR|PA Cloud|PA XDR|PA NetSec|PA Cyber|S-ISME|S-CISO|S-CEHL|S-EHE|S-ISP|S-CSPL|S-TA|S-EHP|S-SA|S-EHF|S-ISF|S-SPF|EEXIN ISM|PEXIN ISM|EXIN 27001E|EXIN PCSA|EXIN 27001P|EXIN PCSerM|EXIN PCSM|EXIN PCD|EXIN PCA|EPDPF|EXIN CIT|EEHF|EPDPE|FEXIN|EXIN 27001F|EPDPP|CIAM|CIPA|CIGE|CRFS|CAMS|CDP|CIST|CCFE|CMFE|CSSA|CDRP|CMWAPT|CRTOP|CREA|CSAP|OPST|CHAT|OPSA|OWSE|OPSE|CHA|CIS LA|CIS RM|CIS IA|CISRM|CCRMP|CITGP|CSX-F|CIRM Fdn|C CS F|CIS F|CSTL|Zach EAA|Zach EAP|Zach EAPro|RHCA|PCI QSA", kind="無價格資訊", conf="官方頁面未列或讀不到價格")
meta("GRCA", kind="官方課程或套裝價")
meta("OSCP+", kind="官方考試費與課程價（分列）", url="https://www.offsec.com/courses/pen-200/")
meta("GRCP", kind="官方課程或套裝價"); meta("CCD|ASIS APP|CFCE|SecAI+", kind="無價格資訊")
meta("GCPT|CASM", kind="官方考試券")
meta("LPIC-1|LPIC-2|LPIC-3", kind="官方考試費", url="https://www.lpi.org/our-certifications/exam-pricing/")
meta("JNCIA Sec|JNCIS Sec|JNCIP Sec|JNCIE Sec", kind="官方考試費", url="https://hpe-networking-training.zendesk.com/hc/en-us/articles/360053374674-General-Certification-Frequently-Asked-Questions")
meta("ITIL Fdn", kind="第三方價格", conf=THIRD, url="https://tutorsbot.com/blog/itil-certification-cost")
meta("ITIL MP|ITIL SL|ITIL Master", kind="無價格資訊", conf=THIRD, url="https://www.superprof.com/blog/itil-certification-cost/")
meta("資安職能 核心|資安職能 專業", kind="官方訓練費（含評量）", conf="複測費與及格標準為資安署法規公告；訓練費取自機關轉載的官方訓練說明", url="https://gazette.nat.gov.tw/EG_FileManager/eguploadpub/eg031209/ch05/type1/gov87/num6/Eg.pdf", date="2026-11-25")
meta("C)ISRM|IS20|C)ISSA|C)DRE|C)IHE|C)HISSP|C)CSA|C)ISSM|C)TIA|C)SLO|C)SWAE|C)CSO|C)PEH|C)DFE|C)AICSO|C)NIS2|C)CFTA|C)PSH|C)PTC|C)SP|C)VA|C)OL|C)PTE", kind="官方考試組合價", url="https://mile2.com/exam-combos/")
meta("C)ISMS-LA|C)NFE|C)ISCAP", kind="無價格資訊", url="https://mile2.com/exam-combos/")
meta("GCPEH|CISP", kind="官方考試券"); meta("DCCRP|DCBCA", kind="官方申請費（不含考試費）"); meta("CIS LI", kind="官方課程含考試")
meta("CSM", kind="官方考試券"); meta("DCBCLA", kind="官方申請費（不含考試費）")
meta("ISA CFS|ISA CRAS|ISA CDS|ISA CE|SABSA SCF|SABSA SCP|SABSA SCM", kind="無價格資訊")
meta("PJPT|PNPT|PWPP|PWPA|PSAA|PAPA|PMRP", kind="官方課程含考試")
meta("MOIS|MBT|MCPT|MDFIR|MRE|MDSO|MRT|MVRE|MCSE|MPT|MTH|MCSF|MSAF|MCPE|MRCI", kind="官方課程或套裝價", url="https://www.mosse-institute.com/certifications.html")
meta("MICS", kind="無價格資訊", url="https://www.mosse-institute.com/certifications.html")
meta("C-AI/MLPen|CRTeamer|CBTeamer|C-ADPenX", kind="官方考試費", url="https://pentestingexams.com/")
meta("C-APIPen|CBFRPro|CKBPro|CDAPen|C-AgAIPen|SOG CMPen And|SOG CMPen iOS|CRTeamerX|CCPenX-Az|CBTeamerX|CCPenX-AWS|CBP|CBTP|CSEDP|SOG CAP|SOG CCSP-AWS|SOG NSP", kind="無價格資訊", url="https://pentestingexams.com/")
meta("GAIPS|GASAE|GOAA|GSOA|GCFA|GPEN|GCIA|GCAD|GCIL|GLIR|GSOM|GICSP|GX-CS|GX-FE|GX-IH|GX-IA", url="https://www.giac.org/pricing/")
meta("FCF|FCA|FCP NS|FCP PCS|FCP SO|FCSS NS|FCSS PCS|FCSS SO|FCSS SASE|FCSS OT|FCX", kind="無價格資訊", url="https://www.fortinet.com/training-certification")
meta("iPAS 初級|iPAS 中級", kind="官方報名費", conf="官方簡章（115 年度）", url="https://www.ipas.org.tw/api/proxy/uploads/certification/ISE/115%E5%B9%B4%E5%BA%A6%E8%B3%87%E8%A8%8A%E5%AE%89%E5%85%A8%E5%B7%A5%E7%A8%8B%E5%B8%AB%E8%83%BD%E5%8A%9B%E9%91%91%E5%AE%9A%E7%B0%A1%E7%AB%A0(%E5%88%9D%E3%80%81%E4%B8%AD%E7%B4%9A)_1150410_20260410115218.pdf", date="2026-11-25")
meta("IIA CIA", url="https://www.theiia.org/en/certifications/cia/")
meta("APMG 27001F|APMG 27001P|APMG 27001A|APMG 20000F|APMG 20000A|APMG 20000P|THM SEC1|THM SAL1|THM SAL2|THM PT1", kind="無價格資訊")
meta("SFSA", kind="無獨立費用")
meta("PDSO CDP", kind="官方課程含考試"); meta("RHCSA|RHCE|BSCP", kind="無價格資訊")
meta("CPENT", kind="無價格資訊；套裝價為維護者提供", conf="考試規則為官方頁面，套裝價為維護者提供", url="https://cert.eccouncil.org/certified-penetration-testing-professional-cpent.html", date="2026-11-25")
meta("LPT", kind="無獨立費用", conf=OFFICIAL, url="https://cert.eccouncil.org/certified-penetration-testing-professional-cpent.html", date="2026-11-25")
meta("CSA", conf="考試形式為官方頁面，價格為維護者提供", url="https://cert.eccouncil.org/certified-soc-analyst.html", date="2026-11-25")
meta("CCISO", url="https://cert.eccouncil.org/certified-chief-information-security-officer.html"); meta("CTIA", url="https://cert.eccouncil.org/certified-threat-intelligence-analyst.html")
meta("CASE", url="https://cert.eccouncil.org/ec-certified-application-security-engineer.html"); meta("EDRP", url="https://cert.eccouncil.org/ec-council-disaster-recovery-professional.html")
meta("CNDA", url="https://cert.eccouncil.org/cnda.html"); meta("CSCU", url="https://cert.eccouncil.org/certified-secure-computer-user.html")
meta("ECES", url="https://cert.eccouncil.org/ec-council-certified-encryption-specialist.html"); meta("ECSS", url="https://cert.eccouncil.org/ec-council-certified-security-specialist.html")
meta("CCISO|CTIA|CASE|EDRP|CNDA|CSCU|ECES|ECSS|PECB 27005RM|PECB 27001F", kind="無價格資訊")
meta("SC-401", url="https://learn.microsoft.com/en-us/credentials/certifications/information-security-administrator/"); meta("SC-200", url="https://learn.microsoft.com/en-us/credentials/certifications/security-operations-analyst/")
meta("SC-300", url="https://learn.microsoft.com/en-us/credentials/certifications/identity-and-access-administrator/"); meta("AZ-104", url="https://learn.microsoft.com/en-us/credentials/certifications/azure-administrator/")
meta("AZ-305", url="https://learn.microsoft.com/en-us/credentials/certifications/azure-solutions-architect/"); meta("SC-900", url="https://learn.microsoft.com/en-us/credentials/certifications/security-compliance-and-identity-fundamentals/")
meta("AZ-900", url="https://learn.microsoft.com/en-us/credentials/certifications/azure-fundamentals/")
meta("SC-401|SC-200|SC-300|AZ-104|AZ-305|SC-900|AZ-900", conf="考試時間與門檻為官方頁面；金額非官方頁面數字", date="2026-11-25")
meta("EISM", kind="無價格資訊", url="https://ciso.eccouncil.org/cciso-certification/eism-program/")
meta("CCSE@cert.eccouncil.org", kind="無價格資訊", url="https://cert.eccouncil.org/certified-cloud-security-engineer.html")
meta("CISA", url="https://www.isaca.org/credentialing/cisa"); meta("CRISC", url="https://www.isaca.org/credentialing/crisc"); meta("CGEIT", url="https://www.isaca.org/credentialing/cgeit")
meta("CDPSE", url="https://www.isaca.org/credentialing/certified-data-privacy-solutions-engineer"); meta("AAIR", url="https://www.isaca.org/credentialing/aair"); meta("AAIA", url="https://www.isaca.org/credentialing/aaia")
meta("CISA|CRISC|CGEIT|CDPSE|AAIR|AAIA", kind="官方考試費", conf=OFFICIAL, date="2026-11-25")
meta("SecurityX|Pentest+|Net+|Linux+|Cloud+|Server+|Project+|CySA+|A+", conf="考試形式為官方頁面，價格為第三方")
price("CCDE", "核心筆試 400-007 $450（120 分鐘）加實作考 $1,600", "實作考 8 小時，情境式；效期三年")
price("CCNP Sec", "核心考試 350-701 $400（120 分鐘）加一科專精考試 $300（90 分鐘）", "無報考資格；效期三年")
price("CCNP Ent", "核心考試 350-401 $400（120 分鐘）加一科專精考試 $300（90 分鐘）", "無報考資格；效期三年")
price("CCNP Auto", "核心考試 350-901 $400（120 分鐘）加一科專精考試 $300（90 分鐘）", "無報考資格；效期三年")
price("CCNP Cyber", "核心考試加一科專精考試", "無正式報考資格；效期三年；此頁未列考試代碼與價格")
price("CCNA", "考試 200-301 $300，120 分鐘", "無報考資格；v2.0 自 2027-02-03 起開考")
price("CCNA Cyber", "考試 200-201 $300，120 分鐘", "無正式報考資格；效期三年")
price("CCNA Auto", "考試 200-901 $300，120 分鐘", "無報考資格；效期三年")
price("CCT", "須通過一科考試", "無正式報考資格；此頁未列考試代碼與價格")
meta("CCDE", url="https://www.cisco.com/c/en/us/training-events/training-certifications/certifications/expert/ccde.html")
meta("CCNP Sec", url="https://www.cisco.com/c/en/us/training-events/training-certifications/certifications/professional/ccnp-security-v2.html")
meta("CCNP Ent", url="https://www.cisco.com/c/en/us/training-events/training-certifications/certifications/professional/ccnp-enterprise.html")
meta("CCNP Auto", url="https://www.cisco.com/site/us/en/learn/training-certifications/certifications/devnet/professional/index.html")
meta("CCNA", url="https://www.cisco.com/site/us/en/learn/training-certifications/certifications/enterprise/ccna/index.html")
meta("CCNA Cyber", url="https://www.cisco.com/c/en/us/training-events/training-certifications/certifications/associate/cyberops-associate.html")
meta("CCNA Auto", url="https://www.cisco.com/site/us/en/learn/training-certifications/certifications/devnet/associate/index.html")
meta("CCNP Cyber|CCT", kind="無價格資訊")
price("CM)ISSO|CM)DFI|CM)IPS|CM)ISRM|CM)DRE|CM)CTA|CM)CSSA", "四張證照套裝 $3,180（原價 $3,980）", "通過指定四張 Mile2 證照考試後授予，無獨立考試")
meta("CM)ISSO|CM)DFI|CM)IPS|CM)ISRM|CM)DRE|CM)CTA|CM)CSSA", kind="官方課程或套裝價", url="https://www.mile2.com/master-certifications/")
price("C)PTE", "選擇題 100 題，2 小時，線上應考", "建議 12 個月網路經驗；效期三年，每年 20 CEU")
meta("C)PTE", kind="無價格資訊")
meta("CREST CPSA|CREST CPIA|CREST CPTIA|CREST CRIA|CREST CRTIA|CREST CCTAPP|CREST CCSAS|CREST CCIM", kind="無價格資訊")
meta("GSE|GSP", kind="無價格資訊", url="https://www.giac.org/get-certified/giac-portfolio-certifications/"); price("CACE", "須 10 年經驗", "選擇、簡答與個案分析兩階段考試")

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
GIAC_ABEY = ("GIAC 價目表標示 In Abeyance（停止報考）", "https://www.giac.org/pricing/", "2026-11-24", "官方頁面")
DROP = {"GEVA": GIAC_ABEY, "GCPM": GIAC_ABEY, "GCWN": GIAC_ABEY, "GLEG": GIAC_ABEY, "GSNA": GIAC_ABEY,
        "FCSS ZTA": ("Fortinet 現行 NSE 1–8 已無 Zero Trust 路線", "https://www.fortinet.com/training-certification",
                     "2026-11-25", "官方頁面"),
        "eNDP": ("由 eEDA 直接取代（INE 官方部落格 2022-10-05）；退役日 2022-10-19 為第三方推定",
                 "https://ine.com/blog/enterprise-defense-admin-learning-path", "2026-11-25",
                 "取代關係為官方頁面，退役日期為第三方")}
MOSSE_GONE = ("發證單位的現行證照目錄已無此項（目錄未列，並非停考公告）", "https://www.mosse-institute.com/certifications.html",
              "2026-11-25", "官方頁面")
for _l in ("MCL", "MCD", "MESE", "MASE", "MNSE"):
    DROP[_l] = MOSSE_GONE
NCSC_CLOSED = ("NCSC 公告 CCP 方案已停止受理新申請與換證，既有證書認可至 2026-12；由 UK Cyber Security Council 的 Chartership 頭銜取代",
               "https://www.ncsc.gov.uk/information/about-certified-professional-scheme", "2026-11-25", "官方頁面")
for _l in ("NCSC CCPLP", "NCSC CCPSP", "NCSC CCPP"):
    DROP[_l] = NCSC_CLOSED

# still on the chart, but the issuer's own site raises a doubt; shown dashed with the note
FLAG = {
    "ITIL Fdn": "現況：第三方報導 ITIL 已出 Version 5（2026-01），ITIL 4 預定 2027-12-31 停考；官方頁面未能讀取（2026-11-25）",
    "OSMR": "現況：OffSec 的 EXP-312 課程頁未提到 OSMR 或任何考試，兩次讀取皆同（2026-11-25）",
    "CSA CGC": "現況：官方頁面只介紹 Cloud Governance & Compliance 課程，未提到考試或證書（2026-11-25）",
    "Cloud Essnt": "現況：官方頁面目前只介紹約 8 小時的自學課程，未列考試資訊（2026-11-25）",
    "CREST CCHIA": "現況：CREST 官方證照總表現列 12 張，未見此項；未找到停考公告（2026-11-25）", "CREST CCNIA": "現況：CREST 官方證照總表現列 12 張，未見此項；未找到停考公告（2026-11-25）", "CREST CRTSA": "現況：CREST 官方證照總表現列 12 張，未見此項；未找到停考公告（2026-11-25）", "CREST CSAS": "現況：CREST 官方證照總表現列 12 張，未見此項；未找到停考公告（2026-11-25）",
    "MAD SOCA": "現況：MITRE 官方頁面目前顯示 coming soon，是否可報名不明（2026-11-25）",
    "MAD CTI": "現況：MITRE 官方頁面目前顯示 coming soon，是否可報名不明（2026-11-25）",
    "SPLK-3001": "現況：Splunk 官方已將此證照列為 legacy（2026-11-24）",
    "CSR": "現況：官方頁面目前沒有開放報名的梯次（2026-11-24）",
    "PACES": "現況：原網域已轉址至 INE，找不到這張證照的官方頁面（2026-11-25）",
    "ACE": "現況：原網域已轉址至 Exterro，官網首頁與導覽列未見此證照（2026-11-25）",
    "TUV ITSM": "現況：官方頁面註記方案期間至 2024-03，是否仍辦理待確認（2026-11-25）",
}

RELABEL = {"IS20": ("IS18", "Mile2 IS18 Controls (formerly IS20)"),
           "CREST CCSAS": ("CREST CCRTS", "CREST Certified Red Team Specialist (formerly CCSAS)"),
           "CREST CSAM": ("CREST CCRTM", "CREST Certified Red Team Manager (formerly CCSAM)"),
           "CM)DFI": ("CM)CFI", "Mile2 Certified Master Cyber Forensics Investigator"),
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
REHOST = [("https://www.cisco.com/c/en/us/training-events/training-certifications/certifications/associate/ccna.html", "https://www.cisco.com/site/us/en/learn/training-certifications/certifications/enterprise/ccna/index.html"),
          ("hhttps://", "https://"),
          ("https://www.crest-approved.org/certification-careers/crest-certifications/crest-certified-simulated-attack-specialist", "https://www.crest-approved.org/crest-certified-red-team-specialist/"),
          ("https://www.crest-approved.org/certification-careers/crest-certifications/crest-certified-simulated-attack-manager", "https://www.crest-approved.org/skills-certifications-careers/crest-certified-red-team-manager/"),
          ("https://secops.group/", "https://pentestingexams.com/"),
          ("https://www.offsec.com/pwk-oscp", "https://www.offsec.com/courses/pen-200/"),
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
    ("CM)ISRM", 20, "Mile2 Certified Master Information Systems Risk Manager", "", "https://www.mile2.com/master-certifications/"),
    ("CM)DRE", 40, "Mile2 Certified Master Disaster Recovery Engineer", "", "https://www.mile2.com/master-certifications/"),
    ("CM)CTA", 37, "Mile2 Certified Master Cyber Threat Analyst", "", "https://www.mile2.com/master-certifications/"),
    ("CM)CSSA", 22, "Mile2 Certified Master Cybersecurity Systems Auditor", "", "https://www.mile2.com/master-certifications/"),
    ("CREST CCIM", 38, "CREST Certified Incident Manager", "", "https://www.crest-approved.org/certification-careers/crest-certifications/crest-certified-incident-manager/"),
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
    # INE and CompTIA, supplied by the maintainer on 2026-11-25
    ("eEDA", 3, "INE eLearnSecurity Enterprise Defense Administrator (replaces eNDP)", "", "https://ine.com/blog/enterprise-defense-admin-learning-path"),
    ("eCRA", 24, "INE Certified Risk Analyst", "", "https://ine.com/security/certifications", "soon"),
    ("eAIPT", 43, "INE Artificial Intelligence Penetration Tester", "", "https://ine.com/security/certifications", "soon"),
    ("SecOT+", 13, "CompTIA SecOT+", "", "https://www.comptia.org/en-us/certifications/secot/", "soon"),
    # Mile2
    ("C)AICSO", 23, "Mile2 Certified AI Cybersecurity Officer", "選擇題 100 題，2 小時", MILE2),
    ("C)NIS2", 25, "Mile2 Certified NIS2 Lead Auditor/Implementer", "選擇題 100 題，2 小時", MILE2),
    ("C)CFTA", 38, "Mile2 Certified Cyber Forensics Threat Analyst", "選擇題 100 題，2 小時", MILE2),
    ("C)OL", 20, "Mile2 Certified Organizational Leader", "選擇題 100 題，2 小時", MILE2),
]
for label, col_, name, detail, link, *flag in EXTRA:
    cls = next(c for lo_, hi_, c in COL_CLS if lo_ <= col_ <= hi_)
    css = ("font-size:0.48vw;" if len(label) > 8 else "") + ("opacity:0.55;border-style:dashed;" if flag else "")
    st = f' style="{css}"' if css else ""
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
    ov = {**O.get(it["label"], {}), **O.get(it["label"] + "@" + host, {})}   # label@host wins where two issuers share a label
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
    if lab in FLAG:
        if ' style="' in h[:h.index("href=")]:
            h = h.replace(' style="', ' style="opacity:0.55;border-style:dashed;', 1)
        else:
            h = h.replace(" href=", ' style="opacity:0.55;border-style:dashed;" href=', 1)
    pk = lab + "@" + it["host"] if lab + "@" + it["host"] in PRICE else lab
    if pk in PRICE and not (pk == lab and any(k.startswith(lab + "@") for k in PRICE)):
        def swap(m):
            first = m.group(2).split("\n")[0]
            return f' {m.group(1)}="' + first + "".join("\n    " + html.escape(l, quote=True) for l in PRICE[pk]) + '"'
        h = re.sub(r' (tooltip\w+)="([^"]*)"', swap, h, count=1)
        md = META.get(pk, {})
        src_line = f"價格來源：{md.get('conf', OFFICIAL)}｜{md.get('date', '2026-11-25')}"
    else:
        src_line = ""
    extra = ("\n    " + html.escape(FLAG[lab], quote=True) if lab in FLAG else "")
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
  </ul>
  <p>資料來源：{by_b['V']} 張屬於本次已讀取官方頁面的發證單位（多數是讀該單位的代表頁面，不是逐張查證）；{by_b['K']} 張依發證單位公開的通用考試形式判定，本次未讀取官方頁面；
  {by_b['U']} 張的官方頁面讀不到或尚未查，考試形式暫用該單位的預設值。另有 {n_band} 張無法從官方名稱判定級別，級別沿用 2024 原圖所在區段。
  同分或該列已滿時會落在相鄰列。
  本次另移除 {len(dropped)} 張停考、退役或已不在官方目錄的證照：{'、'.join(d['label'] for d in dropped)}（各自的原因與來源見 data/retired.csv）；
  另有 {len(FLAG)} 張現況有疑問，以虛線框標示並在提示文字說明；
  並補上官方已有、原圖未收的 {len(EXTRA)} 張（GIAC 8 張、The SecOps Group 15 張、Mile2 4 張）。
  價格方面，GIAC 全系列與另外 {len(PRICE)} 張已改為 2026 年 11 月官方頁面的數字，其餘仍是 2024 年的內容。</p>
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
import os
ddir = os.path.dirname(csv_path)
with open(os.path.join(ddir, "prices.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["label", "name", "price_text", "price_kind", "source_url", "checked", "confidence"])
    for i in sorted(items, key=lambda i: i["label"]):
        pk = i["label"] + "@" + i["host"] if i["label"] + "@" + i["host"] in PRICE else i["label"]
        if pk in PRICE and not (pk == i["label"] and any(k.startswith(pk + "@") for k in PRICE)):
            md = META.get(pk, {})
            url = md["url"] if "url" in md else i["href"]
            w.writerow([i["label"], i["name"], " / ".join(PRICE[pk]), md.get("kind", "官方考試費"), url,
                        md.get("date", "2026-11-25"), md.get("conf", OFFICIAL)])
with open(os.path.join(ddir, "flagged.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["label", "name", "note"])
    for i in items:
        if i["label"] in FLAG:
            w.writerow([i["label"], i["name"], FLAG[i["label"]]])
with open(os.path.join(ddir, "retired.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["label", "name", "reason", "source", "checked", "confidence"])
    for d in dropped:
        nm = html.unescape(re.search(r'tooltip\w+="([^"\n]*)', d["html"]).group(1))
        w.writerow([d["label"], nm, *DROP[d["label"]]])
moved = sum(1 for i in items if i["nrow"] != i["row"])
off = sum(1 for i in items if i["nrow"] != i["target"])
print(f"items {len(items)} | score {lo}-{hi} | basis {by_b} | moved rows {moved} | placed off-target {off} | dropped {len(dropped)}")
print("tier from 2024 band:", sum(1 for i in items if i["tsrc"].startswith("沿用")))

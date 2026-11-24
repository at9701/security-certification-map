# 資安證照地圖 Security Certification Roadmap（2026-11）

衍生自 [Paul Jerimy 的 Security Certification Roadmap](https://pauljerimy.com/security-certification-roadmap/)（最後更新 2024 年 7 月）。
沿用原版的版面與領域分欄，介面改為繁體中文，更新了之後的證照變動、加入台灣證照，並**把難度位置依公開規則全部重排**。

**本專案與原作者無關，也未經其背書；上下位置不是原作者的評級。**

- 線上版：`index.html`（GitHub Pages）
- 原始碼來源：[PaulJerimy/SecCertRoadmap](https://github.com/PaulJerimy/SecCertRoadmap)
- 證照數：512（原版 481）

## 排序規則

原作者沒有公開評分標準，只在變更紀錄提到「依研究與回饋調整」。本版改用可檢查的計分：

`分數 = 考試形式 + 8 × 官方級別 + 報考門檻 + 考試強度（須審查委員會或面試另加 3）`

| 項目 | 給分 |
|---|---|
| 考試形式 | 實作考 30、實作加筆試或面試 26、情境題／論述／口試 22、實作練習審核 20、選擇題加實作題 16、選擇題 12、修課結業 4 |
| 官方級別 | 入門 0、初階 1、專業 2、專家 3、頂級 4（各乘 8） |
| 報考門檻 | 無 0、僅建議經驗或須先修官方課程 3、須前置證照或 1–2 年經驗 6、3–4 年或兩層前置證照 10、5 年以上 16 |
| 考試強度 | 1 小時內 0、約 2 小時 2、3–4 小時 5、6–12 小時 8、24 小時以上 11（多日制不再加分） |

分數線性對應到 26 列；該列已滿時落在相鄰列。左右欄位（領域）不動。每張證照的判定與分數在頁面上滑鼠移過去就看得到，完整清單在 `data/ranked.csv`。

這套規則偏重「怎麼考」，所以實作考的證照（OffSec、Hack The Box、TCM 等）普遍上升，純選擇題的證照（CEH、Security+ 等）下降，靠年資門檻的管理類證照（CISSP、CISM）大致持平。這是規則的取捨，不是業界共識。

## 資料可信度（請先讀）

| 標記 | 張數 | 意義 |
|---|---|---|
| V | 186 | 2026-11 讀取過該發證單位的官方頁面。多數是讀該單位的一個代表頁面，**不是逐張查證** |
| K | 240 | 依發證單位公開的通用考試形式判定，這一輪沒有讀官方頁面 |
| U | 87 | 官方頁面讀不到或尚未查，考試形式暫用預設值 |

- 110 個來源中約 75 個已嘗試讀取，其中十多個被對方網站擋下或連結已失效；研究筆記在 `data/findings.md`。
- 42 張無法從官方名稱判定級別，級別沿用 2024 原圖所在區段。
- 多數證照的連結與價格仍是 2024 年 7 月的內容。已知失效或搬家的：EXIN、SECO、ISECOM、VMware（Broadcom）、The SecOps Group（已搬到 pentestingexams.com）、Security Blue Team（現為 Centri）。
- Fortinet 於 2026-07-15 改為八級制，圖上仍是舊名稱。
- 官方已有但圖上未收：Mile2 的 C)AICSO、C)NIS2 等；pentestingexams.com 的多張新證照。
- 讀不到官方頁面的單位：EXIN、SECO、ISECOM、VMware、PMI、Juniper、BCS、Axelos（ITIL）、CIISec、CSIAC、QAI、Shared Assessments。這些網站拒絕自動讀取或連結已失效，相關證照維持 U。

## 相對於 2024-07 原版的內容變更

- 更名／取代 19 項（SecurityX、OSCP+、HTB CWES、PMRP、CRTL、SC-401、SC-500、CCDL2、CM)CFI、Palo Alto 角色制、Cisco CCNA／CCNP Cybersecurity 與 Automation）
- 新增 34 張（OffSec、HTB、TCM、TryHackMe、CompTIA SecAI+、ISACA 與 GIAC 的 AI 類，以及 GIAC 價目表已有的 GCAD、GCIL、GLIR、GSOM、GX-CS、GX-FE、GX-IH、GX-IA）
- 台灣證照 4 張（iPAS 資訊安全工程師 初級／中級、資通安全職能評量證書 核心／專業）
- 移除 7 張（MS-100、AZ-220、ISACA CSX-P，以及 GIAC 標示停止報考的 GCPM、GCWN、GLEG、GSNA）

## 重新產生

`index.html` 由腳本產生，不要手改。

```bash
python3 tools/grid.py  source/Security-Certification-Roadmap9.html cells.json
python3 tools/build.py source/Security-Certification-Roadmap9.html cells.json built.html
python3 tools/rank.py  built.html index.html data/ranked.csv
```

- `tools/build.py`：內容變更（更名、新增、移除、中文化），清單在檔案內的 `REPLACE`、`REMOVE`、`ADD`、`TW`。
- `tools/rank.py`：計分與重新排版。各發證單位的預設值在 `HOST`，個別證照的判定用 `o(...)` 覆寫；改這裡再重跑就會重排。

## 授權

原作採 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)，本衍生版依相同授權釋出，見 `LICENSE`。

- 原作者：Paul Jerimy
- 修改：at9701，2026 年 11 月

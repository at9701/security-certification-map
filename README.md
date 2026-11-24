# Security Certification Roadmap（2026-11 非官方更新版）

[Paul Jerimy 的 Security Certification Roadmap](https://pauljerimy.com/security-certification-roadmap/) 的非官方修改版。原圖最後一次內容更新是 2024 年 7 月；這個版本沿用原版版面，只更新之後的證照變動，並加入台灣證照。

**本專案與原作者無關，也未經其背書。**

- 線上版：開啟 GitHub Pages 後即為 `index.html`
- 原始碼來源：[PaulJerimy/SecCertRoadmap](https://github.com/PaulJerimy/SecCertRoadmap)（`Security-Certification-Roadmap9.html`）
- 證照數：508（原版 481）

## 相對於 2024-07 原版的變更

| 類別 | 數量 | 內容 |
|---|---|---|
| 更名／取代 | 17 | CASP+ → SecurityX、OSCP → OSCP+、HTB CBBH → CWES、PJMR → PMRP、CRTO II → CRTL、SC-400 → SC-401、AZ-500 → SC-500、Palo Alto 六張舊證照改為角色制、Cisco CyberOps／DevNet 改為 CCNA／CCNP Cybersecurity 與 Automation |
| 新增 | 26 | OffSec（OSTH、OSIR、OSCC、OSAI）、HTB（CAPE、CWPE、COAE、CJCA、CDEP）、TCM（PJPT、PSAA、PWPA、PWPP、PAPA）、TryHackMe（SAL1、SAL2、SEC1、PT1）、CompTIA SecAI+、ISACA（AAISM、AAIR、AAIA）、GIAC（GOAA、GAIPS、GASAE、GSOA） |
| 台灣證照 | 4 | iPAS 資訊安全工程師 初級／中級、資通安全職能評量證書 核心／專業 |
| 移除 | 3 | MS-100、AZ-220、ISACA CSX-P（皆已停考） |
| 價格 | — | GIAC $979 → $999、PNPT → $399、ISC2 CC 免費 → $199 |

完整清單在 `index.html` 頁面下方。

## 已知限制

- **新增證照的位置（難度列）是修改者的判斷**，不是 Paul Jerimy 的評級。
- 未列在變更清單的約 430 張證照，連結與價格仍是 2024 年 7 月的內容，**未逐一重驗**。VMware（Broadcom 改制後）相關證照很可能已失效。
- SC-500 僅依 Microsoft 課程退役頁判定為 AZ-500 的後繼；ISC2 CC 的 $199、iPAS 中級費用來自第三方來源，請以官方頁面為準。
- Palo Alto 新舊證照官方說明沒有一對一對應，這裡按角色取最接近者。
- 圖表隨視窗寬度縮放，手機上需放大檢視。

## 重新產生

`index.html` 由腳本從原版 HTML 產生，不要手改。

```bash
python3 tools/grid.py source/Security-Certification-Roadmap9.html cells.json
python3 tools/build.py source/Security-Certification-Roadmap9.html cells.json index.html
```

- `tools/grid.py`：解析原版的 CSS grid（47 欄 × 27 列），算出每張證照與空格的位置。
- `tools/build.py`：所有變更都寫在這個檔案的 `REPLACE`、`REMOVE`、`ADD`、`TW` 清單裡，要增修證照改這裡再重跑。

## 授權

原作採 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)，本修改版依相同授權釋出，見 `LICENSE`。

- 原作者：Paul Jerimy
- 修改：at9701，2026 年 11 月

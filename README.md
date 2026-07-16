# Milora_tool

遊戲成就紀錄器的 GPL-3.0 純程式碼公開版，版本 `1.2.6.10`。

此套件只包含應用程式原始碼，不包含遊戲圖片、專案代表圖、社群品牌圖示、正式成就目錄、關聯資料、來源快照、資料庫、帳號、郵件、日誌或備份。首次啟動會建立空白資料庫，成就列表預設為空白。

## Windows 啟用方式

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\啟動後端.cmd
```

開啟 `http://127.0.0.1:8000`。公開版後端會同時提供 API 與前端靜態檔，不需要先安裝 IIS。

`OPEN_SOURCE_EMPTY_DATA=1` 會略過正式遊戲目錄啟動門檻。若自行匯入或同步第三方資料，必須確認資料來源授權及使用條款。

## 授權

本套件內由專案作者擁有權利的程式碼依 GNU General Public License v3.0 授權，完整條款見 `LICENSE`。外部依賴、遊戲名稱與商標仍適用各權利人的條款。

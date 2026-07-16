# 安全設定

- 不要提交 `.env`、資料庫、日誌、備份或 SMTP 密碼。
- 正式環境請使用 HTTPS、`APP_ENV=production` 與安全 Cookie。
- 請替換 `.env.example` 的範例站長信箱。
- 匯入外部資料前先在隔離環境檢查內容及來源。

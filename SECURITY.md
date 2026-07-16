# 安全設定

- 不要提交 `.env`、資料庫、日誌、備份或 SMTP 密碼。
- 正式環境請使用 HTTPS，將 `APP_ENV` 設為 `production`，並啟用安全 Cookie。
- 請設定專用 `SITE_OWNER_EMAIL`，不要沿用 `.env.example` 的範例地址。
- 匯入外部遊戲資料前，先在隔離環境檢查內容及來源。
- 公開問題回報不得附帶帳號、存取權杖、電子郵件內容或資料庫檔案。

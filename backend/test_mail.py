from __future__ import annotations

import sys
from email.message import EmailMessage

from backend.main import SMTP_FROM, deliver_email


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("用法：python -m backend.test_mail 收件信箱")

    message = EmailMessage()
    message["From"] = SMTP_FROM
    message["To"] = sys.argv[1]
    message["Subject"] = "遊戲成就紀錄器寄信測試"
    message.set_content("這是一封自架郵件伺服器測試信。")
    deliver_email(message)
    print("寄送程序完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

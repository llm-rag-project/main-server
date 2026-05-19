import smtplib
from datetime import datetime, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from app.core.config import settings


class EmailService:
    def __init__(self):
        self.host = settings.smtp_host
        self.port = settings.smtp_port
        self.user = settings.smtp_user
        self.password = settings.smtp_password
        self.from_addr = settings.smtp_from or settings.smtp_user

    def _check_config(self):
        if not self.user or not self.password:
            raise ValueError(
                "SMTP 설정이 되어있지 않습니다. "
                ".env에 SMTP_USER, SMTP_PASSWORD를 설정해 주세요."
            )

    def send_daily_report(
        self,
        to_emails: list[str],
        excel_bytes: bytes,
        keyword_name: str | None = None,
    ) -> None:
        self._check_config()

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        subject_keyword = f"[{keyword_name}] " if keyword_name else ""
        subject = f"{subject_keyword}AI 기사 모니터링 데일리 리포트 ({today_str})"

        body = f"""안녕하세요,

{today_str} 기준 AI 기사 모니터링 데일리 리포트를 첨부해 드립니다.
{f'키워드: {keyword_name}' if keyword_name else ''}

첨부 파일에서 기사별 AI 중요도 점수, 요약, 원문 링크를 확인하실 수 있습니다.

감사합니다.
AI 기사 모니터링 시스템
""".strip()

        msg = MIMEMultipart()
        msg["From"] = formataddr(("AI기사 모니터링 시스템", self.from_addr))
        msg["To"] = ", ".join(to_emails)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Excel 첨부
        filename = f"daily_report_{today_str}.xlsx"
        attachment = MIMEBase(
            "application",
            "vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        attachment.set_payload(excel_bytes)
        encoders.encode_base64(attachment)
        attachment.add_header(
            "Content-Disposition",
            f'attachment; filename="{filename}"',
        )
        msg.attach(attachment)

        with smtplib.SMTP(self.host, self.port) as server:
            server.ehlo()
            server.starttls()
            server.login(self.user, self.password)
            server.sendmail(self.from_addr, to_emails, msg.as_string())

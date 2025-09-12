# services/email_service.py
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

class EmailService:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("FROM_EMAIL", self.smtp_username)
        self.default_recipients = os.getenv("EMAIL_RECIPIENTS", "").split(",")
        self.default_recipients = [email.strip() for email in self.default_recipients if email.strip()]
    
    def send_error_notification(self, error_type: str, error_message: str, 
                              error_details: Optional[dict] = None,
                              recipients: Optional[List[str]] = None,
                              priority: str = "HIGH") -> bool:
        try:
            if not recipients:
                recipients = self.default_recipients
            
            if not recipients or not self.smtp_username or not self.smtp_password:
                print("❌ 이메일 설정이 완료되지 않았습니다.")
                return False
            
            subject = f"🚨 [{priority}] {error_type} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            html_body = self._create_error_email_body(error_type, error_message, error_details, priority)
            
            return self._send_email(recipients, subject, html_body)
            
        except Exception as e:
            print(f"❌ 이메일 발송 중 오류: {e}")
            return False
    
    def _create_error_email_body(self, error_type: str, error_message: str, 
                               error_details: Optional[dict], priority: str) -> str:
        priority_color = {"LOW": "#28a745", "MEDIUM": "#ffc107", "HIGH": "#fd7e14", "CRITICAL": "#dc3545"}
        color = priority_color.get(priority, "#dc3545")
        
        details_html = ""
        if error_details:
            details_html = "<h3>📋 오류 세부 정보:</h3><ul>"
            for key, value in error_details.items():
                details_html += f"<li><strong>{key}:</strong> {value}</li>"
            details_html += "</ul>"
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="border-left: 4px solid {color}; padding-left: 15px; margin-bottom: 20px;">
                    <h1 style="color: {color}; margin: 0;">🚨 시스템 오류 발생</h1>
                    <p style="margin: 5px 0; font-size: 14px; color: #666;">
                        {datetime.now().strftime('%Y년 %m월 %d일 %H시 %M분 %S초')}
                    </p>
                </div>
                
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
                    <h3 style="margin-top: 0;">🚨 오류 정보</h3>
                    <p><strong>오류 타입:</strong> {error_type}</p>
                    <p><strong>우선순위:</strong> {priority}</p>
                    <p><strong>오류 메시지:</strong></p>
                    <div style="background-color: #fff; padding: 10px; border-radius: 3px; border: 1px solid #dee2e6;">
                        <code style="color: #d63384;">{error_message}</code>
                    </div>
                </div>
                
                {details_html}
                
                <div style="background-color: #e7f3ff; padding: 15px; border-radius: 5px; margin-top: 20px;">
                    <h3 style="margin-top: 0; color: #0066cc;">🔧 권장 조치사항</h3>
                    <ul>
                        <li>로그 파일 확인</li>
                        <li>서버 상태 점검</li>
                        <li>필요시 수동 개입</li>
                        <li>자동 복구 시스템 확인</li>
                    </ul>
                </div>
            </div>
        </body>
        </html>
        """
        return html_body
    
    def _send_email(self, recipients: List[str], subject: str, html_body: str) -> bool:
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = self.from_email
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = subject
            
            html_part = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(html_part)
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                text = msg.as_string()
                server.sendmail(self.from_email, recipients, text)
            
            print(f"✅ 이메일 발송 완료: {len(recipients)}명에게 발송")
            return True
            
        except Exception as e:
            print(f"❌ 이메일 발송 실패: {e}")
            return False

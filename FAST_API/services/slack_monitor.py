# services/slack_monitor.py
import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.socket_mode.async_client import AsyncSocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from services.email_service import EmailService

class SlackMonitor:
    """
    Slack 메시지 모니터링 및 오류 감지 서비스
    """
    def __init__(self):
        self.slack_token = os.getenv("SLACK_BOT_TOKEN")
        self.app_token = os.getenv("SLACK_APP_TOKEN")
        self.channel_id = os.getenv("SLACK_CHANNEL_ID")
        self.email_service = EmailService()
        
        # Slack 클라이언트 초기화
        self.client = AsyncWebClient(token=self.slack_token)
        self.socket_client = AsyncSocketModeClient(
            app_token=self.app_token,
            web_client=self.client
        )
        
        # 오류 패턴
        self.error_patterns = [
            "검색 중 오류가 발생했습니다",
            "죄송합니다.*처리할 수 없습니다",
            "오류가 발생했습니다.*다시 시도해주세요",
            "API.*error.*failed",
            "HTTP.*401.*Unauthorized",
            "HTTP.*500.*Internal Server Error"
        ]
        
        self.alert_history = []
        self.max_alerts_per_hour = 5
    
    async def start_monitoring(self):
        """
        Slack 메시지 모니터링 시작
        """
        try:
            print("🔍 Slack 메시지 모니터링 시작...")
            
            # Socket Mode로 실시간 메시지 수신
            self.socket_client.socket_mode_request_listeners.append(self.handle_socket_mode_request)
            
            await self.socket_client.connect()
            
            # 모니터링 루프
            while True:
                await asyncio.sleep(1)
                
        except Exception as e:
            print(f"❌ Slack 모니터링 오류: {e}")
    
    async def handle_socket_mode_request(self, client: AsyncSocketModeClient, req: SocketModeRequest):
        """
        Socket Mode 요청 처리
        """
        try:
            if req.type == "events_api":
                # 이벤트 처리
                event = req.payload.get("event", {})
                
                if event.get("type") == "message":
                    await self.process_message(event)
                
                # 응답 전송
                client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))
                
        except Exception as e:
            print(f"❌ Socket Mode 요청 처리 오류: {e}")
    
    async def process_message(self, event: Dict):
        """
        메시지 처리 및 오류 감지
        """
        try:
            text = event.get("text", "")
            user = event.get("user", "")
            channel = event.get("channel", "")
            timestamp = event.get("ts", "")
            
            # 봇 메시지는 무시
            if event.get("bot_id") or event.get("subtype") == "bot_message":
                return
            
            # 오류 메시지 감지
            if self.is_error_message(text):
                await self.handle_error_detection(text, user, channel, timestamp)
                
        except Exception as e:
            print(f"❌ 메시지 처리 오류: {e}")
    
    def is_error_message(self, text: str) -> bool:
        """
        오류 메시지인지 확인
        """
        import re
        
        for pattern in self.error_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    async def handle_error_detection(self, message: str, user: str, channel: str, timestamp: str):
        """
        오류 감지 시 처리
        """
        try:
            # 중복 알림 방지
            if self._should_send_alert(message):
                error_details = {
                    "timestamp": datetime.now().isoformat(),
                    "slack_user": user,
                    "slack_channel": channel,
                    "slack_timestamp": timestamp,
                    "message": message
                }
                
                # 이메일 발송
                email_success = self.email_service.send_error_notification(
                    error_type="SLACK_ERROR",
                    error_message=message,
                    error_details=error_details,
                    priority="HIGH"
                )
                
                # Slack 알림 발송
                slack_success = await self.send_slack_alert(message, channel)
                
                if email_success or slack_success:
                    self.alert_history.append({
                        "timestamp": datetime.now(),
                        "message": message,
                        "user": user
                    })
                    
                    print(f"✅ Slack 오류 감지 및 알림 발송 완료")
                
                # 자동 복구 시도
                await self._attempt_auto_recovery("SLACK_ERROR")
                
        except Exception as e:
            print(f"❌ Slack 오류 처리 중 오류: {e}")
    
    async def send_slack_alert(self, error_message: str, channel: str) -> bool:
        """
        Slack 알림 발송
        """
        try:
            alert_message = f"""
🚨 **시스템 오류 감지**

**오류 메시지:** {error_message}
**감지 시간:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**채널:** #{channel}

자동 복구를 시도하고 있습니다...
            """
            
            response = await self.client.chat_postMessage(
                channel=channel,
                text=alert_message,
                username="System Monitor",
                icon_emoji=":warning:"
            )
            
            return response["ok"]
            
        except Exception as e:
            print(f"❌ Slack 알림 발송 실패: {e}")
            return False
    
    def _should_send_alert(self, message: str) -> bool:
        """
        알림 발송 여부 결정 (중복 방지)
        """
        now = datetime.now()
        recent_alerts = [
            alert for alert in self.alert_history
            if (now - alert["timestamp"]).seconds < 3600  # 1시간 내
        ]
        
        return len(recent_alerts) < self.max_alerts_per_hour
    
    async def _attempt_auto_recovery(self, error_type: str):
        """
        자동 복구 시도
        """
        try:
            # 간단한 복구 작업
            if error_type == "SLACK_ERROR":
                # FastAPI 컨테이너 재시작
                import subprocess
                
                result = subprocess.run(
                    ["docker-compose", "restart", "fastapi-app"],
                    capture_output=True, text=True, cwd="/path/to/your/project"
                )
                
                if result.returncode == 0:
                    # 복구 완료 알림
                    await self.send_recovery_notification(error_type)
                    
        except Exception as e:
            print(f"❌ 자동 복구 시도 중 오류: {e}")
    
    async def send_recovery_notification(self, error_type: str):
        """
        복구 완료 알림
        """
        try:
            recovery_message = f"""
✅ **자동 복구 완료**

**복구 작업:** {error_type}
**복구 시간:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

시스템이 정상적으로 복구되었습니다.
            """
            
            await self.client.chat_postMessage(
                channel=self.channel_id,
                text=recovery_message,
                username="System Monitor",
                icon_emoji=":white_check_mark:"
            )
            
        except Exception as e:
            print(f"❌ 복구 알림 발송 실패: {e}")
    
    def test_slack_connection(self) -> bool:
        """
        Slack 연결 테스트
        """
        try:
            response = self.client.auth_test()
            return response["ok"]
        except Exception as e:
            print(f"❌ Slack 연결 테스트 실패: {e}")
            return False

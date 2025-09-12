# services/error_monitor.py
import asyncio
import logging
import re
import subprocess
from datetime import datetime
from typing import Dict, List, Optional
from services.email_service import EmailService

class ErrorMonitor:
    """
    시스템 오류 모니터링 및 알림 서비스
    """
    def __init__(self):
        self.email_service = EmailService()
        self.error_patterns = {
            "SLACK_ERROR": [
                r"검색 중 오류가 발생했습니다",
                r"죄송합니다.*처리할 수 없습니다",
                r"오류가 발생했습니다.*다시 시도해주세요"
            ],
            "API_ERROR": [
                r"HTTP.*401.*Unauthorized",
                r"HTTP.*500.*Internal Server Error",
                r"API.*error.*failed"
            ],
            "DATABASE_ERROR": [
                r"database.*error",
                r"connection.*failed",
                r"sql.*error"
            ],
            "DOCKER_ERROR": [
                r"container.*failed",
                r"docker.*error",
                r"service.*unhealthy"
            ]
        }
        self.alert_history = []
        self.max_alerts_per_hour = 5
    
    async def monitor_docker_logs(self):
        """
        Docker 컨테이너 로그 모니터링
        """
        try:
            while True:
                # FastAPI 컨테이너 로그 확인
                result = subprocess.run(
                    ["docker-compose", "logs", "--tail=50", "fastapi-app"],
                    capture_output=True, text=True, cwd="/path/to/your/project"
                )
                
                if result.returncode == 0:
                    logs = result.stdout
                    await self._analyze_logs(logs)
                
                # 30초마다 체크
                await asyncio.sleep(30)
                
        except Exception as e:
            print(f"❌ 로그 모니터링 오류: {e}")
    
    async def monitor_slack_messages(self, slack_client):
        """
        Slack 메시지 모니터링
        """
        try:
            # Slack 메시지 스트림 모니터링
            for message in slack_client.rtm_read():
                if message.get('type') == 'message':
                    text = message.get('text', '')
                    if self._is_error_message(text):
                        await self._handle_error_detection("SLACK_ERROR", text)
                        
        except Exception as e:
            print(f"❌ Slack 모니터링 오류: {e}")
    
    async def _analyze_logs(self, logs: str):
        """
        로그 분석 및 오류 감지
        """
        lines = logs.split('\n')
        
        for line in lines:
            for error_type, patterns in self.error_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        await self._handle_error_detection(error_type, line)
                        break
    
    def _is_error_message(self, message: str) -> bool:
        """
        Slack 메시지가 오류 메시지인지 확인
        """
        error_indicators = [
            "검색 중 오류가 발생했습니다",
            "죄송합니다",
            "오류가 발생했습니다",
            "다시 시도해주세요",
            "처리할 수 없습니다"
        ]
        
        return any(indicator in message for indicator in error_indicators)
    
    async def _handle_error_detection(self, error_type: str, error_message: str):
        """
        오류 감지 시 처리
        """
        # 중복 알림 방지
        if self._should_send_alert(error_type, error_message):
            error_details = {
                "timestamp": datetime.now().isoformat(),
                "error_type": error_type,
                "message": error_message,
                "container": "fastapi-app"
            }
            
            # 이메일 발송
            success = self.email_service.send_error_notification(
                error_type=error_type,
                error_message=error_message,
                error_details=error_details,
                priority=self._get_priority(error_type)
            )
            
            if success:
                self.alert_history.append({
                    "timestamp": datetime.now(),
                    "error_type": error_type,
                    "message": error_message
                })
                
                print(f"✅ {error_type} 오류 감지 및 이메일 발송 완료")
            
            # 자동 복구 시도
            await self._attempt_auto_recovery(error_type)
    
    def _should_send_alert(self, error_type: str, error_message: str) -> bool:
        """
        알림 발송 여부 결정 (중복 방지)
        """
        now = datetime.now()
        recent_alerts = [
            alert for alert in self.alert_history
            if (now - alert["timestamp"]).seconds < 3600  # 1시간 내
            and alert["error_type"] == error_type
        ]
        
        return len(recent_alerts) < self.max_alerts_per_hour
    
    def _get_priority(self, error_type: str) -> str:
        """
        오류 타입별 우선순위 설정
        """
        priority_map = {
            "SLACK_ERROR": "HIGH",
            "API_ERROR": "CRITICAL", 
            "DATABASE_ERROR": "CRITICAL",
            "DOCKER_ERROR": "HIGH"
        }
        return priority_map.get(error_type, "MEDIUM")
    
    async def _attempt_auto_recovery(self, error_type: str):
        """
        자동 복구 시도
        """
        try:
            recovery_actions = {
                "SLACK_ERROR": self._restart_chatbot_service,
                "API_ERROR": self._restart_fastapi_container,
                "DATABASE_ERROR": self._restart_database_service,
                "DOCKER_ERROR": self._restart_docker_services
            }
            
            action = recovery_actions.get(error_type)
            if action:
                result = await action()
                if result:
                    # 복구 완료 알림
                    self.email_service.send_recovery_notification(
                        action_type=f"{error_type}_RECOVERY",
                        action_result="복구 작업 완료"
                    )
                    
        except Exception as e:
            print(f"❌ 자동 복구 시도 중 오류: {e}")
    
    async def _restart_chatbot_service(self) -> bool:
        """
        챗봇 서비스 재시작
        """
        try:
            result = subprocess.run(
                ["docker-compose", "restart", "fastapi-app"],
                capture_output=True, text=True, cwd="/path/to/your/project"
            )
            return result.returncode == 0
        except Exception as e:
            print(f"❌ 챗봇 서비스 재시작 실패: {e}")
            return False
    
    async def _restart_fastapi_container(self) -> bool:
        """
        FastAPI 컨테이너 재시작
        """
        try:
            result = subprocess.run(
                ["docker-compose", "down", "fastapi-app"],
                capture_output=True, text=True, cwd="/path/to/your/project"
            )
            await asyncio.sleep(5)
            
            result = subprocess.run(
                ["docker-compose", "up", "-d", "fastapi-app"],
                capture_output=True, text=True, cwd="/path/to/your/project"
            )
            return result.returncode == 0
        except Exception as e:
            print(f"❌ FastAPI 컨테이너 재시작 실패: {e}")
            return False
    
    async def _restart_database_service(self) -> bool:
        """
        데이터베이스 서비스 재시작
        """
        try:
            result = subprocess.run(
                ["docker-compose", "restart", "postgres"],
                capture_output=True, text=True, cwd="/path/to/your/project"
            )
            return result.returncode == 0
        except Exception as e:
            print(f"❌ 데이터베이스 재시작 실패: {e}")
            return False
    
    async def _restart_docker_services(self) -> bool:
        """
        전체 Docker 서비스 재시작
        """
        try:
            result = subprocess.run(
                ["docker-compose", "down"],
                capture_output=True, text=True, cwd="/path/to/your/project"
            )
            await asyncio.sleep(10)
            
            result = subprocess.run(
                ["docker-compose", "up", "-d"],
                capture_output=True, text=True, cwd="/path/to/your/project"
            )
            return result.returncode == 0
        except Exception as e:
            print(f"❌ Docker 서비스 재시작 실패: {e}")
            return False
    
    def start_monitoring(self):
        """
        모니터링 시작
        """
        print("�� 오류 모니터링 시스템 시작...")
        asyncio.create_task(self.monitor_docker_logs())

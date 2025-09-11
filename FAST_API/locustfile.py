# locustfile.py 수정
from locust import HttpUser, task, between
import random

class ChatbotUser(HttpUser):
    wait_time = between(1, 3)
    host = "https://43.201.185.192.nip.io"
    
    def on_start(self):
        # 각 유저마다 다른 테스트 계정으로 로그인
        user_id = random.randint(1, 100)
        self.login(f"test_user_{user_id}")
    
    def login(self, username):
        response = self.client.post("/auth/login", 
            json={"username": username, "password": "test123"})
        if response.status_code == 200:
            print(f"{username} 로그인 성공")
        else:
            print(f"{username} 로그인 실패: {response.status_code}")
    
    @task(5)
    def chat_question(self):
        questions = [
            "안녕하세요", "현재 날씨 알려줘", "추천 상품 있어?",
            "검은색 셔츠 추천해줘", "여름 옷 추천해줘", "가격대별로 추천해줘"
        ]
        question = random.choice(questions)
        
        response = self.client.post("/chat/", 
            json={"message": question},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            print(f"질문: {question} - 성공")
        else:
            print(f"질문: {question} - 실패: {response.status_code}")

from locust import HttpUser, task, between
import random

class SimpleUser(HttpUser):
    wait_time = between(1, 3)
    host = "https://43.201.185.192.nip.io"
    
    @task(5)
    def health_check(self):
        response = self.client.get("/health")
        print(f"Health check: {response.status_code}")
    
    @task(3)
    def home_page(self):
        response = self.client.get("/")
        print(f"Home page: {response.status_code}")
    
    @task(2)
    def metrics(self):
        response = self.client.get("/metrics")
        print(f"Metrics: {response.status_code}")

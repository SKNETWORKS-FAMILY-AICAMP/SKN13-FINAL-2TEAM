from locust import HttpUser, task, between

class FastAPIUser(HttpUser):
    wait_time = between(1, 3)
    host = "https://43.201.185.192.nip.io"
    
    @task(3)
    def home_page(self):
        self.client.get("/")
    
    @task(2)
    def health_check(self):
        self.client.get("/health")
    
    @task(1)
    def metrics(self):
        self.client.get("/metrics")

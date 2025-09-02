# SKN13-Final-2Team

## 프로젝트 개요
의류 추천 시스템을 위한 FastAPI 기반 웹 애플리케이션입니다.

## 주요 기능
- 사용자 인증 및 OAuth 로그인 (Google, Kakao)
- 취향 기반 의류 추천
- 상품 검색 및 찜목록 관리
- 챗봇을 통한 의류 추천
- 관리자 대시보드

## 관리자 기능 설정

### 1. 환경 변수 설정
프로젝트 루트에 `.env` 파일을 생성하고 다음 내용을 추가하세요:

```bash
# 관리자 계정 설정 (필수)
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=Admin123!

# 데이터베이스 설정
DB_USER=postgres
DB_PASSWORD=1234
DB_HOST=localhost
DB_PORT=5432
DB_NAME=musinsa

# 세션 보안
SESSION_SECRET=your-secret-key-here

# S3 설정
S3_BUCKET_NAME=your-bucket-name
AWS_REGION=ap-northeast-2
DATA_SOURCE=s3
S3_PRODUCTS_FILE_KEY=products/products.csv
```

### 2. 관리자 계정 생성
애플리케이션을 시작하면 `bootstrap_admin()` 함수가 자동으로 관리자 계정을 생성합니다.

### 3. 관리자 페이지 접근
- 관리자 계정으로 로그인하면 자동으로 `/admin/dashboard`로 리다이렉션됩니다
- 일반 사용자는 관리자 페이지에 접근할 수 없습니다
- 관리자 전용 기능: 캐시 관리, S3 데이터 관리, 시스템 모니터링

## 설치 및 실행

### Docker를 사용한 실행
```bash
cd FAST_API
docker-compose up --build
```

### 로컬 실행
```bash
cd FAST_API
pip install -r requirements.txt
python main.py
```

## API 문서
- FastAPI 자동 문서: `http://localhost:8000/docs`
- 관리자 페이지: `http://localhost:8000/admin/dashboard` (관리자만 접근 가능)

## 기술 스택
- Backend: FastAPI, SQLAlchemy, PostgreSQL
- Frontend: HTML, CSS, JavaScript
- OAuth: Google, Kakao
- 캐싱: Redis (예정)
- 모니터링: Prometheus, Grafana
# 🛍️ Ivle Malle - AI 기반 의류 추천 플랫폼

<div align="center">



**AI가 당신의 스타일을 완벽하게 이해하는 의류 추천 서비스**

</div>

## 📑 목차

- [📋 프로그램 설명](#-프로그램-설명)
- [🚀 프로그램 기능](#-프로그램-기능)
  - [1. 🎨 개인화 추천 시스템](#1-개인화-추천-시스템)
  - [2. 🤖 AI 챗봇 서비스](#2-ai-챗봇-서비스)
  - [3. 🖼️ 이미지 기반 검색](#3-이미지-기반-검색)
  - [4. 🔍 상품 검색 및 필터링](#4-상품-검색-및-필터링)
  - [5. ❤️ 찜 시스템](#5-찜-시스템)
  - [6. 👤 사용자 관리](#6-사용자-관리)
- [🛠️ 기술 스택](#️-기술-스택)
- [📋 요구사항](#-요구사항)
- [🚀 로컬 개발 환경 설정](#-로컬-개발-환경-설정)
- [📁 파일 구조](#-파일-구조)

---

## 📋 프로그램 설명

**Ivle Malle**은 AI 기반 의류 추천 플랫폼으로, 사용자의 개인적 취향과 상황을 분석하여 최적의 의류를 추천합니다.

### 🌟 주요 특징
- 🤖 **AI 기반 개인화 추천**: LangGraph 아키텍처의 지능형 추천 시스템
- 🖼️ **이미지 검색**: 업로드한 이미지와 유사한 의류 자동 검색
- 💬 **대화형 챗봇**: 자연어로 의류 추천 요청 및 상담
- 🔐 **소셜 로그인**: Google, Kakao 계정으로 간편 가입

---

## 🚀 프로그램 기능

### 1. 🎨 개인화 추천 시스템
- **3단계 필터링**: 스타일 → 체형 → 색상 순으로 정교한 추천
- **사용자 프로필**: 성별, 키, 몸무게, 선호 스타일/색상 관리
- **스타일 설문**: 취향 파악을 위한 맞춤형 설문조사

### 2. 🤖 AI 챗봇 서비스
- **전문 에이전트**: 5개의 특화된 AI 에이전트 (검색, 대화, 날씨, 일반, 후속질문)
- **컨텍스트 기억**: 이전 대화 내용을 기억한 연속적 대화
- **멀티모달 입력**: 텍스트, 이미지, 위치 정보 지원

### 3. 🖼️ 이미지 기반 검색
- **YOLO 객체 탐지**: 업로드 이미지에서 의류 자동 인식
- **Fashion-CLIP**: 이미지와 텍스트의 유사도 계산
- **벡터 검색**: Qdrant를 활용한 유사 상품 검색

### 4. 🔍 상품 검색 및 필터링
- **다중 필터**: 성별, 카테고리, 가격, 브랜드, 평점
- **실시간 검색**: API 기반 즉시 결과 반환
- **정렬 옵션**: 가격순, 이름순, 인기순

### 5. ❤️ 찜 시스템
- **즐겨찾기**: 관심 상품 저장 및 관리
- **비교 기능**: 찜한 상품들 간 상세 비교
- **통계 분석**: 찜 횟수 기반 인기 상품 랭킹

### 6. 👤 사용자 관리
- **소셜 로그인**: Google, Kakao OAuth 지원
- **마이페이지**: 찜 목록, 추천 히스토리, 설정 관리
- **피드백 시스템**: 추천 품질 개선을 위한 사용자 피드백

---

## 🛠️ 기술 스택

### Backend
- **Framework**: FastAPI 0.116.1
- **ASGI Server**: Uvicorn 0.35.0
- **Language**: Python 3.9+
- **Database**: PostgreSQL + SQLAlchemy 1.4.54
- **Authentication**: OAuth2 (Google, Kakao) + Authlib 1.6.1
- **Security**: bcrypt 4.3.0, PyJWT 2.10.1, cryptography 45.0.5

### AI/ML
- **LLM**: OpenAI 1.97.1 (GPT-4, GPT-4o-mini)
- **Computer Vision**: YOLO (ultralytics 8.3.192), OpenCV 4.10.*
- **Embedding Model**: Fashion-CLIP 0.2.2
- **Vector Database**: Qdrant Client 1.8.0
- **Deep Learning**: PyTorch 2.8.0+cpu, TorchVision 0.23.0+cpu
- **Data Processing**: pandas 2.3.1, numpy >=2.0,<3.0

### Frontend
- **Template Engine**: Jinja2 3.1.6
- **Styling**: CSS3, Responsive Design
- **JavaScript**: ES6+ (Vanilla JS)
- **Image Processing**: Pillow 10.4.0

### Infrastructure
- **Cloud Server**: AWS EC2
- **Containerization**: Docker, Docker Compose
- **Web Server**: Nginx (Reverse Proxy)
- **Cloud Storage**: AWS S3 (boto3 1.40.2)
- **Database**: AWS RDS PostgreSQL
- **Monitoring**: Prometheus Client 0.19.0, Prometheus FastAPI Instrumentator 7.0.0
- **HTTP Client**: httpx 0.28.1, requests 2.32.5

### Development Tools
- **Environment**: python-dotenv 1.1.1
- **Text Processing**: rapidfuzz 3.5.2
- **Multipart**: python-multipart 0.0.20

---

## 📋 요구사항

### 시스템 요구사항
- **Python**: 3.9 이상
- **Docker**: 20.10 이상 (권장)
- **메모리**: 최소 4GB RAM

### 필수 환경변수
```bash
# OpenAI
OPENAI_API_KEY=your_openai_api_key

# 데이터베이스 (RDS PostgreSQL)
DATABASE_URL=postgresql://username:password@your-rds-endpoint:5432/ivle_malle

# AWS S3
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
S3_BUCKET_NAME=your_bucket_name

# OAuth
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
KAKAO_CLIENT_ID=your_kakao_client_id
KAKAO_CLIENT_SECRET=your_kakao_client_secret

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=ivlle
```

---

## 🚀 로컬 개발 환경 설정

### 1. 저장소 클론 및 환경 설정
```bash
git clone https://github.com/your-username/ivle-malle.git
cd ivle-malle

# .env 파일 생성 및 환경변수 설정
touch .env
nano .env
```

### 2. Docker로 실행 (권장)
```bash
# Docker Compose로 모든 서비스 실행
docker-compose up -d

# 또는 Python으로 직접 실행
pip install -r requirements.txt
python main.py
```

### 3. 접속 확인
- **웹 애플리케이션**: http://localhost:8000
- **API 문서**: http://localhost:8000/docs
- **관리자 대시보드**: http://localhost:8000/admin

---

## 📁 파일 구조

```
FAST_API/
├── 📁 routers/           # API 라우터 (홈, 인증, 상품, 챗봇, 찜 등)
├── 📁 models/            # 데이터베이스 모델
├── 📁 schemas/           # Pydantic 스키마
├── 📁 crud/              # 데이터베이스 CRUD
├── 📁 services/          # 챗봇 로직
│   └── 📁 agents/        # AI 에이전트 (검색, 대화, 날씨 등)
├── 📁 modules/           # AI 모듈 (상의, 하의, 스커트, 원피스)
├── 📁 templates/         # Jinja2 HTML 템플릿
├── 📁 static/            # 정적 파일 (CSS, JS, 이미지)
├── 📁 utils/             # 유틸리티 함수
├── 📁 cache/             # 캐시 파일
├── 📄 main.py            # 메인 애플리케이션
├── 📄 db.py              # 데이터베이스 설정
├── 📄 image_recommender.py # 이미지 추천 시스템
├── 📄 requirements.txt   # Python 의존성
├── 📄 docker-compose.yml # Docker Compose 설정
└── 📄 *.md              # 프로젝트 문서들
```

### 📋 주요 파일
- **`main.py`**: FastAPI 애플리케이션 진입점
- **`services/llm_service.py`**: LangGraph 기반 LLM 서비스
- **`image_recommender.py`**: YOLO + Fashion-CLIP 이미지 추천
- **`routers/`**: 각 기능별 API 엔드포인트
- **`templates/`**: 웹 페이지 템플릿
- **`static/`**: CSS, JavaScript, 이미지 파일

---


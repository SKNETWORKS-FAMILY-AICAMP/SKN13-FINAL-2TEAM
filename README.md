# 🛍️ Ivle Malle - AI 기반 의류 추천 플랫폼

<div align="center">



**AI가 당신의 스타일을 완벽하게 이해하는 의류 추천 서비스**

</div>

---

## 👥 팀원

<table>
  <tr>
    <td align=center><b>구자현</b></td>
    <td align=center><b>김지민</b></td>
    <td align=center><b>민경재</b></td>
    <td align=center><b>박수빈</b></td>
    <td align=center><b>이유나</b></td>
    <td align=center><b>홍성의</b></td>
  <tr>
    <td align="center" width="16%">
      <b><img src="https://github.com/user-attachments/assets/73d20f9d-0ad1-4943-83e4-f7fce66be47e"/></b>
    </td>
    <td align="center" width="16%">
      <b><img src="https://github.com/user-attachments/assets/b11e7863-82d9-4723-81fb-7e9707839874"/></b>
    </td>
    <td align="center" width="16%">
      <b><img src="https://github.com/user-attachments/assets/82fa9e5a-b0d9-47fd-8c18-c25530f4fc16"/></b>
    </td>
    <td align="center" width="16%">
      <b><img src="https://github.com/user-attachments/assets/a03abcb1-4ccb-49e0-bb93-ff34dacefaa8"/></b>
    </td>
    <td align="center" width="16%">
      <b><img src="https://github.com/user-attachments/assets/9cda4399-df93-4878-ace3-719ba795d0c3"/></b>
    </td>
    <td align="center" width="16%">
      <b><img src="https://github.com/user-attachments/assets/a2ad1268-f1b9-49a7-a515-2c1805a37faf"/></b>
    </td>
  </tr>
  <tr>
    <td align="center" width="16%">
      <a href="https://github.com/Koojh99">
        <img src="https://img.shields.io/badge/GitHub-Koojh99-DFA4B3?logo=github" alt="구자현 GitHub"/>
      </a>
    </td>
    <td align="center" width="16%">
      <a href="https://github.com/Gogimin">
        <img src="https://img.shields.io/badge/GitHub-Gogimin-FBB795?logo=github" alt="김지민 GitHub"/>
      </a>
    </td>
    <td align="center" width="16%">
      <a href="https://github.com/rudwo524">
        <img src="https://img.shields.io/badge/GitHub-rudwo524-FBD284?logo=github" alt="민경재 GitHub"/>
      </a>
    </td>
    <td align="center" width="16%">
      <a href="https://github.com/subin0821">
        <img src="https://img.shields.io/badge/GitHub-subin0821-B7D9CC?logo=github" alt="박수빈 GitHub"/>
      </a>
    </td>
    <td align="center" width="16%">
      <a href="https://github.com/yunawawa">
        <img src="https://img.shields.io/badge/GitHub-yunawawa-ABC8DB?logo=github" alt="이유나 GitHub"/>
      </a>
    </td>
    <td align="center" width="16%">
      <a href="https://github.com/seonguihong">
        <img src="https://img.shields.io/badge/GitHub-seonguihong-CCB0E0?logo=github" alt="홍성의 GitHub"/>
      </a>
    </td>
  </tr>
  <tr>
    <td align="center">AI/ML </td>
    <td align="center">백엔드</td>
    <td align="center">서버 관리</td>
    <td align="center">PM/프론트엔드</td>
    <td align="center">AI/ML</td>
    <td align="center">데이터</td>
  </tr>
</table>

---


## 📑 목차

- [📋 프로그램 설명](#-프로그램-설명)
- [🚀 프로그램 기능](#-프로그램-기능)

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
- 🔐 **소셜 로그인**: Google 계정으로 간편 가입

---

## 🚀 프로그램 기능

### 1. 🎨 개인화 추천 시스템
**사용자 맞춤형 의류 추천의 핵심 기능**

- **3단계 필터링 알고리즘**:
  - 1단계: 사용자 선호 스타일 기반 상품 선별 (Casual, Street, Formal, Minimal)
  - 2단계: 체형 유사 사용자들의 찜 데이터 기반 개인화
  - 3단계: 선호 색상으로 최종 필터링
- **사용자 프로필 관리**: 성별, 키, 몸무게, 선호 스타일/색상 저장
- **스타일 설문조사**: 10개 문항의 맞춤형 설문으로 취향 파악
- **홈페이지 추천 섹션**: "(사용자)님이 좋아할 만한 콘텐츠" 개인화 추천

### 2. 🤖 AI 챗봇 서비스
**LangGraph 아키텍처 기반 지능형 대화 시스템**

- **5개 전문 AI 에이전트**:
  - **SearchAgent**: "파란색 셔츠", "나이키 운동화" 등 구체적 상품 검색
  - **ConversationAgent**: "데이트룩", "면접복", "파티룩" 등 상황별 추천
  - **WeatherAgent**: 현재 날씨와 위치 기반 의류 추천
  - **GeneralAgent**: 일반 대화 및 인사 처리
  - **FollowUpAgent**: "이거 말고 다른 거", "더 싼 거 있어?" 등 후속 질문
- **컨텍스트 기억 시스템**: 이전 대화 내용을 기억한 연속적 대화

### 3. 🖼️ 이미지 기반 검색
**컴퓨터 비전 기술을 활용한 이미지 검색**

- **YOLO 객체 탐지**: 업로드된 이미지에서 의류 객체 자동 인식 및 크롭
- **Fashion-CLIP 임베딩**: 이미지와 텍스트를 벡터로 변환하여 유사도 계산
- **Qdrant 벡터 검색**: 유사한 의류 상품을 벡터 공간에서 검색
- **GPT-4 Vision**: 이미지 분석 및 카테고리 자동 분류

### 4. 🔍 상품 검색 및 필터링
**다양한 조건으로 상품을 찾는 고급 검색 시스템**

- **다중 필터 옵션**:
  - 성별: 남성, 여성, 공용
  - 카테고리: 상의, 하의, 스커트, 원피스
  - 가격대: 최소/최대 가격 설정
  - 브랜드: 브랜드명 검색
- **실시간 검색**: API 기반 즉시 결과 반환 (20개씩 페이지네이션)
- **정렬 옵션**: 가격순(낮은순/높은순), 이름순, 인기순
- **검색 결과 최적화**: 캐싱을 통한 빠른 응답 속도

### 5. ❤️ 찜 시스템
**관심 상품 관리 및 비교 분석**

- **즐겨찾기 기능**: 관심 상품 저장 및 관리
- **비교 기능**: 찜한 상품들 간 상세 비교 (가격, 브랜드 등)
- **인기순 정렬**: 찜 횟수 기반 인기 상품 랭킹 시스템
- **개인화**: 사용자별 찜 목록 관리 및 히스토리
- **소셜 기능**: 찜 데이터를 활용한 개인화 추천

### 6. 👤 사용자 관리
**완전한 사용자 계정 및 프로필 시스템**

- **소셜 로그인**: Google 로그인 지원
- **마이페이지**: 찜 목록, 추천 히스토리, 개인 설정 관리
- **프로필 관리**: 개인정보, 선호도, 스타일 설정
- **피드백 시스템**: 추천 품질 개선을 위한 사용자 피드백 수집
- **세션 관리**: 안전한 로그인 상태 유지

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
git clone https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN13-FINAL-2TEAM.git

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
### 🎬 시연 영상

<div align="center">
  
[![Ivle Malle 시연](https://img.youtube.com/vi/DNN0Q7pK3cI/0.jpg)](https://www.youtube.com/watch?v=DNN0Q7pK3cI)

</div>

---

### 📋 회고록

<table>
  <tr>
    <td width="80" align="center"><strong>팀원</strong></td>
    <td><strong>한줄 회고</strong></td>
  </tr>
  <tr>
    <td align="center">구자현</td>
    <td>두 달동안 yolo모델 학습부터 데이터 파이프라인 구축, 챗봇 연결까지 정말 많은걸 해본 프로젝트였습니다. 이미지 관련해서 처음 생각했던 기능들이 잘된거 같기도 하고, 또 완벽한 성능은 아니라서 아쉽기도 해서,, "시간이 많았으면 좋았을 텐데"하는 아쉬움도 정말 많이 들었습니다. 그럼에도 불구하고 이번 프로젝트를 통해 하고 싶은 분야도 해보고, 많은걸 얻게 되는 프로젝트라고 생각합니다.  
    </td>
  </tr>
  <tr>
    <td align="center">김지민</td>
    <td>마지막 프로젝트는 6개월간 SKN에서 쌓은 AI 지식과 경험을 최대한 활용한 도전이었습니다 🤯 데이터 수집과 전처리 과정을 자동화하며 효율성을 높였고, 주로 백엔드를 다루면서 프론트엔드 경험까지 쌓으며 전반적인 서비스 구현 능력을 향상시켰습니다 ✌️ 부족한 부분도 있었지만, 이번 프로젝트를 통해 얻은 배움이 앞으로의 성장에 큰 밑거름이 될 것이라 생각합니다. 앞으로도 계속 발전하기 위해 노력하겠습니다. 😊</td>
  </tr>
  <tr>
    <td align="center">민경재</td>
    <td>두 달 동안 서버 오류 해결부터 Slack 모니터링 시스템 구축까지, API 키 설정의 중요성부터 Git 충돌 해결까지, 개발의 모든 단계를 경험하며 많은 것을 배우고 성장할 수 있었던 뜻깊은 시간이었습니다. 모두 수고하셨습니다!!</td>
  </tr>
  <tr>
    <td align="center">박수빈</td>
    <td></td>
  </tr>
  <tr>
    <td align="center">이유나</td>
    <td>이번 프로젝트는 역시 마지막 프로젝트 답게 좀 고민을 많이 하고 힘들었습니다🥹 YOLO 와는 더 이상 만나기 싫어졌구요,,, 패션을 다루다 보니 하고 싶은 것도 많았기 때문에 아쉬움도 많지만 좋은 팀원들 덕분에 성공적으로 끝마친 것 같습니다~! 모두들 수고많으셨습니다!!😆</td>
  </tr>
  <tr>
    <td align="center">홍성의</td>
    <td>두 달 동안 많은 것을 배우고 경험할 수 있었던 뜻깊은 시간이었습니다. 우리 팀 파이팅!</td>
  </tr>
</table>

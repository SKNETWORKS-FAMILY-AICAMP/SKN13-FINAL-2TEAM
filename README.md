###### SKN13-FINAL-2TEAM


## 1️⃣ 팀 소개
### 팀 명 : Ivle Malle
#### 🗓️ 개발 기간
> 2025.07.23 ~ 
### 👥 팀원

<table width="100%">
  <tr>
    <td align=center><b>구자현</b></td>
    <td align=center><b>김지민</b></td>
    <td align=center><b>민경재</b></td>
    <td align=center><b>박수빈</b></td>
    <td align=center><b>이유나</b></td>
    <td align=center><b>홍성의</b></td>
  </tr>
  <tr>
    <td align="center" width="16%">
      <b><img src="https://github.com/user-attachments/assets/a2e78d57-db3e-4204-9d02-fff1ab699124"/></b>
    </td>
    <td align="center" width="16%">
      <b><img src="https://github.com/user-attachments/assets/2624f7cc-db21-436d-bccd-52cede65a3b0"/></b>
    </td>
    <td align="center" width="16%">
      <b><img src="https://github.com/user-attachments/assets/2e42b141-fff2-4d56-8c44-7b00756fd814"/></b>
    </td>
    <td align="center" width="16%">
      <b><img src="https://github.com/user-attachments/assets/cc1f39e6-3496-433e-a24b-5322a69ad41d"/></b>
    </td>
    <td align="center" width="16%">
      <b><img src="https://github.com/user-attachments/assets/c69f9919-6ed2-4036-b24f-bdcca4121e7d"/></b>
    </td>
    <td align="center" width="16%">
      <b><img src="https://github.com/user-attachments/assets/fd9a233e-ae7e-4d89-90b6-49ba7d690bd5"/></b>
    </td>
  </tr>
  <tr>
    <td align="center" width="16%">
      <a href="https://github.com/Koojh99">
        <img src="https://img.shields.io/badge/GitHub-Koojh99-C7CDE5?logo=github" alt="구자현 GitHub"/>
      </a>
    </td>
    <td align="center" width="16%">
      <a href="https://github.com/Gogimin">
        <img src="https://img.shields.io/badge/GitHub-Gogimin-FAC8D1?logo=github" alt="김지민 GitHub"/>
      </a>
    </td>
    <td align="center" width="16%">
      <a href="https://github.com/rudwo524">
        <img src="https://img.shields.io/badge/GitHub-rudwo524-FECC99?logo=github" alt="민경재 GitHub"/>
      </a>
    </td>
    <td align="center" width="16%">
      <a href="https://github.com/subin0821">
        <img src="https://img.shields.io/badge/GitHub-subin0821-FFF2A3?logo=github" alt="박수빈 GitHub"/>
      </a>
    </td>
    <td align="center" width="16%">
      <a href="https://github.com/yunawawa">
        <img src="https://img.shields.io/badge/GitHub-yunawawa-EFE1F8?logo=github" alt="이유나 GitHub"/>
      </a>
    </td>
    <td align="center" width="16%">
      <a href="https://github.com/seonguihong">
        <img src="https://img.shields.io/badge/GitHub-seonguihong-BAD7E7?logo=github" alt="홍성의 GitHub"/>
      </a>
    </td>
  </tr>
  <tr>
    <td align="center">역할</td>
    <td align="center">역할</td>
    <td align="center">역할</td>
    <td align="center">역할</td>
    <td align="center">역할</td>
    <td align="center">역할</td>

  </tr>
</table>



## 🚀 현재 상황 개요 (추후 업데이트 예정)

이 프로젝트는 의류 전문 이커머스 플랫폼의 백엔드 역할을 하도록 설계된 FastAPI 애플리케이션입니다. 사용자 인증, 상품 조회, 데이터 캐싱을 처리하고 챗봇 인터페이스를 제공합니다. 상품 데이터는 AWS S3 버킷에서 동적으로 로드되며, 사용자 데이터는 PostgreSQL 데이터베이스에 저장됩니다.

## 📁 프로젝트 구조 (추후 업데이트 예정)

```
FAST_API/
├── crud/                 # 데이터베이스 CRUD(생성, 읽기, 업데이트, 삭제) 작업을 포함합니다.
├── models/               # SQLAlchemy 데이터베이스 모델을 포함합니다.
├── routers/              # API 엔드포인트 정의(라우트)를 포함합니다.
├── schemas/              # Pydantic 데이터 유효성 검사 스키마를 포함합니다.
├── static/               # 정적 파일(CSS, JavaScript, 이미지)을 포함합니다.
├── templates/            # Jinja2 HTML 템플릿을 포함합니다.
├── cache/                # 파일 기반 캐시를 저장하기 위한 디렉토리입니다.
├── .env                  # (존재하지 않음) 환경 변수 파일 (생성 필요).
├── main.py               # 메인 애플리케이션 진입점입니다.
├── db.py                 # PostgreSQL 데이터베이스 설정 및 세션 관리.
├── s3_data_loader.py     # AWS S3에서 데이터를 로드하고 처리하는 로직.
├── cache_manager.py      # 성능 최적화를 위한 캐싱 로직.
├── data_store.py         # 상품 정보를 위한 인메모리 데이터 저장소.
├── security.py           # 비밀번호 처리 및 검증 로직.
├── dependencies.py       # 인증 및 권한 부여를 위한 FastAPI 종속성.
├── requirements.txt      # Python 패키지 종속성.
└── ...
```

---

## 🚀 현재 상황 개요 (추후 업데이트 예정)

이 프로젝트는 의류 전문 이커머스 플랫폼의 백엔드 역할을 하도록 설계된 FastAPI 애플리케이션입니다. 사용자 인증, 상품 조회, 데이터 캐싱을 처리하고 챗봇 인터페이스를 제공합니다. 상품 데이터는 AWS S3 버킷에서 동적으로 로드되며, 사용자 데이터는 PostgreSQL 데이터베이스에 저장됩니다.

## 📁 프로젝트 구조 (추후 업데이트 예정)

```
FAST_API/
├── crud/                 # 데이터베이스 CRUD(생성, 읽기, 업데이트, 삭제) 작업을 포함합니다.
├── models/               # SQLAlchemy 데이터베이스 모델을 포함합니다.
├── routers/              # API 엔드포인트 정의(라우트)를 포함합니다.
├── schemas/              # Pydantic 데이터 유효성 검사 스키마를 포함합니다.
├── static/               # 정적 파일(CSS, JavaScript, 이미지)을 포함합니다.
├── templates/            # Jinja2 HTML 템플릿을 포함합니다.
├── cache/                # 파일 기반 캐시를 저장하기 위한 디렉토리입니다.
├── .env                  # (존재하지 않음) 환경 변수 파일 (생성 필요).
├── main.py               # 메인 애플리케이션 진입점입니다.
├── db.py                 # PostgreSQL 데이터베이스 설정 및 세션 관리.
├── s3_data_loader.py     # AWS S3에서 데이터를 로드하고 처리하는 로직.
├── cache_manager.py      # 성능 최적화를 위한 캐싱 로직.
├── data_store.py         # 상품 정보를 위한 인메모리 데이터 저장소.
├── security.py           # 비밀번호 처리 및 검증 로직.
├── dependencies.py       # 인증 및 권한 부여를 위한 FastAPI 종속성.
├── requirements.txt      # Python 패키지 종속성.
└── ...
```

---

## 🖥️ 시스템 아키텍쳐 (추후 업데이티 예정)

여기에 아키텍쳐쳐 사진 넣을거에요

## Data Flow Diagram

### Lvl 0

<img width="2032" height="596" alt="image" src="https://github.com/user-attachments/assets/57bfda62-e2e0-4a1b-b9a8-b157c923f664" />

### Lvl 1

<img width="576" height="714" alt="image" src="https://github.com/user-attachments/assets/cf4dfade-f53e-4a4a-a099-4575341d82e6" />
<img width="1002" height="390" alt="image" src="https://github.com/user-attachments/assets/0b8430a0-4130-4b68-a0e4-17d68a06c42e" />

## User Flow Chart

<img width="1642" height="1084" alt="image" src="https://github.com/user-attachments/assets/dfe5e6a7-130c-4cd0-aa14-c62ab1ba9f97" />



## 📄 파일 설명

### 핵심 애플리케이션 파일

*   **`main.py`**: FastAPI 애플리케이션의 메인 진입점입니다. 앱을 초기화하고, 미들웨어(세션 등)를 설정하며, 정적 디렉토리를 마운트하고, 모든 API 라우터를 포함하며, 데이터베이스 초기화 및 S3 데이터 로딩과 같은 애플리케이션 시작 이벤트를 처리합니다.

*   **`db.py`**: SQLAlchemy를 사용하여 PostgreSQL 데이터베이스 연결을 관리합니다. 환경 변수에서 연결 세부 정보를 읽고, 데이터베이스 엔진을 생성하며, API 라우트에서 사용할 `get_db` 세션 종속성을 제공합니다. 또한 데이터베이스 테이블을 초기화하는 함수(`init_db`)와 기본 관리자 사용자를 생성하는 함수(`bootstrap_admin`)를 포함합니다.

*   **`s3_data_loader.py`**: AWS S3 버킷에서 데이터를 가져오는 역할을 합니다. `boto3`를 사용하여 S3에 연결하고, CSV 파일을 로드하며, 데이터(예: 이미지 URL 정리, 컬럼 매핑)를 처리하고, 성능 향상을 위해 결과를 캐시하도록 `cache_manager`와 통합됩니다.

*   **`cache_manager.py`**: S3의 상품 목록과 같이 자주 액세스하는 데이터를 저장하기 위해 이중 계층 캐싱 시스템(인메모리 및 파일 기반)을 구현합니다. 이를 통해 반복적이고 느린 데이터 로딩 작업의 필요성을 줄입니다.

*   **`data_store.py`**: 간단하고 중앙화된 인메모리 저장소입니다. `s3_data_loader.py`에 의해 로드된 의류 상품 데이터를 전역 리스트(`clothing_data`)에 보관하여 애플리케이션 전체에서 쉽게 액세스할 수 있도록 합니다.

*   **`security.py`**: 비밀번호 검증을 처리합니다. **참고:** 현재 구현은 해싱을 사용하지 않고 비밀번호를 일반 텍스트로 비교합니다. 이는 단순화된 접근 방식으로, 프로덕션 환경에서는 안전한 해싱 라이브러리(예: `passlib`)로 교체해야 합니다.

*   **`dependencies.py`**: 라우트를 보호하기 위한 재사용 가능한 FastAPI 종속성을 정의합니다.
    *   `login_required`: 특정 엔드포인트에 액세스하기 전에 사용자가 로그인했는지 확인합니다.
    *   `admin_required`: 로그인한 사용자가 'admin' 역할을 가지고 있는지 확인하는 더 엄격한 종속성입니다.

*   **`database.py`**: `pandas`를 사용하여 로컬 `products.csv` 파일에서 상품 데이터를 읽는 레거시 또는 대체 데이터 로딩 메커니즘으로 보입니다. 애플리케이션 시작 로직에서 사용되는 기본 데이터 소스는 아닙니다.

*   **`requirements.txt`**: 프로젝트 실행에 필요한 모든 Python 라이브러리 및 패키지를 나열합니다. `pip install -r requirements.txt`를 사용하여 설치할 수 있습니다.

### 주요 디렉토리

*   **`routers/`**: 관련된 엔드포인트를 그룹화하는 여러 API "라우터"를 포함합니다. 예를 들어, `router_auth.py`는 로그인/로그아웃을 처리하고, `router_products.py`는 상품 목록 및 필터링을 처리합니다. 이를 통해 API를 체계적이고 모듈식으로 유지합니다.

*   **`models/`**: SQLAlchemy 모델을 포함합니다. 이 디렉토리의 각 파일은 PostgreSQL 데이터베이스의 테이블에 매핑되는 Python 클래스(예: `users` 테이블을 위한 `User` 모델)를 정의할 가능성이 높습니다.

*   **`crud/`**: 데이터베이스 작업(생성, 읽기, 업데이트, 삭제)을 수행하는 함수를 보관합니다. 이는 일반적인 디자인 패턴에 따라 라우터의 API 엔드포인트 로직에서 원시 데이터베이스 로직을 분리합니다.

*   **`schemas/`**: 들어오는 요청 데이터를 검증하고 나가는 응답 데이터의 형식을 지정하는 데 사용되는 Pydantic 모델(스키마)을 포함합니다. 이를 통해 API를 오가는 데이터가 일관되고 예상된 구조를 갖도록 보장합니다.

*   **`templates/`**: 애플리케이션의 프론트엔드 페이지를 렌더링하는 데 사용되는 Jinja2 HTML 템플릿을 포함합니다.

*   **`static/`**: 클라이언트의 브라우저에 직접 제공되는 CSS 스타일시트, JavaScript 파일, 이미지와 같은 모든 정적 자산을 저장합니다.

*   **`cache/`**: `cache_manager`가 파일 기반 캐시 객체를 저장하는 기본 디렉토리입니다. 이 디렉토리는 일반적으로 `.gitignore`에 추가해야 합니다.

---

## ⚙️ 설정 및 애플리케이션 실행

1.  **`.env` 파일 생성**: `.env.example`이 있는 경우 복사하거나 새 `.env` 파일을 만들고 다음을 포함한 필수 환경 변수를 채웁니다:
    *   데이터베이스 자격 증명 (`DB_USER`, `DB_PASSWORD` 등)
    *   AWS 자격 증명 (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
    *   S3 버킷 세부 정보 (`S3_BUCKET_NAME`, `S3_FILE_KEY`)
    *   세션 시크릿 키 (`SESSION_SECRET`)

2.  **종속성 설치**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **애플리케이션 실행**:
    ```bash
    uvicorn main:app --reload
    ```
    애플리케이션은 `http://127.0.0.1:8000`에서 사용할 수 있습니다.


## 이미지 부분 (자현이형이 적고있는것)


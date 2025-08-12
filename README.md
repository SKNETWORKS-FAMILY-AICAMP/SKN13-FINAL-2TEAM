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

## 🖥️ System Architecture

<img width="2573" height="1178" alt="System_Architecture" src="https://github.com/user-attachments/assets/ef430ee3-966f-4ba9-9f0f-56bf992c95c2" />

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

---
## 👗 이미지 기반 패션 추천 모델 (YOLOv8 + FashionCLIP + GPT4o + FAISS)
본 모듈은 **AI 의류 쇼핑 어시스턴트 플랫폼**의 핵심 기능 중 하나로, 사용자가 업로드한 의류 이미지를 분석하여 제품을 추천하는 **이미지 기반 패션 검색/추천 시스템**입니다.

---

## 📌 개요
- **목표**: 대규모 의류 이미지 데이터(5~10만 장)에서 객체를 정확히 탐지하고, 멀티모달 검색을 통해 유사한 제품을 실시간으로 추천
- **주요 기능**
  1. YOLOv8을 이용한 의류 객체 탐지 및 크롭
  2. GPT-4o를 통한 패션 아이템 설명 캡션 생성
  3. FashionCLIP으로 이미지·텍스트 임베딩 생성
  4. FAISS 기반 벡터 검색으로 유사 아이템 추천
 
 ---
## 🛠 기술 스택 
| 기술 | 역할 |
|------|------|
| **YOLOv8l** | 객체 탐지 및 바운딩 박스 추출 |
| **FashionCLIP** | 이미지·텍스트 멀티모달 임베딩 |
| **GPT-4o** | 의류 아이템 캡션 생성 |
| **FAISS** | 임베딩 벡터 검색 및 최근접 이웃 탐색 |
| Python 3.9+, PyTorch 2.8 | 모델 학습 및 추론 환경 |
| Roboflow | 데이터 전처리 및 증강 |
---

## 🧠 모델 개요 
### 모델명
- **FashionCLIP**
- **YOLOv8-Large (yolov8l)**
```python
from ultralytics import YOLO
model = YOLO("yolov8l.pt")
```
### FashionCLIP
- CLIP(Contrastive Language-Image Pretraining)의 의류 특화 버전
- OpenAI의 CLIP 모델(4억 쌍의 이미지-텍스트 데이터 학습)을 기반으로, 패션 도메인에 맞춰 파인튜닝
- 이미지와 텍스트를 동일한 임베딩 공간에 매핑 → 검색·추천 가능

### YOLOv8-Large 모델 선정 이유
본 프로젝트는 5~10만 장 규모의 의류 이미지를 대상으로, **정확도**, **속도**, **안정성**의 균형을 중요시했습니다. 다양한 객체 탐지 모델과 비교 평가한 결과, YOLOv8l이 다음과 같은 이유로 최종 선정되었습니다.

| 모델 | mAP@0.5-0.95(%) | 추론 속도(FPS) | 장점 | 단점 |
|------|----------------|----------------|------|------|
| YOLOv8l | 53.2 | 85 | 높은 정확도와 속도, Anchor-free 구조, 다양한 객체 크기 대응 | 모델 크기가 s/m보다 큼 |
| YOLOv11l | 54.5 | 82 | 최신 아키텍처, 일부 mAP 개선 | 초기 버전, 안정성 검증 부족 |
| EfficientDet-D3 | 48.1 | 40 | 파라미터 효율성 우수 | 속도 느림, 소형 객체 약함 |
| Faster R-CNN | 42.5 | 15 | 높은 정밀도, 안정성 | 속도 매우 느림 |

**선정 이유 요약**
1. **정확도-속도 균형**: mAP는 YOLOv11l보다 약간 낮지만 FPS가 높아 대규모 데이터 처리에 유리
2. **안정성**: 산업·연구에서 검증된 사례 다수
3. **배포 용이성**: Ultralytics 생태계와 완벽 호환, TensorRT/ONNX 변환 검증 사례 존재
4. **제약 적음**: 타 모델 대비 호환성 및 처리 효율성 우수
---
## 🧹데이터 전처리
YOLOv8l 학습 전, **Roboflow**를 활용해 다음과 같은 전처리를 수행했습니다.

| 단계 | 목적 | 수행 작업 | 사용 도구 |
|------|------|----------|-----------|
| 결측치 처리 | 누락값 제거 | 라벨 파일이 없거나 바운딩 박스 0개인 이미지 제거 | Roboflow |
| 라벨 검증 | 데이터 품질 확보 | 라벨 값이 클래스 목록에 포함되는지 검증 | Roboflow |
| 이미지 표준화 | 모델 학습 품질 향상 | Auto-Orient, Resize(imgsz=640), Adaptive Equalization | Roboflow |
| 데이터 증강 | 일반화 성능 강화 | Horizontal/Vertical Flip, Rotation(-10°~+10°) | Roboflow |
| 데이터 분리 | 학습/검증/테스트 분할 | 초기학습: train 4177, valid 400, test 200 / 추가 학습: train 1545, valid 150, test 77 | Roboflow |

## 📂 YOLOv8-Large 모델 이미지 학습용 데이터셋
- **출처**: 자체 크롤링 (29CM, 무신사, W Concept, 지그재그 등)
- **구성**: 5개 클래스 ("dress","pants","skirt&pants","skirt","top")
- **정보**
  
| 항목명 | 설명 | 예시 | 필요성 |
|--------|------|------|--------|
| image_id | 이미지 파일명 | image_001.jpg | YOLO 결과와 원본 이미지 매칭 |
| image_path | 이미지 경로 | dataset/train/images/image_001.jpg | CLIP 입력 경로 |
| width | 이미지 가로 크기(px) | 640 | 좌표 변환에 필요 |
| height | 이미지 세로 크기(px) | 640 | 좌표 변환에 필요 |
| class_id | 객체 클래스 ID | 1 | 카테고리 필터링 |
| class_name | 객체 클래스명 | pants | 텍스트 쿼리와 비교 |
| bbox_x_center | 바운딩 박스 중심 X좌표 | 0.515625 | 크롭 시 활용 |
| bbox_y_center | 바운딩 박스 중심 Y좌표 | 0.53828125 | 크롭 시 활용 |
| bbox_width | 바운딩 박스 너비 | 0.3453125 | 크롭 시 활용 |
| bbox_height | 바운딩 박스 높이 | 0.7609375 | 크롭 시 활용 |

---
## 📊학습 결과 
### 1차 학습 (best.pt)
- **Epoch**: 103
- **mAP@0.5**: 0.974
- **mAP@0.5:0.95**: 0.837
- **Precision**: 0.918
- **Recall**: 0.960

### 추가 학습 (best_ft.pt)
- **Epoch**: 28 (조기 종료)
- **mAP@0.5**: 0.905 (-6.9%)
- **mAP@0.5:0.95**: 0.766 (-7.1%)
- **Precision**: 0.825
- **Recall**: 0.891

### testcase
<img width="272" height="490" alt="image" src="https://github.com/user-attachments/assets/7965d336-ffd6-4f9c-8d9b-a528f26ccb87" />
<img width="418" height="525" alt="image" src="https://github.com/user-attachments/assets/d207cac7-f3ca-4358-83c4-26e96a3f1340" />

**분석:**
- 추가 학습 데이터의 클래스 불균형 및 소규모로 인한 성능 저하
- Fine-tuning 과정에서 일반화 성능 일부 손상
- 향후 클래스별 최소 2,000장 확보 필요
---
## 🔄시스템 아키텍처(모델 파이프라인)

<img width="708" height="237" alt="image" src="https://github.com/user-attachments/assets/9bbcb6c2-aabd-43f2-adbc-ec431455e6d2" />

사용자가 이미지를 업로드하면, 본 시스템은 다음 단계를 거쳐 유사 의류를 추천합니다.
1. **YOLOv8 객체 탐지**  
   업로드된 이미지에서 의류 객체를 탐지하고, 해당 영역을 바운딩 박스로 표시합니다.
2. **바운딩 박스 크롭**  
   탐지된 영역을 잘라내어 후속 분석에 활용합니다.
3. **GPT-4o 기반 캡션 생성**  
   크롭된 의류 이미지에 대해 자연어 설명(예: *"화이트 셔츠와 체크 패턴 스커트"*)을 생성합니다.
4. **FashionCLIP 임베딩 추출**  
   이미지와 텍스트를 동일한 벡터 공간에 매핑하여 임베딩을 생성합니다.
5. **FAISS 벡터 검색**  
   임베딩을 기반으로 대규모 의류 데이터셋에서 가장 유사한 아이템을 검색합니다.
6. **추천 결과 제공**  
   검색된 유사 의류 이미지를 사용자에게 추천합니다.

---
## 🚀향후계획
1. 클래스별 데이터 균형 확보
2. YOLO 모델로 의류 크롭 후 Fashion CLIP에 전달
3. GPT-4o로 캡션 생성 → Fashion CLIP 임베딩
4. 이미지 간 유사도 검색 성능 향상



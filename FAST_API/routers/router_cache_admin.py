from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from cache_manager import cache_manager
from s3_data_loader import s3_loader
import os

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/cache/info", response_class=JSONResponse)
async def get_cache_info():
    """캐시 정보 조회"""
    try:
        cache_info = cache_manager.get_cache_info()
        
        # S3 연결 정보 추가
        s3_info = {
            "bucket_name": os.getenv("S3_BUCKET_NAME", "N/A"),
            "aws_region": os.getenv("AWS_REGION", "N/A"),
            "data_source": os.getenv("DATA_SOURCE", "s3"),
            "products_file_key": os.getenv("S3_PRODUCTS_FILE_KEY", "products/products.csv")
        }
        
        return {
            "success": True,
            "cache_info": cache_info,
            "s3_info": s3_info,
            "message": "캐시 정보를 성공적으로 조회했습니다."
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "캐시 정보 조회 중 오류가 발생했습니다."
        }

@router.post("/cache/clear", response_class=JSONResponse)
async def clear_cache(cache_key: str = None):
    """캐시 삭제"""
    try:
        if cache_key:
            cache_manager.clear_cache(cache_key)
            message = f"캐시 '{cache_key}'를 삭제했습니다."
        else:
            cache_manager.clear_cache()
            message = "전체 캐시를 삭제했습니다."
        
        return {
            "success": True,
            "message": message
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "캐시 삭제 중 오류가 발생했습니다."
        }

@router.post("/cache/cleanup", response_class=JSONResponse)
async def cleanup_expired_cache():
    """만료된 캐시 정리"""
    try:
        cache_manager.cleanup_expired_cache()
        cache_info = cache_manager.get_cache_info()
        
        return {
            "success": True,
            "cache_info": cache_info,
            "message": "만료된 캐시를 정리했습니다."
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "캐시 정리 중 오류가 발생했습니다."
        }

@router.post("/cache/refresh-data", response_class=JSONResponse)
async def refresh_s3_data():
    """S3 데이터 강제 새로고침"""
    try:
        # 기존 캐시 삭제
        cache_manager.clear_cache()
        
        # S3에서 데이터 강제 로드
        file_key = os.getenv("S3_PRODUCTS_FILE_KEY", "products/products.csv")
        data = s3_loader.load_product_data(file_key, use_cache=False)
        
        if data:
            # 새 데이터를 캐시에 저장
            cache_identifier = f"s3_products_{s3_loader.bucket_name}_{file_key}"
            cache_manager.set(cache_identifier, data)
            
            return {
                "success": True,
                "data_count": len(data),
                "message": f"S3 데이터를 성공적으로 새로고침했습니다. ({len(data)}개 상품)"
            }
        else:
            return {
                "success": False,
                "message": "S3 데이터 로드에 실패했습니다."
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "S3 데이터 새로고침 중 오류가 발생했습니다."
        }

@router.get("/cache/test-s3", response_class=JSONResponse)
async def test_s3_connection():
    """S3 연결 테스트"""
    try:
        # S3 버킷 파일 목록 조회
        files = s3_loader.list_files_in_bucket(prefix="products/")
        
        if files:
            return {
                "success": True,
                "connection_status": "연결 성공",
                "files_found": len(files),
                "sample_files": files[:5],  # 첫 5개 파일만 표시
                "message": "S3 연결이 정상적으로 작동합니다."
            }
        else:
            return {
                "success": False,
                "connection_status": "파일 없음",
                "message": "S3 연결은 되지만 파일을 찾을 수 없습니다."
            }
    except Exception as e:
        return {
            "success": False,
            "connection_status": "연결 실패",
            "error": str(e),
            "message": "S3 연결 테스트에 실패했습니다."
        }

@router.get("/cache/health", response_class=JSONResponse)
async def cache_health_check():
    """캐시 시스템 상태 확인"""
    try:
        cache_info = cache_manager.get_cache_info()
        
        # 데이터 소스별 상태 확인
        data_source = os.getenv("DATA_SOURCE", "s3").lower()
        
        status = {
            "cache_system": "정상",
            "data_source": data_source,
            "cache_info": cache_info,
            "timestamp": cache_manager.memory_cache
        }
        
        # S3 상태 확인 (data_source가 s3인 경우)
        if data_source == "s3":
            try:
                files = s3_loader.list_files_in_bucket(prefix="products/")
                status["s3_status"] = "연결됨"
                status["s3_files_count"] = len(files)
            except:
                status["s3_status"] = "연결 실패"
                status["s3_files_count"] = 0
        
        return {
            "success": True,
            "status": status,
            "message": "시스템이 정상적으로 작동 중입니다."
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "상태 확인 중 오류가 발생했습니다."
        }
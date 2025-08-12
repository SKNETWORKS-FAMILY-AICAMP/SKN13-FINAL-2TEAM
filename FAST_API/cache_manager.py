import os
import time
import json
import pickle
import hashlib
from typing import List, Dict, Optional
from pathlib import Path

class CacheManager:
    """데이터 캐싱 관리 클래스"""
    
    def __init__(self, cache_dir: str = "cache", cache_ttl: int = 3600):
        """
        Args:
            cache_dir: 캐시 디렉토리 경로
            cache_ttl: 캐시 유효 시간 (초, 기본값: 1시간)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_ttl = cache_ttl
        self.memory_cache = {}
        
        # 캐시 디렉토리 생성
        self.cache_dir.mkdir(exist_ok=True)
        print(f"📂 캐시 디렉토리 초기화: {self.cache_dir.absolute()}")
    
    def _get_cache_key(self, identifier: str) -> str:
        """캐시 키 생성"""
        return hashlib.md5(identifier.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """캐시 파일 경로 생성"""
        return self.cache_dir / f"{cache_key}.pkl"
    
    def _is_cache_valid(self, cache_path: Path) -> bool:
        """캐시 파일이 유효한지 확인"""
        if not cache_path.exists():
            return False
        
        # 파일 수정 시간 확인
        file_age = time.time() - cache_path.stat().st_mtime
        return file_age < self.cache_ttl
    
    def get_from_memory(self, identifier: str) -> Optional[List[Dict]]:
        """메모리 캐시에서 데이터 조회"""
        cache_key = self._get_cache_key(identifier)
        
        if cache_key in self.memory_cache:
            data, timestamp = self.memory_cache[cache_key]
            
            # 캐시 유효성 확인
            if time.time() - timestamp < self.cache_ttl:
                print(f"🚀 메모리 캐시 히트: {identifier}")
                return data
            else:
                # 만료된 캐시 삭제
                del self.memory_cache[cache_key]
                print(f"🗑️ 만료된 메모리 캐시 삭제: {identifier}")
        
        return None
    
    def set_to_memory(self, identifier: str, data: List[Dict]) -> None:
        """메모리 캐시에 데이터 저장"""
        cache_key = self._get_cache_key(identifier)
        self.memory_cache[cache_key] = (data, time.time())
        print(f"💾 메모리 캐시 저장: {identifier} ({len(data)}개 항목)")
    
    def get_from_file(self, identifier: str) -> Optional[List[Dict]]:
        """파일 캐시에서 데이터 조회"""
        cache_key = self._get_cache_key(identifier)
        cache_path = self._get_cache_path(cache_key)
        
        if self._is_cache_valid(cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    data = pickle.load(f)
                print(f"📁 파일 캐시 히트: {identifier}")
                
                # 메모리 캐시에도 저장
                self.set_to_memory(identifier, data)
                return data
            except Exception as e:
                print(f"❌ 파일 캐시 읽기 실패: {e}")
                # 손상된 캐시 파일 삭제
                cache_path.unlink(missing_ok=True)
        
        return None
    
    def set_to_file(self, identifier: str, data: List[Dict]) -> None:
        """파일 캐시에 데이터 저장"""
        cache_key = self._get_cache_key(identifier)
        cache_path = self._get_cache_path(cache_key)
        
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)
            print(f"💿 파일 캐시 저장: {identifier} ({len(data)}개 항목)")
        except Exception as e:
            print(f"❌ 파일 캐시 저장 실패: {e}")
    
    def get(self, identifier: str) -> Optional[List[Dict]]:
        """캐시에서 데이터 조회 (메모리 → 파일 순서)"""
        # 1. 메모리 캐시 확인
        data = self.get_from_memory(identifier)
        if data is not None:
            return data
        
        # 2. 파일 캐시 확인
        data = self.get_from_file(identifier)
        if data is not None:
            return data
        
        print(f"🔍 캐시 미스: {identifier}")
        return None
    
    def set(self, identifier: str, data: List[Dict]) -> None:
        """캐시에 데이터 저장 (메모리 + 파일)"""
        self.set_to_memory(identifier, data)
        self.set_to_file(identifier, data)
    
    def clear_cache(self, identifier: Optional[str] = None) -> None:
        """캐시 삭제"""
        if identifier:
            # 특정 캐시 삭제
            cache_key = self._get_cache_key(identifier)
            
            # 메모리 캐시 삭제
            if cache_key in self.memory_cache:
                del self.memory_cache[cache_key]
            
            # 파일 캐시 삭제
            cache_path = self._get_cache_path(cache_key)
            cache_path.unlink(missing_ok=True)
            
            print(f"🗑️ 캐시 삭제: {identifier}")
        else:
            # 전체 캐시 삭제
            self.memory_cache.clear()
            
            for cache_file in self.cache_dir.glob("*.pkl"):
                cache_file.unlink()
            
            print("🗑️ 전체 캐시 삭제")
    
    def get_cache_info(self) -> Dict:
        """캐시 정보 조회"""
        file_cache_count = len(list(self.cache_dir.glob("*.pkl")))
        memory_cache_count = len(self.memory_cache)
        
        # 캐시 크기 계산
        total_size = 0
        for cache_file in self.cache_dir.glob("*.pkl"):
            total_size += cache_file.stat().st_size
        
        return {
            "memory_cache_count": memory_cache_count,
            "file_cache_count": file_cache_count,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "cache_ttl_hours": self.cache_ttl / 3600,
            "cache_dir": str(self.cache_dir.absolute())
        }
    
    def cleanup_expired_cache(self) -> None:
        """만료된 캐시 정리"""
        cleaned_count = 0
        
        # 파일 캐시 정리
        for cache_file in self.cache_dir.glob("*.pkl"):
            if not self._is_cache_valid(cache_file):
                cache_file.unlink()
                cleaned_count += 1
        
        # 메모리 캐시 정리
        expired_keys = []
        current_time = time.time()
        
        for cache_key, (data, timestamp) in self.memory_cache.items():
            if current_time - timestamp >= self.cache_ttl:
                expired_keys.append(cache_key)
        
        for key in expired_keys:
            del self.memory_cache[key]
            cleaned_count += 1
        
        if cleaned_count > 0:
            print(f"🧹 만료된 캐시 정리 완료: {cleaned_count}개")

# 전역 캐시 매니저 인스턴스
cache_manager = CacheManager(
    cache_dir=os.getenv("CACHE_DIR", "cache"),
    cache_ttl=int(os.getenv("CACHE_TTL", "3600"))  # 기본 1시간
)

"""
FollowUp Agent (간소화 버전)
이전 Q/A 데이터를 기반으로 후속 질문을 처리하는 에이전트
"""
import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

@dataclass
class FollowUpAgentResult:
    """FollowUp Agent 결과"""
    success: bool
    message: str
    products: List[Dict]
    metadata: Dict

class FollowUpAgent:
    """후속 질문 처리 에이전트"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"
    
    def is_follow_up_question(self, user_input: str, db=None, user_id: int = None) -> bool:
        """후속 질문인지 판단"""
        print(f"=== FollowUp Agent - 후속 질문 체크 ===")
        print(f"입력: {user_input}")
        
        # 후속 질문 키워드들
        follow_up_keywords = [
            "저거", "그거", "위에", "중에", "가장", "제일", "첫번째", "두번째", "세번째", "마지막",
            "싸", "비싸", "저렴", "비용", "가격", "얼마", "사이즈", "색깔", "어떤", "좋을까",
            "추천", "선택", "고르", "더", "다른", "또", "어느", "몇번째"
        ]
        
        user_lower = user_input.lower()
        matched_keywords = [kw for kw in follow_up_keywords if kw in user_lower]
        
        if len(matched_keywords) == 0:
            print("후속 질문 키워드가 없음")
            return False
        
        # 키워드가 있으면 최근 추천 확인 (선택사항)
        if db and user_id:
            has_recent_recs = self._check_recent_recommendations(db, user_id)
            print(f"매칭된 키워드: {matched_keywords}")
            print(f"최근 추천 있음: {has_recent_recs}")
            return has_recent_recs
        else:
            # db/user_id가 없으면 키워드만으로 판단
            print(f"매칭된 키워드: {matched_keywords}")
            print("후속 질문 판정: True (키워드 기반)")
            return True
    
    def process_follow_up_question(self, user_input: str, db, user_id: int, session_id: str = None) -> FollowUpAgentResult:
        """
        후속 질문 처리 (간소화 버전)
        
        Args:
            user_input: 사용자 입력
            db: 데이터베이스 세션
            user_id: 사용자 ID
            session_id: 현재 세션 ID (선택사항)
        
        Returns:
            FollowUpAgentResult: 후속 질문 처리 결과
        """
        print(f"=== FollowUp Agent 시작 (간소화) ===")
        print(f"질문: {user_input}, 세션: {session_id}, 사용자: {user_id}")
        
        try:
            print(f"🔍 팔로우업 프로세스 시작")
            print(f"🔍 매개변수: session_id={session_id}, user_id={user_id}")
            
            # 특정 세션의 최근 Q/A 데이터 불러오기
            print(f"🔍 Q/A 데이터 로드 시도...")
            recent_qa_data = self._get_recent_qa_data(db, user_id, session_id)
            
            print(f"🔍 Q/A 데이터 로드 결과: {len(recent_qa_data)}개")
            
            if not recent_qa_data:
                error_msg = f"❌ 세션 {session_id}에서 최근 대화 내용을 찾을 수 없습니다." if session_id else "❌ 최근 대화 내용을 찾을 수 없습니다."
                error_msg += " 먼저 상품을 추천받은 후 후속 질문을 해주세요."
                
                print(f"🔍 Q/A 데이터 없음 - 오류 반환")
                
                return FollowUpAgentResult(
                    success=False,
                    message=error_msg,
                    products=[],
                    metadata={"error": "no_recent_qa", "agent_type": "followup", "session_id": session_id}
                )
            
            # LLM을 사용해 후속 질문 처리
            print(f"🔍 LLM 답변 생성 시작...")
            answer = self._generate_followup_answer_with_llm(user_input, recent_qa_data)
            
            print(f"🔍 LLM 답변 생성 완료: {answer[:50]}...")
            
            result = FollowUpAgentResult(
                success=True,
                message=answer,
                products=[],  # 새로운 상품 추천은 없음
                metadata={"follow_up": True, "agent_type": "followup", "qa_count": len(recent_qa_data)}
            )
            
            print(f"🔍 팔로우업 결과 반환: success={result.success}")
            return result
            
        except Exception as e:
            print(f"FollowUp Agent 오류: {e}")
            import traceback
            traceback.print_exc()
            
            return FollowUpAgentResult(
                success=False,
                message="후속 질문을 처리하는 중 오류가 발생했습니다. 다시 시도해주세요.",
                products=[],
                metadata={"error": str(e), "agent_type": "followup"}
            )
    
    def _get_recent_qa_data(self, db, user_id: int, session_id: str = None) -> List[Dict]:
        """특정 세션의 최근 Q/A 데이터 불러오기"""
        try:
            print(f"📥 Q/A 데이터 로드 시작 - 세션ID: {session_id}, 사용자ID: {user_id}")
            
            # DB 연결 상태 확인
            if db is None:
                print(f"❌ DB 연결이 None입니다!")
                return []
            else:
                print(f"📥 DB 연결 확인됨: {type(db)}")
            
            if session_id:
                print(f"📥 특정 세션 {session_id}의 메시지 조회 중...")
                # 특정 세션의 메시지들 가져오기
                from crud.chat_crud import get_session_messages
                
                print(f"📥 get_session_messages 함수 호출...")
                messages_data = get_session_messages(db, session_id, user_id)
                print(f"📥 ✅ 세션 {session_id}에서 {len(messages_data)}개 메시지 로드 성공")
                
                # 메시지 상세 출력 (디버깅)
                print(f"📥 메시지 상세 정보:")
                for i, msg in enumerate(messages_data):  # 모든 메시지
                    msg_type = msg.get('type', 'unknown')
                    msg_text = msg.get('text', '')
                    msg_id = msg.get('id', 'unknown')
                    created_at = msg.get('created_at', 'unknown')
                    print(f"  📥 메시지 {i+1}: ID={msg_id}, TYPE={msg_type}, TEXT={msg_text[:30]}..., TIME={created_at}")
            else:
                # 전체 사용자 히스토리에서 가져오기 (fallback)
                from crud.chat_crud import get_user_chat_history
                recent_messages = get_user_chat_history(db, user_id, limit=10)
                messages_data = [
                    {
                        "id": msg.id,
                        "type": msg.message_type,
                        "text": msg.text,
                        "created_at": msg.created_at.isoformat() if msg.created_at else None
                    }
                    for msg in recent_messages
                ]
                print(f"전체 히스토리에서 {len(messages_data)}개 메시지 로드")
            
            qa_pairs = []
            user_msg = None
            
            # 메시지들을 시간순으로 정렬 (오래된 것부터)
            messages_data.sort(key=lambda x: x.get('created_at', ''), reverse=False)
            
            # 연속된 유저-봇 메시지를 Q/A 쌍으로 구성
            print(f"Q/A 쌍 구성 시작...")
            for i, msg_data in enumerate(messages_data):
                msg_type = msg_data.get('type')
                msg_text = msg_data.get('text', '')
                
                print(f"  처리 중 메시지 {i+1}: {msg_type} - {msg_text[:30]}...")
                
                if msg_type == "user":
                    user_msg = msg_text
                    print(f"    → 사용자 메시지 저장: {user_msg[:30]}...")
                elif msg_type == "bot" and user_msg:
                    qa_pairs.append({
                        "question": user_msg,
                        "answer": msg_text,
                        "created_at": msg_data.get('created_at')
                    })
                    print(f"    ✅ Q/A 쌍 생성 - Q: {user_msg[:30]}... A: {msg_text[:30]}...")
                    user_msg = None  # 사용된 유저 메시지 초기화
            
            # 최근 3개 Q/A만 사용 (뒤에서부터)
            recent_qa = qa_pairs[-3:] if len(qa_pairs) >= 3 else qa_pairs
            
            print(f"최종 Q/A 데이터 {len(recent_qa)}개 로드 완료")
            return recent_qa
            
        except Exception as e:
            print(f"Q/A 데이터 로드 오류: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _generate_followup_answer_with_llm(self, user_input: str, recent_qa_data: List[Dict]) -> str:
        """LLM을 사용해 후속 질문에 대한 답변 생성"""
        
        # 최근 Q/A 데이터를 텍스트로 구성
        qa_context = ""
        for i, qa in enumerate(recent_qa_data, 1):
            qa_context += f"Q{i}: {qa['question']}\n"
            qa_context += f"A{i}: {qa['answer'][:300]}...\n\n"  # 답변은 300자로 제한
        
        system_prompt = """당신은 의류 추천 챗봇의 후속 질문 전문가입니다.
사용자가 이전 대화 내용에 대해 후속 질문을 했습니다.

역할:
1. 이전 Q/A 내용을 기반으로 사용자의 후속 질문에 답변
2. 가격, 브랜드, 스타일 등을 비교/분석하여 도움되는 정보 제공
3. 구체적이고 실용적인 조언 제공

답변 스타일:
- 친근하고 도움이 되는 톤
- 이전 대화 내용을 정확히 참조
- 비교나 분석이 필요하면 명확하게 제시
- 추가 질문이나 선택에 도움되는 정보 포함

최대 200자 내외로 간결하게 답변해주세요."""

        user_prompt = f"""최근 대화 내용:
{qa_context}

사용자 후속 질문: {user_input}

위 대화 내용을 바탕으로 사용자의 후속 질문에 답변해주세요."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )
            
            answer = response.choices[0].message.content.strip()
            print(f"LLM 후속 답변 생성 완료: {answer[:50]}...")
            return answer
            
        except Exception as e:
            print(f"LLM 답변 생성 오류: {e}")
            return "죄송합니다. 답변을 생성하는 중 오류가 발생했습니다. 다시 시도해주세요."


    
    def _check_recent_recommendations(self, db, user_id: int) -> bool:
        """최근 추천이 있는지 확인 (간소화 버전)"""
        try:
            recent_qa_data = self._get_recent_qa_data(db, user_id)
            return len(recent_qa_data) > 0
            
        except Exception as e:
            print(f"최근 추천 확인 오류: {e}")
            return False

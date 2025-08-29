document.addEventListener("DOMContentLoaded", () => {
    // 플로팅 위젯 요소들
    const floatingWidget = document.getElementById("floating-chatbot-widget");
    const toggleBtn = document.getElementById("chatbot-toggle-btn");
    const closeBtn = document.getElementById("widget-close-btn");
    const widgetMessages = document.getElementById("widget-messages");
    const widgetForm = document.getElementById("widget-form");
    const widgetInput = document.getElementById("widget-input");

    // 세션 관리 변수들 (저장용으로만 사용)
    let currentSessionId = localStorage.getItem('chatbot_session_id') || null;
    
    // UUID 마이그레이션 후 기존 정수 세션 ID 초기화
    if (currentSessionId && !isValidUUID(currentSessionId)) {
        console.log('기존 정수 세션 ID를 초기화합니다:', currentSessionId);
        localStorage.removeItem('chatbot_session_id');
        currentSessionId = null;
    }
    
    // 페이지 로드 시 세션 검증 (로그아웃 후 재로그인 시 새로운 세션 생성)
    function validateSession() {
        // 로그인 상태 확인 (간단한 방법)
        const isLoggedIn = document.cookie.includes('session=');
        if (!isLoggedIn && currentSessionId) {
            console.log('로그인 상태가 아니므로 챗봇 세션 초기화');
            localStorage.removeItem('chatbot_session_id');
            currentSessionId = null;
        }
    }
    
    // 페이지 로드 시 세션 검증 실행
    validateSession();

    // UUID 유효성 검사 함수
    function isValidUUID(uuid) {
        const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
        return uuidRegex.test(uuid);
    }

    // 플로팅 위젯 초기화
    if (floatingWidget && toggleBtn && closeBtn) {
        initializeFloatingWidget();
    }

    function initializeFloatingWidget() {
        // 토글 버튼 클릭 이벤트
        toggleBtn.addEventListener("click", () => {
            floatingWidget.classList.add("active");
            toggleBtn.classList.add("hidden");
            widgetInput.focus();
            
            // 세션이 있으면 이전 대화 내용 로드
            if (currentSessionId && isValidUUID(currentSessionId)) {
                loadPreviousMessages();
            }
        });

        // 닫기 버튼 클릭 이벤트
        closeBtn.addEventListener("click", () => {
            floatingWidget.classList.remove("active");
            toggleBtn.classList.remove("hidden");
        });

        // 위젯 폼 제출 이벤트
        widgetForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const message = widgetInput.value.trim();
            if (message) {
                addMessage(message, "user");
                widgetInput.value = "";
                showLoadingIndicator();
                
                sendMessageToAPI(message);
            }
        });

        // 초기 환영 메시지 (대화 기록이 없을 때만)
        setTimeout(() => {
            if (widgetMessages.children.length === 0) {
                addMessage("안녕하세요! 의류 추천 챗봇입니다. 어떤 스타일을 찾으시나요? 😊", "bot");
            }
        }, 500);
    }

    // 이전 대화 내용 로드
    async function loadPreviousMessages() {
        if (!currentSessionId || !isValidUUID(currentSessionId)) return;
        
        try {
            const response = await fetch(`/chat/session/${currentSessionId}/messages`, {
                headers: {
                    'Authorization': 'Bearer ' + localStorage.getItem('access_token')
                }
            });
            
            const data = await response.json();
            
            if (data.success && data.messages && data.messages.length > 0) {
                // 기존 메시지들 제거
                widgetMessages.innerHTML = '';
                
                // 이전 메시지들 추가
                data.messages.forEach(msg => {
                    addMessage(msg.text, msg.type);
                    
                    // 추천 결과가 있으면 상품 카드도 추가
                    if (msg.products && msg.products.length > 0) {
                        addRecommendations(msg.products);
                    }
                });
            }
        } catch (error) {
            console.error('이전 대화 내용 로드 오류:', error);
            // 오류 발생 시 세션 ID 초기화
            localStorage.removeItem('chatbot_session_id');
            currentSessionId = null;
        }
    }

    async function sendMessageToAPI(message) {
        // 날씨 관련 키워드 확인
        const weatherKeywords = ['날씨', '기온', '덥', '춥', '비와', '눈와'];
        const isWeatherQuery = weatherKeywords.some(keyword => message.includes(keyword));

        let latitude = null;
        let longitude = null;

        // 날씨 질문일 경우, 위치 정보 요청
        if (isWeatherQuery) {
            try {
                const position = await new Promise((resolve, reject) => {
                    if (!navigator.geolocation) {
                        reject(new Error('Geolocation is not supported by your browser.'));
                        return;
                    }
                    navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 });
                });
                latitude = position.coords.latitude;
                longitude = position.coords.longitude;
                console.log(`위치 정보 확보: ${latitude}, ${longitude}`);
            } catch (error) {
                console.error('위치 정보를 가져올 수 없습니다.', error);
                removeLoadingIndicator();
                addMessage('현재 위치를 가져올 수 없어요. 😥 브라우저의 위치 정보 접근을 허용했는지 확인해주세요!', 'bot');
                return; // 위치 정보 없으면 전송 중단
            }
        }

        // API로 메시지 전송
        try {
            const formData = new FormData();
            formData.append('user_input', message);
            if (currentSessionId && isValidUUID(currentSessionId)) {
                formData.append('session_id', currentSessionId);
            }
            if (latitude && longitude) {
                formData.append('latitude', String(latitude));
                formData.append('longitude', String(longitude));
            }

            console.log('메시지 전송:', message, '세션:', currentSessionId, '위치:', latitude, longitude);

            const response = await fetch('/chat/', {
                method: 'POST',
                body: formData,
                headers: {
                    'Authorization': 'Bearer ' + localStorage.getItem('access_token')
                }
            });

            const data = await response.json();
            removeLoadingIndicator();

            console.log('챗봇 응답:', data);

            if (data.message) {
                addMessage(data.message, "bot");
                
                if (data.products && data.products.length > 0) {
                    addRecommendations(data.products);
                }
                
                if (data.session_id && data.session_id !== currentSessionId) {
                    currentSessionId = data.session_id;
                    // UUID 유효성 검사 후 저장
                    if (isValidUUID(currentSessionId)) {
                        localStorage.setItem('chatbot_session_id', currentSessionId);
                    }
                }
            } else {
                addMessage("죄송합니다. 오류가 발생했습니다. 다시 시도해주세요.", "bot");
            }
        } catch (error) {
            console.error('Error:', error);
            removeLoadingIndicator();
            addMessage("네트워크 오류가 발생했습니다. 다시 시도해주세요.", "bot");
        }
    }

    function addMessage(message, sender) {
        const messageWrapper = document.createElement("div");
        messageWrapper.classList.add("widget-message", `widget-${sender}-message`);
        
        const messageContent = document.createElement("div");
        messageContent.classList.add("widget-message-content");
        
        // 마크다운 스타일 텍스트를 HTML로 변환
        let formattedMessage = message
            .replace(/\n/g, '<br>')  // 엔터를 <br>로 변환
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')  // **텍스트** → <strong>텍스트</strong>
            .replace(/^(\d+\.\s)/gm, '<strong>$1</strong>')  // 숫자. → 볼드
            .replace(/^(👕|👖)\s*\*\*(.*?)\*\*/gm, '$1 <strong>$2</strong>')  // 이모지 + 제목
            .replace(/^(\s+)(📍|💰|✨)\s*/gm, '$1$2 ')  // 아이콘 정렬
            .replace(/^(💡)\s*\*\*(.*?)\*\*/gm, '$1 <strong>$2</strong>');  // 팁 제목
        
        messageContent.innerHTML = formattedMessage;
        messageWrapper.appendChild(messageContent);
        
        widgetMessages.appendChild(messageWrapper);
        widgetMessages.scrollTop = widgetMessages.scrollHeight;
    }

    function addRecommendations(recommendations) {
        const recommendationsWrapper = document.createElement("div");
        recommendationsWrapper.classList.add("widget-message", "widget-bot-message");
        
        const recommendationsContent = document.createElement("div");
        recommendationsContent.classList.add("widget-message-content");
        
        let recommendationsHTML = '<div style="display: flex; flex-direction: column; gap: 6px;">';
        recommendations.forEach((product, index) => {
            const productName = product.상품명 || product.제품이름 || '상품명 없음';
            const brand = product.한글브랜드명 || product.브랜드 || '브랜드 없음';
            const imageUrl = product.이미지URL || product.사진 || product.대표이미지URL || '';
            const price = product.원가 || product.가격 || product.할인가 || 0;
            const productLink = product.상품링크 || product.링크 || product.URL || '';
            
            // 디버깅: 상품 링크 정보 출력
            console.log(`상품 ${index + 1}:`, {
                name: productName,
                link: productLink,
                hasLink: productLink && productLink.trim() !== ''
            });
            
            // 링크가 있는지 확인
            const hasLink = productLink && productLink.trim() !== '';
            
                         recommendationsHTML += `
                 <div class="chatbot-product-card" data-product-index="${index}">
                     
                     <!-- 상품 이미지 -->
                     <div style="position: relative; flex-shrink: 0;">
                         ${imageUrl && imageUrl.trim() !== '' ? 
                             `<img src="${imageUrl}" alt="${productName}" 
                                  onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                              <div style="width: 60px; height: 60px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 8px; display: none; align-items: center; justify-content: center; color: white; font-size: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.15);">👕</div>`
                             :
                             `<div style="width: 60px; height: 60px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-size: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.15);">👕</div>`
                         }
                     </div>
                     
                     <!-- 상품 정보 -->
                     <div style="flex: 1; min-width: 0; display: flex; flex-direction: column; justify-content: space-between;">
                         <div>
                             <h4 style="
                                 margin: 0 0 4px 0; 
                                 font-size: 0.9rem; 
                                 color: #2c3e50; 
                                 font-weight: 700;
                                 overflow: hidden; 
                                 text-overflow: ellipsis; 
                                 white-space: nowrap;
                                 line-height: 1.2;
                             ">${productName}</h4>
                             <p style="
                                 margin: 0 0 3px 0; 
                                 font-size: 0.75rem; 
                                 color: #E50914; 
                                 font-weight: 600;
                                 opacity: 0.9;
                             ">${brand}</p>
                             <p style="
                                 margin: 0; 
                                 font-size: 0.95rem; 
                                 color: #e74c3c; 
                                 font-weight: 700;
                                 font-family: 'Arial', sans-serif;
                             ">${price ? price.toLocaleString() + '원' : '가격 정보 없음'}</p>
                         </div>
                         
                         <!-- 액션 버튼들 -->
                         <div style="display: flex; gap: 6px; margin-top: 8px;">
                             <button class="chatbot-jjim-btn" 
                             onclick="addToJjim('${product.상품코드 || product.상품ID || index}', '${productName}', '${brand}', '${imageUrl}', '${price}', '${productLink}')">
                                 ❤️ 찜하기
                             </button>
                             ${hasLink ? 
                                 `<button class="chatbot-view-btn" 
                                 onclick="openProductLink('${productLink}', '${productName}')">
                                     상품 보기
                                 </button>` 
                                 : 
                                 `<span style="
                                     color: #6c757d; 
                                     font-size: 0.7rem; 
                                     font-style: italic;
                                     text-align: center;
                                     padding: 8px 12px;
                                     background: #f8f9fa;
                                     border-radius: 8px;
                                     flex: 1;
                                     display: flex;
                                     align-items: center;
                                     justify-content: center;
                                     min-height: 36px;
                                 ">상품 정보</span>`
                             }
                         </div>
                     </div>
                 </div>
             `;
        });
        recommendationsHTML += '</div>';
        
        recommendationsContent.innerHTML = recommendationsHTML;
        recommendationsWrapper.appendChild(recommendationsContent);
        
        // 카드 클릭 이벤트 제거 - 버튼으로만 액션 수행
        
        widgetMessages.appendChild(recommendationsWrapper);
        widgetMessages.scrollTop = widgetMessages.scrollHeight;
    }

    function showLoadingIndicator() {
        const loadingWrapper = document.createElement("div");
        loadingWrapper.classList.add("widget-message", "widget-bot-message", "loading-dots");
        loadingWrapper.id = "loading-indicator";

        const loadingContent = document.createElement("div");
        loadingContent.classList.add("widget-message-content");
        loadingContent.innerHTML = `<span class="loading-indicator"></span><span class="loading-indicator"></span><span class="loading-indicator"></span>`;
        loadingWrapper.appendChild(loadingContent);

        widgetMessages.appendChild(loadingWrapper);
        widgetMessages.scrollTop = widgetMessages.scrollHeight;
    }

    function removeLoadingIndicator() {
        const loadingIndicator = document.getElementById("loading-indicator");
        if (loadingIndicator) {
            loadingIndicator.remove();
        }
    }

    // 상품 링크 열기 함수
    function openProductLink(link, productName) {
        console.log('openProductLink 호출됨:', { link, productName });
        
        if (link && link.trim() !== '') {
            // 링크가 http로 시작하지 않으면 https:// 추가
            let finalLink = link.trim();
            if (!finalLink.startsWith('http://') && !finalLink.startsWith('https://')) {
                finalLink = 'https://' + finalLink;
            }
            
            console.log('최종 링크:', finalLink);
            
            try {
                // 먼저 새 탭에서 열기 시도
                const newWindow = window.open(finalLink, '_blank');
                if (newWindow) {
                    console.log('새 창이 성공적으로 열렸습니다.');
                } else {
                    console.log('팝업이 차단되었습니다. 현재 탭에서 열기 시도...');
                    // 팝업이 차단되면 현재 탭에서 열기
                    if (confirm('팝업이 차단되었습니다. 현재 탭에서 상품 페이지를 여시겠습니까?')) {
                        window.location.href = finalLink;
                    } else {
                        // 사용자에게 팝업 허용 방법 안내
                        alert('팝업을 허용하려면:\n1. 브라우저 주소창 옆의 팝업 차단 아이콘을 클릭\n2. "항상 허용" 선택\n3. 페이지 새로고침 후 다시 시도');
                    }
                }
            } catch (error) {
                console.error('링크 열기 오류:', error);
                alert(`${productName}의 링크를 열 수 없습니다.`);
            }
        } else {
            // 링크가 없으면 알림
            console.log('링크가 비어있습니다.');
            alert(`${productName}의 상품 링크가 없습니다.`);
        }
    }

    // 전역 함수로 등록 (HTML에서 직접 호출 가능)
    window.openProductLink = openProductLink;

    // 찜하기 기능 구현
    async function addToJjim(productId, productName, brand, imageUrl, price, productLink) {
        try {
            // 찜하기 API 호출
            const response = await fetch('/jjim/add', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: new URLSearchParams({
                    'product_id': productId,
                    'product_name': productName,
                    'brand': brand,
                    'image_url': imageUrl,
                    'price': price,
                    'product_link': productLink
                })
            });

            const result = await response.json();

            if (result.success) {
                // 찜하기 성공 시 버튼 스타일 변경
                const jjimBtn = event.target;
                jjimBtn.innerHTML = '❤️';
                jjimBtn.style.background = 'rgba(231, 76, 60, 0.1)';
                jjimBtn.style.borderColor = '#e74c3c';
                jjimBtn.style.color = '#e74c3c';
                
                // 성공 메시지 표시
                showFeedbackMessage('찜목록에 추가되었습니다! 💕', 'success');
                
                // 피드백 요청 (세션당 한 번만)
                if (!sessionFeedbackState.feedbackRequested) {
                    setTimeout(() => {
                        showFeedbackModal(productId, productName, '찜하기');
                    }, 1000);
                }
            } else {
                showFeedbackMessage(result.message || '찜하기에 실패했습니다.', 'error');
            }
        } catch (error) {
            console.error('찜하기 오류:', error);
            showFeedbackMessage('찜하기 중 오류가 발생했습니다.', 'error');
        }
    }

    // 피드백 메시지 표시 함수
    function showFeedbackMessage(message, type = 'info') {
        const messageDiv = document.createElement('div');
        messageDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 8px;
            color: white;
            font-weight: 600;
            z-index: 10000;
            animation: slideIn 0.3s ease;
            ${type === 'success' ? 'background: linear-gradient(135deg, #27ae60, #2ecc71);' : 
              type === 'error' ? 'background: linear-gradient(135deg, #e74c3c, #c0392b);' : 
              'background: linear-gradient(135deg, #3498db, #2980b9);'}
        `;
        messageDiv.textContent = message;
        
        document.body.appendChild(messageDiv);
        
        // 3초 후 자동 제거
        setTimeout(() => {
            messageDiv.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                if (messageDiv.parentNode) {
                    messageDiv.parentNode.removeChild(messageDiv);
                }
            }, 300);
        }, 3000);
    }

    // 피드백 모달 표시 함수
    function showFeedbackModal(productId, productName, action) {
        const modal = document.createElement('div');
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10001;
            animation: fadeIn 0.3s ease;
        `;
        
        modal.innerHTML = `
            <div style="
                background: white;
                padding: 24px;
                border-radius: 12px;
                max-width: 400px;
                width: 90%;
                text-align: center;
                box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            ">
                <h3 style="margin: 0 0 16px 0; color: #2c3e50; font-size: 1.2rem;">
                    이 추천이 어떠셨나요? 🎉
                </h3>
                <p style="margin: 0 0 20px 0; color: #7f8c8d; font-size: 0.9rem;">
                    "${productName}"을 ${action}하셨네요!<br>
                    앞으로 더 나은 추천을 위해 간단한 피드백을 남겨주세요.
                </p>
                
                <div style="display: flex; gap: 12px; margin-bottom: 20px;">
                    <button class="feedback-btn like-btn" style="
                        flex: 1;
                        padding: 12px;
                        border: 2px solid #27ae60;
                        background: white;
                        color: #27ae60;
                        border-radius: 8px;
                        font-weight: 600;
                        cursor: pointer;
                        transition: all 0.2s ease;
                    " onmouseover="this.style.background='#27ae60'; this.style.color='white'" onmouseout="this.style.background='white'; this.style.color='#27ae60'">
                        👍 좋아요
                    </button>
                    <button class="feedback-btn dislike-btn" style="
                        flex: 1;
                        padding: 12px;
                        border: 2px solid #e74c3c;
                        background: white;
                        color: #e74c3c;
                        border-radius: 8px;
                        font-weight: 600;
                        cursor: pointer;
                        transition: all 0.2s ease;
                    " onmouseover="this.style.background='#e74c3c'; this.style.color='white'" onmouseout="this.style.background='white'; this.style.color='#e74c3c'">
                        👎 아쉬워요
                    </button>
                </div>
                
                <textarea id="feedback-reason" placeholder="이유를 간단히 알려주세요 (선택사항)" style="
                    width: 100%;
                    padding: 12px;
                    border: 1px solid #ddd;
                    border-radius: 8px;
                    resize: vertical;
                    min-height: 80px;
                    font-family: inherit;
                    margin-bottom: 16px;
                "></textarea>
                
                <div style="display: flex; gap: 8px;">
                    <button id="submit-feedback" style="
                        flex: 1;
                        padding: 12px;
                        background: linear-gradient(135deg, #3498db, #2980b9);
                        color: white;
                        border: none;
                        border-radius: 8px;
                        font-weight: 600;
                        cursor: pointer;
                        transition: all 0.2s ease;
                    " onmouseover="this.style.transform='translateY(-1px)'" onmouseout="this.style.transform='translateY(0)'">
                        피드백 제출
                    </button>
                    <button id="skip-feedback" style="
                        padding: 12px 20px;
                        background: #95a5a6;
                        color: white;
                        border: none;
                        border-radius: 8px;
                        font-weight: 600;
                        cursor: pointer;
                        transition: all 0.2s ease;
                    " onmouseover="this.style.background='#7f8c8d'" onmouseout="this.style.background='#95a5a6'">
                        건너뛰기
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // 피드백 제출 이벤트
        modal.querySelector('#submit-feedback').addEventListener('click', () => {
            const feedbackType = modal.querySelector('.like-btn').classList.contains('active') ? 'like' : 'dislike';
            const reason = modal.querySelector('#feedback-reason').value;
            
            // 피드백 데이터 저장 (실제 구현 시 API 호출)
            console.log('피드백 제출:', { productId, productName, feedbackType, reason, action });
            
            // 모달 닫기
            document.body.removeChild(modal);
            sessionFeedbackState.feedbackRequested = true;
            
            showFeedbackMessage('피드백을 보내주셔서 감사합니다! 💝', 'success');
        });
        
        // 건너뛰기 이벤트
        modal.querySelector('#skip-feedback').addEventListener('click', () => {
            document.body.removeChild(modal);
            sessionFeedbackState.feedbackRequested = true;
        });
        
        // 좋아요/아쉬워요 버튼 이벤트
        modal.querySelectorAll('.feedback-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                modal.querySelectorAll('.feedback-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                btn.style.background = btn.classList.contains('like-btn') ? '#27ae60' : '#e74c3c';
                btn.style.color = 'white';
            });
        });
        
        // 모달 외부 클릭 시 닫기
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                document.body.removeChild(modal);
                sessionFeedbackState.feedbackRequested = true;
            }
        });
    }

    // 세션별 피드백 상태 관리
    const sessionFeedbackState = {
        sessionId: null,
        feedbackRequested: false
    };

    // 전역 함수로 등록
    window.addToJjim = addToJjim;
    window.showFeedbackModal = showFeedbackModal;
});
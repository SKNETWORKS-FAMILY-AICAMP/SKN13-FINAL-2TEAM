document.addEventListener("DOMContentLoaded", () => {
    // --- DOM 요소 --- //
    const floatingWidget = document.getElementById("floating-chatbot-widget");
    const toggleBtn = document.getElementById("chatbot-toggle-btn");
    const closeBtn = document.getElementById("widget-close-btn");
    const widgetMessages = document.getElementById("widget-messages");
    const widgetForm = document.getElementById("widget-form");
    const widgetInput = document.getElementById("widget-input");
    const imageUploadBtn = document.getElementById("widget-image-upload-btn");
    const imageInput = document.getElementById("widget-image-input");

    // --- 상태 변수 --- //
    let currentSessionId = localStorage.getItem('chatbot_session_id') || null;
    let attachedFile = null; // 첨부된 이미지 파일 상태

    // --- 초기화 --- //
    if (floatingWidget && toggleBtn && closeBtn) {
        initializeFloatingWidget();
    }

    // --- 함수 정의 --- //

    function initializeFloatingWidget() {
        toggleBtn.addEventListener("click", () => {
            floatingWidget.classList.add("active");
            toggleBtn.classList.add("hidden");
            widgetInput.focus();
            if (currentSessionId && isValidUUID(currentSessionId)) {
                loadPreviousMessages();
            }
        });

        closeBtn.addEventListener("click", () => {
            floatingWidget.classList.remove("active");
            toggleBtn.classList.remove("hidden");
        });

        widgetForm.addEventListener("submit", handleFormSubmit);
        imageUploadBtn.addEventListener("click", () => imageInput.click());
        imageInput.addEventListener("change", handleFileSelect);

        // Enter 키로 전송하는 기능 추가
        widgetInput.addEventListener('keydown', (e) => {
            // Shift + Enter는 줄바꿈을 위해 제외
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault(); // 기본 동작(줄바꿈 등) 방지
                widgetForm.requestSubmit(); // 폼의 submit 이벤트를 강제로 실행
            }
        });

        setTimeout(() => {
            if (widgetMessages.children.length === 0) {
                addMessage("안녕하세요! 의류 추천 챗봇입니다. 어떤 스타일을 찾으시나요? 😊", "bot");
            }
        }, 500);
    }

    function isValidUUID(uuid) {
        const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
        return uuid ? uuidRegex.test(uuid) : false;
    }

    function handleFileSelect(e) {
        const file = e.target.files[0];
        if (file) {
            attachedFile = file;
            displayImagePreview(file);
        }
        e.target.value = null;
    }

    function displayImagePreview(file) {
        // 기존 미리보기가 있다면 제거
        const existingPreview = document.getElementById('widget-attachment-preview');
        if (existingPreview) existingPreview.remove();

        const previewURL = URL.createObjectURL(file);
        
        const previewContainer = document.createElement('div');
        previewContainer.id = 'widget-attachment-preview';
        previewContainer.innerHTML = `
            <div class="attachment-item">
                <img src="${previewURL}" alt="Attachment Preview">
                <button class="remove-attachment-btn">&times;</button>
            </div>
        `;
        
        widgetForm.insertBefore(previewContainer, widgetInput);

        // 'X' 버튼에 클릭 이벤트 리스너 추가
        previewContainer.querySelector('.remove-attachment-btn').addEventListener('click', removeAttachment);
    }

    // [수정] 첨부 파일 및 미리보기 제거 함수
    function removeAttachment() {
        attachedFile = null;
        const existingPreview = document.getElementById('widget-attachment-preview');
        if (existingPreview) {
            existingPreview.remove();
        }
    }

    // [수정] 폼 제출 핸들러
    async function handleFormSubmit(e) {
        e.preventDefault();
        
        const message = widgetInput.value.trim();
        const fileToSend = attachedFile; // 전송 직전의 파일 상태를 캡처

        if (!message && !fileToSend) return;

        // FormData 생성
        const formData = new FormData();
        if (message) {
            formData.append('user_input', message);
        }
        if (fileToSend) {
            formData.append('image', fileToSend, fileToSend.name);
        }
        if (currentSessionId && isValidUUID(currentSessionId)) {
            formData.append('session_id', currentSessionId);
        }

        // UI 업데이트 (사용자 메시지 표시)
        if (message) {
            addMessage(message, "user");
        }
        if (fileToSend) {
            const previewURL = URL.createObjectURL(fileToSend);
            addMessage(`<img src="${previewURL}" class="message-image-preview" alt="Sent Image">`, "user");
        }

        // 입력 필드와 첨부 파일 상태 초기화
        widgetInput.value = "";
        removeAttachment(); // 미리보기 및 파일 변수 초기화
        showLoadingIndicator();

        // API 요청
        await sendRequestToAPI(formData);
    }

    async function sendRequestToAPI(formData) {
        const userInput = formData.get('user_input') || "";
        const weatherKeywords = ['날씨', '기온', '덥', '춥', '비와', '눈와'];
        const isWeatherQuery = weatherKeywords.some(keyword => userInput.includes(keyword));

        if (isWeatherQuery) {
            try {
                const position = await new Promise((resolve, reject) => {
                    navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 });
                });
                formData.append('latitude', String(position.coords.latitude));
                formData.append('longitude', String(position.coords.longitude));
            } catch (error) {
                removeLoadingIndicator();
                addMessage('현재 위치를 가져올 수 없어요. 😥', 'bot');
                return;
            }
        }

        try {
            const response = await fetch('/chat/', {
                method: 'POST',
                body: formData,
                headers: {
                    'Authorization': 'Bearer ' + localStorage.getItem('access_token')
                }
            });

            if (!response.ok) {
                const text = await response.text(); // 404 등일 때 HTML 받아 디버깅
                throw new Error(`HTTP ${response.status} - ${text.slice(0, 200)}`);
            }

            const data = await response.json();
            removeLoadingIndicator();

            if (data.message) {
                addMessage(data.message, "bot");
                if (data.products && data.products.length > 0) {
                    addRecommendations(data.products, data.recommendation_id);
                }
            } else {
                addMessage("죄송합니다. 오류가 발생했습니다.", "bot");
            }

            if (data.session_id && data.session_id !== currentSessionId) {
                currentSessionId = data.session_id;
                if (isValidUUID(currentSessionId)) {
                    localStorage.setItem('chatbot_session_id', currentSessionId);
                }
            }
        } catch (error) {
            console.error('Error:', error);
            removeLoadingIndicator();
            addMessage(`네트워크 오류가 발생했습니다: ${error.message}`, "bot");
        }
    }

    function addMessage(message, sender) {
        const messageWrapper = document.createElement("div");
        messageWrapper.classList.add("widget-message", `widget-${sender}-message`);
        const messageContent = document.createElement("div");
        messageContent.classList.add("widget-message-content");
        messageContent.innerHTML = formatMessage(message);
        messageWrapper.appendChild(messageContent);
        widgetMessages.appendChild(messageWrapper);
        widgetMessages.scrollTop = widgetMessages.scrollHeight;
    }

    function formatMessage(message) {
        if (message.startsWith('<img')) return message;
        return message.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    }

    function addRecommendations(recommendations, recommendationId) {
        const recommendationsWrapper = document.createElement("div");
        recommendationsWrapper.classList.add("widget-message", "widget-bot-message");
        const recommendationsContent = document.createElement("div");
        recommendationsContent.classList.add("widget-message-content");
        let recommendationsHTML = '<div class="recommendations-grid">';
        recommendations.forEach(product => {
            const p_id = product.상품코드 || product.id;
            const p_rec_id = product.recommendation_id || recommendationId;
            recommendationsHTML += `
                <div class="product-card">
                    <img src="${product.사진 || product.image_url}" alt="${product.상품명}" class="recommendation-img">
                    <div class="product-info">
                        <div class="product-brand">${product.한글브랜드명 || '브랜드 없음'}</div>
                        <div class="product-name">${product.상품명}</div>
                        <div class="product-price">${product.가격 ? product.가격.toLocaleString() + '원' : ''}</div>
                    </div>
                </div>`;
        });
        recommendationsHTML += '</div>';
        recommendationsContent.innerHTML = recommendationsHTML;
        recommendationsWrapper.appendChild(recommendationsContent);
        widgetMessages.appendChild(recommendationsWrapper);
        widgetMessages.scrollTop = widgetMessages.scrollHeight;
    }

    function showLoadingIndicator() {
        const indicator = document.createElement("div");
        indicator.id = "loading-indicator";
        indicator.classList.add("widget-message", "widget-bot-message");
        indicator.innerHTML = `<div class="widget-message-content"><div class="loading-dot"></div><div class="loading-dot"></div><div class="loading-dot"></div></div>`;
        widgetMessages.appendChild(indicator);
        widgetMessages.scrollTop = widgetMessages.scrollHeight;
    }

    function removeLoadingIndicator() {
        const indicator = document.getElementById("loading-indicator");
        if (indicator) indicator.remove();
    }

    async function loadPreviousMessages() {
        if (!currentSessionId || !isValidUUID(currentSessionId)) return;
        try {
<<<<<<< HEAD
            const response = await fetch(`/chat/session/${currentSessionId}/messages`);
=======
            // 찜하기 API 호출
            const response = await fetch('/jjim/add', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                credentials: 'same-origin',  // 쿠키 포함
                body: new URLSearchParams({
                    'product_id': productId
                })
            });

            const responseText = await response.text();
            let result;
            try {
                result = JSON.parse(responseText);
            } catch (parseError) {
                showFeedbackMessage('서버 응답 형식 오류', 'error');
                return;
            }

            if (result.success) {
                // 찜하기 성공 시 버튼 스타일 변경 및 제거 기능 활성화
                const jjimBtn = document.querySelector(`[data-product-id="${productId}"]`);
                if (jjimBtn) {
                    jjimBtn.innerHTML = '❌ 찜해제';
                    jjimBtn.classList.add('jjim-active'); // CSS 클래스로 스타일 적용
                    jjimBtn.dataset.jjimStatus = 'jjim'; // 찜 상태 표시
                    
                    // 제거 기능을 위한 클릭 이벤트 변경
                    jjimBtn.onclick = () => removeFromJjim(productId, productName, brand, imageUrl, price, productLink, recommendationId);
                }
                
                // 성공 메시지 표시
                showFeedbackMessage('찜목록에 추가되었습니다! 💕', 'success');
            } else {
                showFeedbackMessage(result.message || '찜하기에 실패했습니다.', 'error');
            }
        } catch (error) {
            console.error('찜하기 오류:', error);
            showFeedbackMessage('찜하기 중 오류가 발생했습니다.', 'error');
        }
    }

    // 찜목록에서 제거하는 함수
    async function removeFromJjim(productId, productName, brand, imageUrl, price, productLink, recommendationId) {
        // productId가 유효한지 확인
        if (!productId || productId === 'undefined' || productId === 'null') {
            showFeedbackMessage('상품코드를 찾을 수 없습니다.', 'error');
            return;
        }
        
        try {
            // 찜목록에서 제거 API 호출
            const response = await fetch('/jjim/remove', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                credentials: 'same-origin',  // 쿠키 포함
                body: new URLSearchParams({
                    'product_id': productId
                })
            });

            const responseText = await response.text();
            let result;
            try {
                result = JSON.parse(responseText);
            } catch (parseError) {
                showFeedbackMessage('서버 응답 형식 오류', 'error');
                return;
            }

            if (result.success) {
                // 제거 성공 시 버튼 스타일 변경 및 찜하기 기능 활성화
                const jjimBtn = document.querySelector(`[data-product-id="${productId}"]`);
                if (jjimBtn) {
                    jjimBtn.innerHTML = '❤️ 찜하기';
                    jjimBtn.classList.remove('jjim-active'); // CSS 클래스 제거하여 기본 스타일로 복원
                    jjimBtn.dataset.jjimStatus = 'not-jjim'; // 찜하지 않은 상태 표시
                    
                    // 찜하기 기능을 위한 클릭 이벤트 변경
                    jjimBtn.onclick = () => addToJjim(productId, productName, brand, imageUrl, price, productLink, recommendationId);
                }
                
                // 성공 메시지 표시
                showFeedbackMessage('찜목록에서 제거되었습니다! 💔', 'success');
            } else {
                showFeedbackMessage(result.message || '찜목록에서 제거하는데 실패했습니다.', 'error');
            }
        } catch (error) {
            console.error('찜목록 제거 오류:', error);
            showFeedbackMessage('찜목록에서 제거하는 중 오류가 발생했습니다.', 'error');
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





    // 빠른 피드백 제출 함수 (좋아요/싫어요)
    async function submitQuickFeedback(productId, productName, rating, recommendationId) {
        // recommendationId가 비어있는지 확인
        if (!recommendationId || recommendationId === '') {
            showFeedbackMessage('추천 ID를 찾을 수 없습니다. 잠시 후 다시 시도해주세요.', 'error');
            return;
        }
        
        // 이미 피드백을 제출한 버튼인지 확인
        const button = event.target;
        if (button.disabled) {
            return; // 이미 비활성화된 버튼이면 무시
        }
        
        try {
            // 버튼 즉시 비활성화 (중복 클릭 방지)
            button.disabled = true;
            button.style.opacity = '0.6';
            button.style.cursor = 'not-allowed';
            
            // 같은 상품의 다른 피드백 버튼들도 비활성화 (코멘트 버튼은 제외)
            const productCard = button.closest('.chatbot-product-card');
            if (productCard) {
                const otherFeedbackBtns = productCard.querySelectorAll('.feedback-like-btn, .feedback-dislike-btn');
                otherFeedbackBtns.forEach(btn => {
                    if (btn !== button) {
                        btn.disabled = true;
                        btn.style.opacity = '0.6';
                        btn.style.cursor = 'not-allowed';
                    }
                });
                // 코멘트 버튼은 계속 활성화 (별도로 저장 가능)
            }
            
            const formData = new FormData();
            formData.append('recommendation_id', recommendationId);
            formData.append('feedback_rating', rating);
            formData.append('feedback_reason', ''); // 빠른 피드백은 이유 없음
            
            console.log('빠른 피드백 제출:', {
                productId,
                productName,
                rating,
                recommendationId
            });
            
            const response = await fetch('/chat/feedback', {
                method: 'POST',
                body: formData,
                credentials: 'same-origin'
            });
            
            const result = await response.json();
            
            if (result.success) {
                console.log('피드백 성공 응답:', result);
                
                let message;
                if (result.already_feedback) {
                    message = '이미 피드백을 제공하셨습니다! 👍';
                    console.log('이미 피드백 존재 - 메시지:', message);
                } else {
                    if (result.feedback_type === 'comment') {
                        message = '코멘트가 성공적으로 저장되었습니다! 💝';
                    } else {
                        message = rating === 1 ? '좋아요! 감사합니다! 👍' : '피드백 감사합니다! 👎';
                    }
                    console.log('새로운 피드백 - 메시지:', message);
                }
                
                console.log('showFeedbackMessage 호출 전');
                showFeedbackMessage(message, 'success');
                console.log('showFeedbackMessage 호출 후');
                
                // 성공 시 버튼별로 다른 완료 표시
                console.log('버튼 상태 변경 전:', button.innerHTML, button.style.background);
                
                // 각 버튼 타입에 맞게 완료 표시
                if (button.classList.contains('feedback-comment-btn')) {
                    // 코멘트 버튼인 경우
                    button.innerHTML = '💬 완료';
                    button.style.setProperty('background', '#3498db', 'important');
                } else if (button.classList.contains('feedback-like-btn')) {
                    // 좋아요 버튼인 경우
                    button.innerHTML = '👍 완료';
                    button.style.setProperty('background', '#27ae60', 'important');
                } else if (button.classList.contains('feedback-dislike-btn')) {
                    // 싫어요 버튼인 경우
                    button.innerHTML = '👎 완료';
                    button.style.setProperty('background', '#e74c3c', 'important');
                }
                
                button.style.setProperty('color', 'white', 'important');
                button.style.setProperty('opacity', '0.8', 'important');
                
                console.log('버튼 상태 변경 후:', button.innerHTML, button.style.background);
                
                // 버튼 비활성화 상태 확인
                console.log('버튼 비활성화 상태:', button.disabled);
                
                // CSS 클래스도 추가
                button.classList.add('feedback-completed');
            } else {
                showFeedbackMessage(`피드백 저장에 실패했습니다: ${result.message}`, 'error');
                
                // 실패 시 버튼 다시 활성화
                button.disabled = false;
                button.style.opacity = '1';
                button.style.cursor = 'pointer';
                
                // 다른 버튼들도 다시 활성화 (코멘트 버튼은 이미 활성화 상태)
                if (productCard) {
                    const otherFeedbackBtns = productCard.querySelectorAll('.feedback-like-btn, .feedback-dislike-btn');
                    otherFeedbackBtns.forEach(btn => {
                        btn.disabled = false;
                        btn.style.opacity = '1';
                        btn.style.cursor = 'pointer';
                    });
                }
            }
        } catch (error) {
            console.error('빠른 피드백 제출 오류:', error);
            showFeedbackMessage('피드백 전송 중 오류가 발생했습니다.', 'error');
            
            // 오류 시 버튼 다시 활성화
            button.disabled = false;
            button.style.opacity = '1';
            button.style.cursor = 'pointer';
            
                            // 다른 버튼들도 다시 활성화 (코멘트 버튼은 이미 활성화 상태)
                const productCard = button.closest('.chatbot-product-card');
                if (productCard) {
                    const otherFeedbackBtns = productCard.querySelectorAll('.feedback-like-btn, .feedback-dislike-btn');
                    otherFeedbackBtns.forEach(btn => {
                        btn.disabled = false;
                        btn.style.opacity = '1';
                        btn.style.cursor = 'pointer';
                    });
                }
        }
    }
    
    // 코멘트 모달 표시 함수
    function showCommentModal(productId, productName, recommendationId) {
        // recommendationId가 비어있는지 확인
        if (!recommendationId || recommendationId === '') {
            showFeedbackMessage('추천 ID를 찾을 수 없습니다. 잠시 후 다시 시도해주세요.', 'error');
            return;
        }
        
        const modal = document.createElement('div');
        modal.className = 'comment-modal';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.6);
            backdrop-filter: blur(8px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10001;
            animation: fadeIn 0.3s ease;
        `;
        
        modal.innerHTML = `
            <div class="comment-content" style="
                background: white;
                padding: 24px;
                border-radius: 16px;
                max-width: 400px;
                width: 90%;
                text-align: center;
                box-shadow: 0 20px 60px rgba(0,0,0,0.15);
            ">
                <h3 style="margin: 0 0 16px 0; color: #2c3e50; font-size: 1.2rem;">
                    💬 상품추천이 마음에 드셨나요?
                </h3>
                <textarea id="comment-text" placeholder="추천에 대한 의견을 자유롭게 작성해주세요..." style="
                    width: 100%;
                    padding: 12px;
                    border: 2px solid #e9ecef;
                    border-radius: 8px;
                    resize: vertical;
                    min-height: 80px;
                    font-family: inherit;
                    font-size: 0.9rem;
                    margin-bottom: 16px;
                    box-sizing: border-box;
                "></textarea>
                <div style="display: flex; gap: 8px;">
                    <button id="submit-comment" style="
                        flex: 1;
                        padding: 12px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        border: none;
                        border-radius: 8px;
                        font-weight: 600;
                        cursor: pointer;
                        transition: all 0.3s ease;
                    ">
                        코멘트 제출
                    </button>
                    <button id="cancel-comment" style="
                        padding: 12px 16px;
                        background: #95a5a6;
                        color: white;
                        border: none;
                        border-radius: 8px;
                        font-weight: 600;
                        cursor: pointer;
                        transition: all 0.3s ease;
                    ">
                        취소
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // 코멘트 제출 이벤트
        modal.querySelector('#submit-comment').addEventListener('click', async () => {
            const comment = modal.querySelector('#comment-text').value.trim();
            
            if (!comment) {
                alert('코멘트를 입력해주세요.');
                return;
            }
            
            // 제출 버튼 비활성화
            const submitBtn = modal.querySelector('#submit-comment');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '제출 중...';
            submitBtn.style.opacity = '0.6';
            
            try {
                const formData = new FormData();
                formData.append('recommendation_id', recommendationId);
                formData.append('feedback_rating', 1); // 코멘트가 있으면 기본적으로 긍정적
                formData.append('feedback_reason', comment);
                
                const response = await fetch('/chat/feedback', {
                    method: 'POST',
                    body: formData,
                    credentials: 'same-origin'
                });
                
                const result = await response.json();
                
                if (result.success) {
                    let message;
                    if (result.already_feedback) {
                        message = '이미 피드백을 제공하셨습니다! 💝';
                    } else {
                        if (result.feedback_type === 'comment') {
                            message = '코멘트가 성공적으로 저장되었습니다! 💝';
                        } else {
                            message = '코멘트를 보내주셔서 감사합니다! 💝';
                        }
                    }
                    showFeedbackMessage(message, 'success');
                    
                    // 성공 시 해당 상품의 모든 피드백 버튼 비활성화
                    const productCard = document.querySelector(`[data-product-id="${productId}"]`)?.closest('.chatbot-product-card');
                    if (productCard) {
                        const feedbackBtns = productCard.querySelectorAll('.feedback-like-btn, .feedback-dislike-btn, .feedback-comment-btn');
                        feedbackBtns.forEach(btn => {
                            btn.disabled = true;
                            btn.style.opacity = '0.6';
                            btn.style.cursor = 'not-allowed';
                            
                            // 각 버튼 타입에 맞게 완료 표시
                            if (btn.classList.contains('feedback-comment-btn')) {
                                btn.innerHTML = '💬 완료';
                                btn.style.background = '#3498db';
                            } else if (btn.classList.contains('feedback-like-btn')) {
                                btn.innerHTML = '👍 완료';
                                btn.style.background = '#27ae60';
                            } else if (btn.classList.contains('feedback-dislike-btn')) {
                                btn.innerHTML = '👎 완료';
                                btn.style.background = '#e74c3c';
                            }
                        });
                    }
                    
                    document.body.removeChild(modal);
                } else {
                    showFeedbackMessage(`코멘트 저장에 실패했습니다: ${result.message}`, 'error');
                    
                    // 실패 시 버튼 다시 활성화
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '코멘트 제출';
                    submitBtn.style.opacity = '1';
                }
            } catch (error) {
                console.error('코멘트 제출 오류:', error);
                showFeedbackMessage('코멘트 전송 중 오류가 발생했습니다.', 'error');
                
                // 오류 시 버튼 다시 활성화
                submitBtn.disabled = false;
                submitBtn.innerHTML = '코멘트 제출';
                submitBtn.style.opacity = '1';
            }
        });
        
        // 취소 이벤트
        modal.querySelector('#cancel-comment').addEventListener('click', () => {
            document.body.removeChild(modal);
        });
        
        // 모달 외부 클릭 시 닫기
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                document.body.removeChild(modal);
            }
        });
    }
    
    // 전역 함수로 등록
    window.addToJjim = addToJjim;
    window.removeFromJjim = removeFromJjim;
    window.submitQuickFeedback = submitQuickFeedback;
    window.showCommentModal = showCommentModal;

    // 피드백 제출 함수 (좋아요/싫어요)
    async function submitFeedback(recommendationId, rating) {
        try {
            // recommendationId가 리스트인지 확인하고 리스트로 변환
            const recommendationIds = Array.isArray(recommendationId) ? recommendationId : [recommendationId];
            
            const formData = new FormData();
            recommendationIds.forEach(id => {
                formData.append('recommendation_id', id);
            });
            formData.append('feedback_rating', rating);
            formData.append('feedback_reason', '');
            
            const response = await fetch('/chat/feedback', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                alert(result.message);
            } else {
                alert('피드백 제출에 실패했습니다: ' + result.message);
            }
        } catch (error) {
            console.error('피드백 제출 오류:', error);
            alert('피드백 제출 중 오류가 발생했습니다.');
        }
    }

    async function sendImageToAPI(file) {
        try {
            const formData = new FormData();
            formData.append('image', file);

            const response = await fetch('/chat/image-recommend', {
                method: 'POST',
                body: formData
            });

>>>>>>> 8900d37b45e70c41d334ebc234bbb89d41519005
            const data = await response.json();
            if (data.success && data.messages) {
                widgetMessages.innerHTML = '';
                data.messages.forEach(msg => {
                    addMessage(msg.text, msg.type);
                    if (msg.products && msg.products.length > 0) {
                        addRecommendations(msg.products, msg.recommendation_id);
                    }
                });
            }
        } catch (error) {
            console.error('Error loading messages:', error);
        }
    }
});
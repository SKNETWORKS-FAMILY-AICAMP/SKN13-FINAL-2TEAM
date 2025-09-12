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

        widgetInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                widgetForm.requestSubmit();
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
            // A new file is selected, so first remove any existing preview.
            removeAttachment();
            // Now, set the new file and display its preview.
            attachedFile = file;
            displayImagePreview(file);
        }
        e.target.value = null;
    }

    function displayImagePreview(file) {
        const previewURL = URL.createObjectURL(file);
        
        const previewContainer = document.createElement('div');
        previewContainer.id = 'chatbot-image-attachment-preview';
        // Store the URL in a data attribute for later revocation
        previewContainer.innerHTML = `
            <div class="chatbot-image-attachment-item">
                <img src="${previewURL}" alt="Attachment Preview" data-url="${previewURL}">
                <button class="chatbot-image-remove-btn">&times;</button>
            </div>
        `;
        
        // Robust insertion: Insert before the parent of the input field.
        if (widgetInput.parentNode) {
            widgetInput.parentNode.insertBefore(previewContainer, widgetInput);
        } else {
            widgetForm.appendChild(previewContainer);
        }

        previewContainer.querySelector('.chatbot-image-remove-btn').addEventListener('click', removeAttachment);
    }

    function removeAttachment() {
        const existingPreview = document.getElementById('chatbot-image-attachment-preview');
        if (existingPreview) {
            // Prevent memory leaks by revoking the object URL
            const img = existingPreview.querySelector('img');
            if (img && img.dataset.url) {
                URL.revokeObjectURL(img.dataset.url);
            }
            existingPreview.remove();
        }
        attachedFile = null;
    }

    async function handleFormSubmit(e) {
        e.preventDefault();
        
        const message = widgetInput.value.trim();
        const fileToSend = attachedFile;

        if (!message && !fileToSend) return;

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

        if (message) {
            addMessage(message, "user");
        }
        if (fileToSend) {
            const previewURL = URL.createObjectURL(fileToSend);
            addMessage(`<img src="${previewURL}" class="chatbot-user-image-message" alt="Sent Image">`, "user");
        }

        widgetInput.value = "";
        removeAttachment();
        showLoadingIndicator();

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
                addMessage('현재 위치를 가져올 수 없어요. 😥 브라우저의 위치 정보 접근을 허용했는지 확인해주세요!', 'bot');
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
                const text = await response.text();
                throw new Error(`HTTP ${response.status} - ${text.slice(0, 200)}`);
            }

            const data = await response.json();
            removeLoadingIndicator();

            // message 또는 answer 필드 체크 (팔로우업 에이전트 호환성)
            const responseMessage = data.message || data.answer;
            const responseProducts = data.products || data.related_products;
            
            if (responseMessage) {
                addMessage(responseMessage, "bot");
                if (responseProducts && responseProducts.length > 0) {
                    addRecommendations(responseProducts, data.recommendation_id);
                }
            } else {
                addMessage("죄송합니다. 오류가 발생했습니다. 다시 시도해주세요.", "bot");
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
            addMessage("네트워크 오류가 발생했습니다. 다시 시도해주세요.", "bot");
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
        let recommendationsHTML = '<div style="display: flex; flex-direction: column; gap: 6px;">';
        
        // recommendationId가 배열인지 확인하고 적절히 처리
        let recommendationIds = [];
        if (Array.isArray(recommendationId)) {
            recommendationIds = recommendationId;
        } else if (recommendationId) {
            recommendationIds = [recommendationId];
        }
        
        recommendations.forEach((product, index) => {
            // Safely access properties with fallbacks for robustness
            const imageUrl = product.사진 || product.image_url || 'https://via.placeholder.com/150?text=No+Image';
            const brandName = product.한글브랜드명 || product.brand_name || '브랜드 정보 없음';
            const productName = product.상품명 || product.product_name || '상품명 정보 없음';
            const price = product.가격 ? product.가격.toLocaleString() + '원' : '가격 정보 없음';
            const altText = productName === '상품명 정보 없음' ? '추천 상품' : productName;

            const productId = product.상품코드 || product.product_id || product.itemid || 'unknown';
            const productLink = product.상품링크 || product.product_link || product.URL || '';
            const hasLink = productLink && productLink.trim() !== '';
            
            // 현재 상품에 해당하는 recommendation_id 찾기
            const currentRecommendationId = recommendationIds[index] || product.recommendation_id || '';
            
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
                            ">${brandName}</p>
                            <p style="
                                margin: 0; 
                                font-size: 0.95rem; 
                                color: #e74c3c; 
                                font-weight: 700;
                                font-family: 'Arial', sans-serif;
                            ">${price}</p>
                        </div>
                        
                        <!-- 피드백 버튼들 -->
                        <div class="feedback-buttons">
                            <button class="feedback-like-btn" 
                                    onclick="submitQuickFeedback('${productId}', '${productName}', 1, '${currentRecommendationId}')"
                                    data-recommendation-id="${currentRecommendationId}">
                                👍 좋아요
                            </button>
                            <button class="feedback-dislike-btn" 
                                    onclick="submitQuickFeedback('${productId}', '${productName}', 0, '${currentRecommendationId}')"
                                    data-recommendation-id="${currentRecommendationId}">
                                👎 싫어요
                            </button>
                            <button class="feedback-comment-btn" 
                                    onclick="showCommentModal('${productId}', '${productName}', '${currentRecommendationId}')"
                                    data-recommendation-id="${currentRecommendationId}">
                                💬 코멘트
                            </button>
                        </div>
                        
                        <!-- 액션 버튼들 -->
                        <div style="display: flex; gap: 6px; margin-top: 8px;">
                            <button class="chatbot-jjim-btn" 
                            onclick="addToJjim('${productId}', '${productName}', '${brandName}', '${imageUrl}', '${price}', '${productLink}', '${currentRecommendationId}')"
                            data-product-id="${productId}"
                            data-recommendation-id="${currentRecommendationId}">
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
                </div>`;
        });

        recommendationsHTML += '</div>';
        recommendationsContent.innerHTML = recommendationsHTML;
        recommendationsWrapper.appendChild(recommendationsContent);
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

    async function loadPreviousMessages() {
        if (!currentSessionId || !isValidUUID(currentSessionId)) return;
        try {
            const response = await fetch(`/chat/session/${currentSessionId}/messages`);
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

    async function addToJjim(productId, productName, brand, imageUrl, price, productLink, recommendationId) {
        try {
            const response = await fetch('/jjim/add', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                credentials: 'same-origin',
                body: new URLSearchParams({ 'product_id': productId })
            });

            const result = await response.json();

            if (result.success) {
                const jjimBtn = document.querySelector(`[data-product-id="${productId}"]`);
                if (jjimBtn) {
                    jjimBtn.innerHTML = '❌ 찜해제';
                    jjimBtn.classList.add('jjim-active');
                    jjimBtn.onclick = () => removeFromJjim(productId, productName, brand, imageUrl, price, productLink, recommendationId);
                }
                showFeedbackMessage('찜목록에 추가되었습니다! 💕', 'success');
            } else {
                showFeedbackMessage(result.message || '찜하기에 실패했습니다.', 'error');
            }
        } catch (error) {
            console.error('찜하기 오류:', error);
            showFeedbackMessage('찜하기 중 오류가 발생했습니다.', 'error');
        }
    }

    async function removeFromJjim(productId, productName, brand, imageUrl, price, productLink, recommendationId) {
        if (!productId || productId === 'undefined' || productId === 'null') {
            showFeedbackMessage('상품코드를 찾을 수 없습니다.', 'error');
            return;
        }
        
        try {
            const response = await fetch('/jjim/remove', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                credentials: 'same-origin',
                body: new URLSearchParams({ 'product_id': productId })
            });

            const result = await response.json();

            if (result.success) {
                const jjimBtn = document.querySelector(`[data-product-id="${productId}"]`);
                if (jjimBtn) {
                    jjimBtn.innerHTML = '❤️ 찜하기';
                    jjimBtn.classList.remove('jjim-active');
                    jjimBtn.onclick = () => addToJjim(productId, productName, brand, imageUrl, price, productLink, recommendationId);
                }
                showFeedbackMessage('찜목록에서 제거되었습니다! 💔', 'success');
            } else {
                showFeedbackMessage(result.message || '찜목록에서 제거하는데 실패했습니다.', 'error');
            }
        } catch (error) {
            console.error('찜목록 제거 오류:', error);
            showFeedbackMessage('찜목록에서 제거하는 중 오류가 발생했습니다.', 'error');
        }
    }

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
        if (!recommendationId || recommendationId === '' || recommendationId === 'undefined') {
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
            
            const response = await fetch('/chat/feedback', {
                method: 'POST',
                body: formData,
                credentials: 'same-origin'
            });
            
            const result = await response.json();
            
            if (result.success) {
                let message;
                if (result.already_feedback) {
                    message = '이미 피드백을 제공하셨습니다! 👍';
                } else {
                    if (result.feedback_type === 'comment') {
                        message = '코멘트가 성공적으로 저장되었습니다! 💝';
                    } else {
                        message = rating === 1 ? '좋아요! 감사합니다! 👍' : '피드백 감사합니다! 👎';
                    }
                }
                
                showFeedbackMessage(message, 'success');
                
                // 성공 시 버튼별로 다른 완료 표시
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
    
    async function sendImageToAPI(file) {
        try {
            const formData = new FormData();
            formData.append('image', file);

            const response = await fetch('/chat/image-recommend', {
                method: 'POST',
                body: formData
            });
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
            console.error('Error sending image:', error);
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
    window.addToJjim = addToJjim;
    window.removeFromJjim = removeFromJjim;
    window.submitQuickFeedback = submitQuickFeedback;
    window.showCommentModal = showCommentModal;
});
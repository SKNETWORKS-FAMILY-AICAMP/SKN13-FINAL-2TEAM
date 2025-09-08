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
        previewContainer.id = 'widget-attachment-preview';
        // Store the URL in a data attribute for later revocation
        previewContainer.innerHTML = `
            <div class="attachment-item">
                <img src="${previewURL}" alt="Attachment Preview" data-url="${previewURL}">
                <button class="remove-attachment-btn">&times;</button>
            </div>
        `;
        
        // Robust insertion: Insert before the parent of the input field.
        if (widgetInput.parentNode) {
            widgetInput.parentNode.insertBefore(previewContainer, widgetInput);
        } else {
            widgetForm.appendChild(previewContainer);
        }

        previewContainer.querySelector('.remove-attachment-btn').addEventListener('click', removeAttachment);
    }

    function removeAttachment() {
        const existingPreview = document.getElementById('widget-attachment-preview');
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
            addMessage(`<img src="${previewURL}" class="message-image-preview" alt="Sent Image">`, "user");
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
                const text = await response.text();
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
            // Safely access properties with fallbacks for robustness
            const imageUrl = product.사진 || product.image_url || 'https://via.placeholder.com/150?text=No+Image';
            const brandName = product.한글브랜드명 || product.brand_name || '브랜드 정보 없음';
            const productName = product.상품명 || product.product_name || '상품명 정보 없음';
            const price = product.가격 ? product.가격.toLocaleString() + '원' : '가격 정보 없음';
            const altText = productName === '상품명 정보 없음' ? '추천 상품' : productName;

            recommendationsHTML += `
                <div class="product-card">
                    <img src="${imageUrl}" alt="${altText}" class="recommendation-img" onerror="this.onerror=null;this.src='https://via.placeholder.com/150?text=Error';">
                    <div class="product-info">
                        <div class="product-brand">${brandName}</div>
                        <div class="product-name">${productName}</div>
                        <div class="product-price">${price}</div>
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

    async function submitQuickFeedback(event, productId, productName, rating, recommendationId) {
        if (!recommendationId) {
            showFeedbackMessage('추천 ID를 찾을 수 없습니다.', 'error');
            return;
        }
        
        const button = event.target;
        if (button.disabled) return;
        
        try {
            button.disabled = true;
            const productCard = button.closest('.chatbot-product-card');
            if (productCard) {
                productCard.querySelectorAll('.feedback-like-btn, .feedback-dislike-btn').forEach(btn => {
                    btn.disabled = true;
                });
            }
            
            const formData = new FormData();
            formData.append('recommendation_id', recommendationId);
            formData.append('feedback_rating', rating);
            formData.append('feedback_reason', '');
            
            const response = await fetch('/chat/feedback', {
                method: 'POST',
                body: formData,
                credentials: 'same-origin'
            });
            
            const result = await response.json();
            
            if (result.success) {
                showFeedbackMessage(rating === 1 ? '좋아요! 감사합니다! 👍' : '피드백 감사합니다! 👎', 'success');
                button.innerHTML = rating === 1 ? '👍 완료' : '👎 완료';
                button.classList.add('feedback-completed');
            } else {
                showFeedbackMessage(`피드백 저장 실패: ${result.message}`, 'error');
                button.disabled = false;
                if (productCard) {
                     productCard.querySelectorAll('.feedback-like-btn, .feedback-dislike-btn').forEach(btn => {
                        btn.disabled = false;
                    });
                }
            }
        } catch (error) {
            showFeedbackMessage('피드백 전송 중 오류 발생.', 'error');
             button.disabled = false;
             const productCard = button.closest('.chatbot-product-card');
             if (productCard) {
                 productCard.querySelectorAll('.feedback-like-btn, .feedback-dislike-btn').forEach(btn => {
                    btn.disabled = false;
                });
            }
        }
    }
    
    function showCommentModal(productId, productName, recommendationId) {
        if (!recommendationId) {
            showFeedbackMessage('추천 ID를 찾을 수 없습니다.', 'error');
            return;
        }
        
        const modal = document.createElement('div');
        modal.className = 'comment-modal';
        modal.innerHTML = `
            <div class="comment-content">
                <h3>💬 상품추천이 마음에 드셨나요?</h3>
                <textarea id="comment-text" placeholder="추천에 대한 의견을 자유롭게 작성해주세요..."></textarea>
                <div class="comment-buttons">
                    <button id="submit-comment">코멘트 제출</button>
                    <button id="cancel-comment">취소</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        modal.querySelector('#submit-comment').addEventListener('click', async () => {
            const comment = modal.querySelector('#comment-text').value.trim();
            if (!comment) {
                alert('코멘트를 입력해주세요.');
                return;
            }
            
            const submitBtn = modal.querySelector('#submit-comment');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '제출 중...';
            
            try {
                const formData = new FormData();
                formData.append('recommendation_id', recommendationId);
                formData.append('feedback_rating', 1);
                formData.append('feedback_reason', comment);
                
                const response = await fetch('/chat/feedback', {
                    method: 'POST',
                    body: formData,
                    credentials: 'same-origin'
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showFeedbackMessage('코멘트가 성공적으로 저장되었습니다! 💝', 'success');
                    document.body.removeChild(modal);
                } else {
                    showFeedbackMessage(`코멘트 저장 실패: ${result.message}`, 'error');
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '코멘트 제출';
                }
            } catch (error) {
                showFeedbackMessage('코멘트 전송 중 오류 발생.', 'error');
                submitBtn.disabled = false;
                submitBtn.innerHTML = '코멘트 제출';
            }
        });
        
        modal.querySelector('#cancel-comment').addEventListener('click', () => {
            document.body.removeChild(modal);
        });
        
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

    window.addToJjim = addToJjim;
    window.removeFromJjim = removeFromJjim;
    window.submitQuickFeedback = submitQuickFeedback;
    window.showCommentModal = showCommentModal;
});
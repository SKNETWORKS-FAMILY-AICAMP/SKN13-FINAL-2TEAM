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
});
document.addEventListener("DOMContentLoaded", () => {
    // 플로팅 위젯 요소들
    const floatingWidget = document.getElementById("floating-chatbot-widget");
    const toggleBtn = document.getElementById("chatbot-toggle-btn");
    const closeBtn = document.getElementById("widget-close-btn");
    const widgetMessages = document.getElementById("widget-messages");
    const widgetForm = document.getElementById("widget-form");
    const widgetInput = document.getElementById("widget-input");

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

        // 초기 환영 메시지
        setTimeout(() => {
            addMessage("안녕하세요! 의류 추천 챗봇입니다. 어떤 스타일을 찾으시나요? 😊", "bot");
        }, 500);
    }

    async function sendMessageToAPI(message) {
        try {
            const formData = new FormData();
            formData.append('user_input', message);

            const response = await fetch('/chat', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            removeLoadingIndicator();

            // 응답 구조 변경
            if (data.message && data.products) {
                addMessage(data.message, "bot");
                
                if (data.products && data.products.length > 0) {
                    addRecommendations(data.products);
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
        messageContent.textContent = message;
        messageWrapper.appendChild(messageContent);
        
        widgetMessages.appendChild(messageWrapper);
        widgetMessages.scrollTop = widgetMessages.scrollHeight;
    }

    function addRecommendations(recommendations) {
        const recommendationsWrapper = document.createElement("div");
        recommendationsWrapper.classList.add("widget-message", "widget-bot-message");
        
        const recommendationsContent = document.createElement("div");
        recommendationsContent.classList.add("widget-message-content");
        
        let recommendationsHTML = '<div style="display: flex; flex-direction: column; gap: 10px;">';
        recommendations.forEach((product, index) => {
            recommendationsHTML += `
                <div style="display: flex; gap: 10px; background: #f8f9fa; padding: 10px; border-radius: 8px; border: 1px solid #e9ecef;">
                    ${product.사진 && product.사진.trim() !== '' ? 
                        `<img src="${product.사진}" alt="${product.상품명}" 
                             style="width: 60px; height: 60px; object-fit: cover; border-radius: 4px;" 
                             onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                         <div style="width: 60px; height: 60px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 4px; display: none; align-items: center; justify-content: center; color: white; font-size: 24px;">👕</div>`
                        :
                        `<div style="width: 60px; height: 60px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 4px; display: flex; align-items: center; justify-content: center; color: white; font-size: 24px;">👕</div>`
                    }
                    <div style="flex: 1; min-width: 0;">
                        <h4 style="margin: 0 0 5px 0; font-size: 0.9rem; color: #2c3e50; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${product.상품명}</h4>
                        <p style="margin: 0 0 3px 0; font-size: 0.8rem; color: #E50914; font-weight: 600;">${product.브랜드}</p>
                        <p style="margin: 0; font-size: 0.8rem; color: #e74c3c; font-weight: 700;">${product.가격 ? product.가격.toLocaleString() + '원' : '가격 정보 없음'}</p>
                    </div>
                </div>
            `;
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
});
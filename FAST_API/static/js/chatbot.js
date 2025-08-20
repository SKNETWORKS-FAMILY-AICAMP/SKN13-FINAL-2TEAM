document.addEventListener("DOMContentLoaded", () => {
    // 플로팅 위젯 요소들
    const floatingWidget = document.getElementById("floating-chatbot-widget");
    const toggleBtn = document.getElementById("chatbot-toggle-btn");
    const closeBtn = document.getElementById("widget-close-btn");
    const widgetMessages = document.getElementById("widget-messages");
    const widgetForm = document.getElementById("widget-form");
    const widgetInput = document.getElementById("widget-input");

    // 세션 관리 변수들
    let currentSessionId = null;
    let currentSessionName = null;
    let sessions = [];

    // 플로팅 위젯 초기화
    if (floatingWidget && toggleBtn && closeBtn) {
        initializeFloatingWidget();
    }

    function initializeFloatingWidget() {
        // 위젯 헤더에 세션 관리 버튼 추가
        addSessionManagementUI();

        // 토글 버튼 클릭 이벤트
        toggleBtn.addEventListener("click", () => {
            floatingWidget.classList.add("active");
            toggleBtn.classList.add("hidden");
            widgetInput.focus();
            
            // 세션 목록 로드
            loadSessions();
        });

        // 닫기 버튼 클릭 이벤트
        closeBtn.addEventListener("click", () => {
            floatingWidget.classList.remove("active");
            toggleBtn.classList.remove("hidden");
            closeSessionSidebar();
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

    function addSessionManagementUI() {
        const widgetHeader = document.querySelector(".widget-header");
        if (widgetHeader) {
            // 세션 관리 버튼 추가
            const sessionBtn = document.createElement("button");
            sessionBtn.className = "widget-session-btn";
            sessionBtn.innerHTML = "📋 대화 내역";
            sessionBtn.title = "세션 관리";
            sessionBtn.addEventListener("click", toggleSessionSidebar);
            
            // 헤더에 버튼 삽입 (닫기 버튼 앞에)
            widgetHeader.insertBefore(sessionBtn, closeBtn);

            // 세션 사이드바 추가
            addSessionSidebar();
        }
    }

    function addSessionSidebar() {
        const sidebarHTML = `
            <div class="widget-session-sidebar" id="session-sidebar">
                <div class="session-sidebar-header">
                    <h4>대화 세션</h4>
                    <button class="session-sidebar-close" id="session-sidebar-close">×</button>
                </div>
                <button class="new-session-btn" id="new-session-btn">🚀 새 대화 시작</button>
                <div class="session-list" id="session-list">
                    <!-- 세션 목록이 여기에 동적으로 추가됩니다 -->
                </div>
            </div>
        `;
        
        floatingWidget.insertAdjacentHTML('beforeend', sidebarHTML);

        // 사이드바 이벤트 리스너
        document.getElementById("session-sidebar-close").addEventListener("click", closeSessionSidebar);
        document.getElementById("new-session-btn").addEventListener("click", createNewSession);
    }

    function toggleSessionSidebar() {
        const sidebar = document.getElementById("session-sidebar");
        sidebar.classList.toggle("active");
        
        if (sidebar.classList.contains("active")) {
            loadSessions();
        }
    }

    function closeSessionSidebar() {
        const sidebar = document.getElementById("session-sidebar");
        sidebar.classList.remove("active");
    }

    async function loadSessions() {
        try {
            const response = await fetch('/chat/sessions');
            const data = await response.json();
            
            if (data.success && data.sessions) {
                sessions = data.sessions;
                renderSessionList();
            }
        } catch (error) {
            console.error('세션 목록 로드 오류:', error);
        }
    }

    function renderSessionList() {
        const sessionList = document.getElementById("session-list");
        if (!sessionList) return;

        sessionList.innerHTML = '';

        if (sessions.length === 0) {
            sessionList.innerHTML = '<div style="text-align: center; color: #6c757d; padding: 20px;">대화 세션이 없습니다.</div>';
            return;
        }

        sessions.forEach(session => {
            const sessionItem = createSessionItem(session);
            sessionList.appendChild(sessionItem);
        });
    }

    function createSessionItem(session) {
        const sessionItem = document.createElement("div");
        sessionItem.className = "session-item";
        sessionItem.setAttribute("data-session-id", session.id);
        
        if (session.id === currentSessionId) {
            sessionItem.classList.add("active");
        }

        const createdDate = new Date(session.created_at);
        
        // 세션 이름을 더 직관적으로 표시
        let displayName = session.name;
        if (displayName.startsWith("대화 ")) {
            displayName = displayName.replace("대화 ", "");
            if (displayName.length > 20) {
                displayName = displayName.substring(0, 20) + "...";
            }
        }
        
        // 메시지 수에 따른 아이콘 선택
        let messageIcon = "💬";
        if (session.message_count > 10) {
            messageIcon = "🔥";
        } else if (session.message_count > 5) {
            messageIcon = "✨";
        }
        
        sessionItem.innerHTML = `
            <div class="session-item-header">
                <div class="session-name" data-session-id="${session.id}">
                    <span class="session-icon">${messageIcon}</span>
                    <span class="session-title">${displayName}</span>
                </div>
                <div class="session-actions">
                    <button class="session-action-btn edit-btn" title="이름 편집">✏️</button>
                    <button class="session-action-btn delete-btn" title="삭제">🗑️</button>
                </div>
            </div>
            <div class="session-info">
                <span class="session-date">${formatDate(createdDate)}</span>
                <span class="session-message-count">${session.message_count}개 메시지</span>
            </div>
            <input type="text" class="session-name-edit" value="${session.name}" data-session-id="${session.id}">
        `;

        // 세션 클릭 이벤트
        sessionItem.addEventListener("click", (e) => {
            if (!e.target.classList.contains('session-action-btn') && !e.target.classList.contains('session-name-edit')) {
                switchToSession(session.id);
            }
        });

        // 편집 버튼 이벤트
        const editBtn = sessionItem.querySelector('.edit-btn');
        editBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            toggleSessionNameEdit(session.id);
        });

        // 삭제 버튼 이벤트
        const deleteBtn = sessionItem.querySelector('.delete-btn');
        deleteBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            deleteSession(session.id);
        });

        // 이름 편집 이벤트
        const nameEdit = sessionItem.querySelector('.session-name-edit');
        nameEdit.addEventListener("blur", () => {
            saveSessionName(session.id, nameEdit.value);
        });
        nameEdit.addEventListener("keypress", (e) => {
            if (e.key === "Enter") {
                nameEdit.blur();
            }
        });

        return sessionItem;
    }

    function formatDate(date) {
        const now = new Date();
        const diffTime = Math.abs(now - date);
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        
        if (diffDays === 1) {
            return "오늘";
        } else if (diffDays === 2) {
            return "어제";
        } else if (diffDays <= 7) {
            return `${diffDays - 1}일 전`;
        } else {
            return date.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' });
        }
    }

    function toggleSessionNameEdit(sessionId) {
        const sessionItem = document.querySelector(`[data-session-id="${sessionId}"]`).closest('.session-item');
        const nameElement = sessionItem.querySelector('.session-name');
        const nameEdit = sessionItem.querySelector('.session-name-edit');
        
        nameElement.style.display = 'none';
        nameEdit.classList.add('active');
        nameEdit.focus();
        nameEdit.select();
    }

    async function saveSessionName(sessionId, newName) {
        try {
            const formData = new FormData();
            formData.append('new_name', newName);

            const response = await fetch(`/chat/session/${sessionId}/name`, {
                method: 'PUT',
                body: formData
            });

            const data = await response.json();
            
            if (data.success) {
                // 세션 목록 새로고침
                loadSessions();
                
                // 현재 세션이면 이름 업데이트
                if (sessionId === currentSessionId) {
                    currentSessionName = newName;
                    updateSessionNameDisplay();
                }
            }
        } catch (error) {
            console.error('세션 이름 저장 오류:', error);
        }
    }

    async function deleteSession(sessionId) {
        if (!confirm('이 대화 세션을 삭제하시겠습니까?')) {
            return;
        }

        try {
            const response = await fetch(`/chat/session/${sessionId}`, {
                method: 'DELETE'
            });

            const data = await response.json();
            
            if (data.success) {
                // 현재 세션이 삭제된 경우 새 세션으로 전환
                if (sessionId === currentSessionId) {
                    currentSessionId = null;
                    currentSessionName = null;
                    clearMessages();
                    addMessage("새로운 대화를 시작합니다. 무엇을 도와드릴까요? 😊", "bot");
                }
                
                // 세션 목록 새로고침
                loadSessions();
            }
        } catch (error) {
            console.error('세션 삭제 오류:', error);
        }
    }

    async function switchToSession(sessionId) {
        try {
            console.log('세션 전환 시도:', sessionId);
            
            const response = await fetch(`/chat/session/${sessionId}`);
            const data = await response.json();
            
            console.log('세션 메시지 응답:', data);
            
            if (data.success) {
                currentSessionId = sessionId;
                const session = sessions.find(s => s.id === sessionId);
                currentSessionName = session ? session.name : null;
                
                // 메시지 목록 새로고침
                clearMessages();
                
                if (data.messages && data.messages.length > 0) {
                    console.log('로드된 메시지 수:', data.messages.length);
                    data.messages.forEach(msg => {
                        console.log('메시지 추가:', msg.type, msg.text);
                        addMessage(msg.text, msg.type);
                    });
                } else {
                    console.log('메시지가 없음, 환영 메시지 추가');
                    addMessage("이 대화 세션을 시작합니다. 무엇을 도와드릴까요? 😊", "bot");
                }
                
                // 세션 목록 UI 업데이트
                updateSessionListUI();
                updateSessionNameDisplay();
                
                // 사이드바 닫기
                closeSessionSidebar();
            } else {
                console.error('세션 메시지 로드 실패:', data.message);
            }
        } catch (error) {
            console.error('세션 전환 오류:', error);
        }
    }

    function createNewSession() {
        currentSessionId = null;
        currentSessionName = null;
        clearMessages();
        addMessage("새로운 대화를 시작합니다. 무엇을 도와드릴까요? 😊", "bot");
        closeSessionSidebar();
    }

    function clearMessages() {
        widgetMessages.innerHTML = '';
    }

    function updateSessionListUI() {
        // 모든 세션 아이템에서 active 클래스 제거
        document.querySelectorAll('.session-item').forEach(item => {
            item.classList.remove('active');
        });
        
        // 현재 세션에 active 클래스 추가
        if (currentSessionId) {
            const currentItem = document.querySelector(`[data-session-id="${currentSessionId}"]`);
            if (currentItem) {
                currentItem.closest('.session-item').classList.add('active');
            }
        }
    }

    function updateSessionNameDisplay() {
        // 헤더에 현재 세션 이름 표시 (선택사항)
        const header = document.querySelector('.widget-header h3');
        if (header && currentSessionName) {
            header.textContent = currentSessionName;
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
            if (currentSessionId) {
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
                    currentSessionName = data.session_name;
                    updateSessionNameDisplay();
                    loadSessions();
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
        
        let recommendationsHTML = '<div style="display: flex; flex-direction: column; gap: 10px;">';
        recommendations.forEach((product, index) => {
            const productName = product.상품명 || product.제품이름 || '상품명 없음';
            const brand = product.한글브랜드명 || product.브랜드 || '브랜드 없음';
            const imageUrl = product.이미지URL || product.사진 || product.대표이미지URL || '';
                         // 원가 우선 사용
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
                <div class="product-card" data-product-index="${index}" style="display: flex; gap: 10px; background: #f8f9fa; padding: 10px; border-radius: 8px; border: 1px solid #e9ecef; ${hasLink ? 'cursor: pointer;' : 'cursor: default;'} transition: all 0.3s ease;" 
                     onmouseover="${hasLink ? 'this.style.transform=\'translateY(-2px)\'; this.style.boxShadow=\'0 4px 12px rgba(0,0,0,0.15)\'' : ''}"
                     onmouseout="${hasLink ? 'this.style.transform=\'translateY(0)\'; this.style.boxShadow=\'none\'' : ''}">
                    ${imageUrl && imageUrl.trim() !== '' ? 
                        `<img src="${imageUrl}" alt="${productName}" 
                             style="width: 60px; height: 60px; object-fit: cover; border-radius: 4px;" 
                             onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                         <div style="width: 60px; height: 60px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 4px; display: none; align-items: center; justify-content: center; color: white; font-size: 24px;">👕</div>`
                        :
                        `<div style="width: 60px; height: 60px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 4px; display: flex; align-items: center; justify-content: center; color: white; font-size: 24px;">👕</div>`
                    }
                    <div style="flex: 1; min-width: 0;">
                        <h4 style="margin: 0 0 5px 0; font-size: 0.9rem; color: #2c3e50; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${productName}</h4>
                        <p style="margin: 0 0 3px 0; font-size: 0.8rem; color: #E50914; font-weight: 600;">${brand}</p>
                        <p style="margin: 0; font-size: 0.8rem; color: #e74c3c; font-weight: 700;">${price ? price.toLocaleString() + '원' : '가격 정보 없음'}</p>
                    </div>
                    <div style="display: flex; align-items: center; color: #6c757d; font-size: 12px;">
                        <span>${hasLink ? '클릭하여 상품 보기 →' : '상품 정보'}</span>
                    </div>
                </div>
            `;
        });
        recommendationsHTML += '</div>';
        
        recommendationsContent.innerHTML = recommendationsHTML;
        recommendationsWrapper.appendChild(recommendationsContent);
        
        // 상품 카드에 클릭 이벤트 추가
        const productCards = recommendationsWrapper.querySelectorAll('.product-card');
        productCards.forEach((card, index) => {
            const product = recommendations[index];
            const productLink = product.상품링크 || product.링크 || product.URL || '';
            const productName = product.상품명 || product.제품이름 || '상품명 없음';
            
            if (productLink && productLink.trim() !== '') {
                card.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('상품 카드 클릭됨:', productName, productLink);
                    openProductLink(productLink, productName);
                });
            }
        });
        
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
});
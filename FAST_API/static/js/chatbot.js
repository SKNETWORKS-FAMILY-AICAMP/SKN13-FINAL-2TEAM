document.addEventListener("DOMContentLoaded", () => {
    const chatBox = document.getElementById("chat-box");
    const userInput = document.getElementById("user-input");
    const sendBtn = document.getElementById("send-btn");

    sendBtn.addEventListener("click", () => {
        const message = userInput.value.trim();
        if (message) {
            addMessage(message, "user");
            userInput.value = "";
            showLoadingIndicator();
            // Simulate a bot response
            setTimeout(() => {
                removeLoadingIndicator();
                addMessage("I am a bot.", "bot");
            }, 1500);
        }
    });

    userInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
            sendBtn.click();
        }
    });

    function addMessage(message, sender) {
        const messageWrapper = document.createElement("div");
        messageWrapper.classList.add("chat-message-wrapper", `${sender}-message-wrapper`);

        const avatar = document.createElement("div");
        avatar.classList.add("chat-avatar");
        avatar.textContent = sender === "user" ? "You" : "Bot";

        const messageElement = document.createElement("div");
        messageElement.classList.add("chat-message", `${sender}-message`);
        messageElement.textContent = message;

        if (sender === "user") {
            messageWrapper.appendChild(messageElement);
            messageWrapper.appendChild(avatar);
        } else {
            messageWrapper.appendChild(avatar);
            messageWrapper.appendChild(messageElement);
        }
        
        chatBox.appendChild(messageWrapper);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function showLoadingIndicator() {
        const loadingWrapper = document.createElement("div");
        loadingWrapper.classList.add("chat-message-wrapper", "bot-message-wrapper", "loading-dots");
        loadingWrapper.id = "loading-indicator";

        const avatar = document.createElement("div");
        avatar.classList.add("chat-avatar");
        avatar.textContent = "Bot";
        loadingWrapper.appendChild(avatar);

        const loadingMessage = document.createElement("div");
        loadingMessage.classList.add("chat-message", "bot-message");
        loadingMessage.innerHTML = `<span class="loading-indicator"></span><span class="loading-indicator"></span><span class="loading-indicator"></span>`;
        loadingWrapper.appendChild(loadingMessage);

        chatBox.appendChild(loadingWrapper);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function removeLoadingIndicator() {
        const loadingIndicator = document.getElementById("loading-indicator");
        if (loadingIndicator) {
            loadingIndicator.remove();
        }
    }
});
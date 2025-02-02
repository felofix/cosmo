// Global click handler for closing popups
document.addEventListener('click', function(e) {
    const citation = e.target.closest('.citation');
    const popup = e.target.closest('.source-popup');

    // If clicking outside both citation and popup, close all popups
    if (!citation && !popup) {
        document.querySelectorAll('.source-popup.show').forEach(p => {
            p.classList.remove('show');
            p.style.display = 'none';
        });
    }
});

async function sendMessage() {
    const messageInput = document.getElementById('message-input');
    const message = messageInput.value.trim();

    if (message === '') return;

    // Add user message to chat
    addMessage(message, true);

    // Clear input
    messageInput.value = '';

    // Add loading message
    const loadingId = addLoadingMessage();

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message })
        });

        // Remove loading message
        removeLoadingMessage(loadingId);

        const data = await response.json();

        if (!data.success) {
            console.error('Error:', data.error);
            addMessage("I apologize, but I encountered an error. Please try again.", false, message);
            return;
        }

        // Add bot response to chat with docs
        addMessage(data.response, false, data.docs || {}, message);

    } catch (error) {
        console.error('Error:', error);
        // Remove loading message
        removeLoadingMessage(loadingId);
        addMessage("I apologize, but I encountered an error. Please try again.", false, message);
    }
}

async function addMessage(content, isUser, docs = {}, message) {
    const chatContainer = document.getElementById('chat-container');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    if (!isUser) {
        // Process text and add citations
        const parts = content.split(/(\[\d+(?:,\d+)*\])/);
        
        // Prepare documents for translation
        const documentsToTranslate = [];
        Object.values(docs).forEach(doc => {
            if (doc && doc.content) {
                documentsToTranslate.push(doc.content);
            }
        });

        // Create a map to store popup content elements for later updates
        const popupContents = new Map();
        
        // Display original content immediately
        for (let i = 0; i < parts.length; i++) {
            const part = parts[i];
            const citationMatch = part.match(/\[(\d+(?:,\d+)*)\]/);
            if (citationMatch) {
                const citations = citationMatch[1].split(',').map(num => num.trim());

                for (const [idx, num] of citations.entries()) {
                    if (idx > 0) {
                        contentDiv.appendChild(document.createTextNode(','));
                    }

                    const span = document.createElement('span');
                    span.className = `citation citation-${num}`;
                    span.textContent = `[${num}]`;

                    const popup = document.createElement('div');
                    popup.className = 'source-popup';

                    const docId = `DOC:${parseInt(num) - 1}`;
                    const doc = docs[docId];
                    if (doc) {
                        const sourceContent = document.createElement('div');
                        sourceContent.className = 'source-content';
                        // Handle newlines in document content
                        sourceContent.innerHTML = doc.content.replace(/\n/g, '<br>');
                        popup.appendChild(sourceContent);

                        // Store the content element for later update
                        popupContents.set(parseInt(num) - 1, sourceContent);

                        const link = document.createElement('a');
                        link.href = doc.url;
                        link.className = 'source-link';
                        link.target = '_blank';
                        const displayUrl = doc.url
                            .replace(/^https?:\/\//, '')
                            .replace(/\/$/, '');
                        link.textContent = displayUrl;
                        popup.appendChild(link);
                    }

                    document.body.appendChild(popup);

                    span.addEventListener('click', function(e) {
                        e.stopPropagation();

                        document.querySelectorAll('.source-popup.show').forEach(p => {
                            if (p !== popup) {
                                p.classList.remove('show');
                                p.style.display = 'none';
                            }
                        });

                        if (popup.classList.contains('show')) {
                            popup.classList.remove('show');
                            popup.style.display = 'none';
                            return;
                        }

                        const rect = span.getBoundingClientRect();
                        const windowWidth = window.innerWidth;
                        const windowHeight = window.innerHeight;

                        let left = rect.left;
                        let top = rect.bottom + 5;

                        popup.style.display = 'block';
                        const popupRect = popup.getBoundingClientRect();

                        if (left + popupRect.width > windowWidth - 20) {
                            left = windowWidth - popupRect.width - 20;
                        }

                        if (top + popupRect.height > windowHeight - 20) {
                            top = rect.top - popupRect.height - 5;
                        }

                        popup.style.left = `${left}px`;
                        popup.style.top = `${top}px`;
                        popup.classList.add('show');
                    });

                    contentDiv.appendChild(span);
                }
            } else {
                // Handle newlines in regular text
                const textParts = part.split('\n');
                textParts.forEach((textPart, index) => {
                    if (index > 0) {
                        contentDiv.appendChild(document.createElement('br'));
                    }
                    contentDiv.appendChild(document.createTextNode(textPart));
                });
            }
        }

        // Append the message to chat container immediately
        messageDiv.appendChild(contentDiv);
        chatContainer.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;

        // Start document translations asynchronously
        if (documentsToTranslate.length > 0) {
            fetch('/api/translate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    question: message,
                    documents: documentsToTranslate
                })
            })
            .then(response => response.json())
            .then(translationResponse => {
                if (translationResponse.translations) {
                    translationResponse.translations.forEach((translatedDoc, index) => {
                        const contentElement = popupContents.get(index);
                        if (contentElement) {
                            // Handle newlines in translated content
                            contentElement.innerHTML = translatedDoc.translation.replace(/\n/g, '<br>');
                        }
                    });
                }
            })
            .catch(error => {
                console.error('Translation error:', error);
            });
        }
    } else {
        // Handle newlines in user messages
        const textParts = content.split('\n');
        textParts.forEach((textPart, index) => {
            if (index > 0) {
                contentDiv.appendChild(document.createElement('br'));
            }
            contentDiv.appendChild(document.createTextNode(textPart));
        });
        messageDiv.appendChild(contentDiv);
        chatContainer.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    document.addEventListener('click', function(e) {
        if (!e.target.closest('.citation')) {
            document.querySelectorAll('.source-popup.show').forEach(popup => {
                popup.classList.remove('show');
                popup.style.display = 'none';
            });
        }
    });
}

function addLoadingMessage() {
    const chatContainer = document.getElementById('chat-container');
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message bot-message loading';
    loadingDiv.textContent = 'Thinking';
    chatContainer.appendChild(loadingDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function removeLoadingMessage() {
    const chatContainer = document.getElementById('chat-container');
    const loadingMessage = chatContainer.querySelector('.loading');
    if (loadingMessage) {
        loadingMessage.remove();
    }
}

// Add event listeners
document.getElementById('message-input').addEventListener('keypress', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

document.getElementById('send-button').addEventListener('click', sendMessage);

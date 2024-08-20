document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const tokenBalance = document.getElementById('token-balance');
    const tabContainer = document.getElementById('tab-container');
    let currentTabId = localStorage.getItem('currentTabId');

    console.log('DOM loaded. Current Tab ID from localStorage:', currentTabId);

    const buttonContainer = document.createElement('div');
    buttonContainer.classList.add('button-container');
    
    const exitButton = document.createElement('button');
    exitButton.textContent = 'Logout';
    exitButton.classList.add('logout-btn');
    exitButton.addEventListener('click', () => {
        window.location.href = '/';
    });

    const clearButton = document.createElement('button');
    clearButton.textContent = 'Clear context';
    clearButton.classList.add('clear-btn');
    clearButton.addEventListener('click', async () => {
        if (currentTabId) {
            try {
                const response = await fetch(`/clear_context/${currentTabId}`, {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                });
                if (response.ok) {
                    document.getElementById(`chat-messages-${currentTabId}`).innerHTML = '';
                } else {
                    console.error('Error clearing context');
                }
            } catch (error) {
                console.error('Error:', error);
            }
        }
    });

    const newTabButton = document.createElement('button');
    newTabButton.textContent = 'New Tab';
    newTabButton.classList.add('chat-btn');
    newTabButton.addEventListener('click', createNewTab);

    buttonContainer.appendChild(exitButton);
    buttonContainer.appendChild(clearButton);
    buttonContainer.appendChild(newTabButton);


    chatForm.after(buttonContainer);

    document.querySelectorAll('.tab-btn').forEach(tabButton => {
        if (!tabButton.querySelector('.edit-icon')) {
            const editIcon = document.createElement('span');
            editIcon.innerHTML = '&#9998;';
            editIcon.classList.add('edit-icon');
            tabButton.appendChild(editIcon);
        }

        if (!tabButton.querySelector('.delete-icon')) {
            const deleteIcon = document.createElement('span');
            deleteIcon.innerHTML = '&#128465;';
            deleteIcon.classList.add('delete-icon');
            tabButton.appendChild(deleteIcon);
        }
    });

    if (currentTabId && document.querySelector(`button[data-tab-id="${currentTabId}"]`)) {
        console.log('Switching to saved tab with ID:', currentTabId);
        switchTab(currentTabId);
    } else if (tabContainer.firstElementChild) {
        console.log('Switching to the first tab with ID:', tabContainer.firstElementChild.dataset.tabId);
        switchTab(tabContainer.firstElementChild.dataset.tabId);
    } else {
        console.log('No tabs.');
        hideAllTabs();
    }

    tabContainer.addEventListener('click', (e) => {
        if (e.target && e.target.closest('button.tab-btn')) {
            const tabButton = e.target.closest('button.tab-btn');
            if (!e.target.matches('.edit-icon') && !e.target.matches('.delete-icon')) {
                switchTab(tabButton.dataset.tabId);
            } else if (e.target.matches('.delete-icon')) {
                const tabId = tabButton.dataset.tabId;
                deleteTab(tabId);
            } else if (e.target.matches('.edit-icon')) {
                startEditingTabName(tabButton);
            }
        }
    });

    function startEditingTabName(tabButton) {
        const tabNameSpan = tabButton.querySelector('.tab-name');
        const tabNameInput = document.createElement('input');
        tabNameInput.type = 'text';
        tabNameInput.value = tabNameSpan.textContent;
        tabNameInput.classList.add('tab-name-edit');

        tabNameSpan.replaceWith(tabNameInput);
        tabButton.classList.add('active');
        tabNameInput.focus();

        tabNameInput.addEventListener('blur', () => {
            saveTabName(tabButton, tabNameInput);
        });

        tabNameInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                tabNameInput.blur();
            }
        });
    }

    function saveTabName(tabButton, tabNameInput) {
        const tabNameSpan = document.createElement('span');
        tabNameSpan.classList.add('tab-name');
        tabNameSpan.textContent = tabNameInput.value;
        tabButton.replaceChild(tabNameSpan, tabNameInput);
        renameTab(tabButton.dataset.tabId, tabNameInput.value);
    }

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = userInput.value.trim();
        if (message && currentTabId) {
            addMessage('user', message);
    
            userInput.value = '';
            userInput.style.height = 'auto';
    
            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ message, tab_id: parseInt(currentTabId, 10) }),
                });
                const data = await response.json();
                if (data.error) {
                    addMessage('error', data.response);
                } else {
                    addMessage('bot', data.response);
                    tokenBalance.textContent = data.tokens_remaining;
                }
            } catch (error) {
                console.error('Error:', error);
                addMessage('error', 'Sorry, an error occurred. Please try again.');
            }
        }
    });

    async function createNewTab() {
        try {
            const response = await fetch('/create_tab', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            const data = await response.json();
            const tabId = data.tab_id;
            const tabName = data.name;
            addTab(tabId, tabName);
            switchTab(tabId);
        } catch (error) {
            console.error('Error:', error);
        }
    }

    async function deleteTab(tabId) {
        try {
            const response = await fetch(`/delete_tab/${tabId}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            if (response.ok) {
                const tabButton = document.querySelector(`button[data-tab-id="${tabId}"]`);
                tabButton.remove();
                document.getElementById(`chat-messages-${tabId}`).remove();

                if (currentTabId === tabId) {
                    localStorage.removeItem('currentTabId');
                    currentTabId = null;
                    hideAllTabs();
                }
            } else {
                console.error('Error deleting tab');
            }
        } catch (error) {
            console.error('Error:', error);
        }
    }

    async function renameTab(tabId, newName) {
        try {
            const response = await fetch(`/rename_tab/${tabId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ new_name: newName })
            });
            if (!response.ok) {
                console.error('Error renaming tab');
            }
        } catch (error) {
            console.error('Error:', error);
        }
    }

    function addTab(tabId, tabName) {
        const tabButton = document.createElement('button');
        tabButton.classList.add('tab-btn');
        tabButton.dataset.tabId = tabId;
    
        const tabNameSpan = document.createElement('span');
        tabNameSpan.classList.add('tab-name');
        tabNameSpan.textContent = tabName;
        tabButton.appendChild(tabNameSpan);

        const editIcon = document.createElement('span');
        editIcon.innerHTML = '&#9998;';
        editIcon.classList.add('edit-icon');
        tabButton.appendChild(editIcon);
    
        const deleteIcon = document.createElement('span');
        deleteIcon.innerHTML = '&#128465;';
        deleteIcon.classList.add('delete-icon');
        tabButton.appendChild(deleteIcon);
    
        tabContainer.appendChild(tabButton);
    
        const chatMessagesContainer = document.createElement('div');
        chatMessagesContainer.id = `chat-messages-${tabId}`;
        chatMessagesContainer.classList.add('chat-messages');
        chatMessagesContainer.style.display = 'none';
        document.querySelector('.chat-container').prepend(chatMessagesContainer);
    }

    async function switchTab(tabId) {
        currentTabId = parseInt(tabId, 10);
        localStorage.setItem('currentTabId', currentTabId);
        hideAllTabs();
    
        const chatMessagesContainer = document.getElementById(`chat-messages-${tabId}`);
        chatMessagesContainer.style.display = 'block';
    
        chatMessagesContainer.innerHTML = '';
    
        try {
            const response = await fetch(`/get_tab_messages/${currentTabId}`);
            const messages = await response.json();
            messages.forEach(msg => {
                const senderClass = msg.sender === 'user' ? 'user' : 'bot';
                addMessageToTab(chatMessagesContainer, senderClass, msg.text);
            });
        } catch (error) {
            console.error('Error:', error);
        }
    }
    

    function hideAllTabs() {
        document.querySelectorAll('.chat-messages').forEach(container => {
            container.style.display = 'none';
        });
    }

    function addMessageToTab(container, sender, text) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', sender);

        const formattedText = formatMessageText(text);

        const textElement = document.createElement('p');
        textElement.innerHTML = formattedText;
        messageElement.appendChild(textElement);
        container.appendChild(messageElement);
        container.scrollTop = container.scrollHeight;
    }

    function addMessage(sender, text) {
        if (currentTabId) {
            const chatMessagesContainer = document.getElementById(`chat-messages-${currentTabId}`);
            addMessageToTab(chatMessagesContainer, sender, text);
        }
    }

    function formatMessageText(text) {
        if (text.includes('```')) {
            return text.replace(/```[\s\S]*?\n([\s\S]*?)\n```/g, '<pre><code>$1</code></pre>');
        }
        return text;
    }


    function saveTabName(tabButton, tabNameInput) {
        const tabNameSpan = document.createElement('span');
        tabNameSpan.classList.add('tab-name');
        tabNameSpan.textContent = tabNameInput.value;

        tabNameInput.replaceWith(tabNameSpan);
        tabButton.classList.remove('active');

        if (tabNameInput.value.length > 0 && tabNameInput.value.length <= 50) {
            renameTab(tabButton.dataset.tabId, tabNameInput.value);
        } else {
            alert('Tab name must be between 1 and 50 characters.');
        }
    }
});

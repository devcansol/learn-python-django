// Powers the floating "Ask AI" chat widget included on every authenticated
// page (see templates/todos/_chat_widget.html). Plain vanilla JS on
// purpose — this project has no build step or JS framework.
(function () {
  var widget = document.getElementById('chat-widget');
  if (!widget) {
    return;
  }

  var toggleButton = document.getElementById('chat-toggle');
  var closeButton = document.getElementById('chat-close');
  var panel = document.getElementById('chat-panel');
  var messagesEl = document.getElementById('chat-messages');
  var form = document.getElementById('chat-form');
  var input = document.getElementById('chat-input');

  var historyLoaded = false;

  function csrfToken() {
    var tokenInput = widget.querySelector('input[name="csrfmiddlewaretoken"]');
    return tokenInput ? tokenInput.value : '';
  }

  function appendMessage(role, text) {
    var bubble = document.createElement('div');
    bubble.className = 'chat-msg chat-msg-' + role;
    bubble.textContent = text;
    messagesEl.appendChild(bubble);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return bubble;
  }

  async function loadHistory() {
    try {
      var response = await fetch('/api/ai/chat/');
      if (!response.ok) {
        return;
      }
      var data = await response.json();
      data.forEach(function (message) {
        appendMessage(message.role, message.content);
      });
    } catch (err) {
      // Silently skip — the widget still works for new messages.
    }
  }

  function openPanel() {
    panel.hidden = false;
    if (!historyLoaded) {
      historyLoaded = true;
      loadHistory();
    }
    input.focus();
  }

  function closePanel() {
    panel.hidden = true;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    var text = input.value.trim();
    if (!text) {
      return;
    }

    appendMessage('user', text);
    input.value = '';
    input.disabled = true;

    try {
      var response = await fetch('/api/ai/chat/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken(),
        },
        body: JSON.stringify({ message: text }),
      });

      var data = await response.json();
      if (!response.ok) {
        appendMessage('error', data.error || 'Something went wrong. Please try again.');
        return;
      }

      appendMessage('assistant', data.content);
    } catch (err) {
      appendMessage('error', 'Could not reach the AI service. Please try again.');
    } finally {
      input.disabled = false;
      input.focus();
    }
  }

  toggleButton.addEventListener('click', function () {
    if (panel.hidden) {
      openPanel();
    } else {
      closePanel();
    }
  });
  closeButton.addEventListener('click', closePanel);
  form.addEventListener('submit', handleSubmit);
})();

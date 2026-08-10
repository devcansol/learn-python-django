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

  var docsList = document.getElementById('chat-docs-list');
  var uploadForm = document.getElementById('chat-upload-form');
  var uploadInput = document.getElementById('chat-upload-input');
  var uploadButton = document.getElementById('chat-upload-btn');
  var uploadStatus = document.getElementById('chat-upload-status');

  var historyLoaded = false;
  var docsLoaded = false;

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

  function appendError(message, retryText) {
    var bubble = document.createElement('div');
    bubble.className = 'chat-msg chat-msg-error';
    var span = document.createElement('span');
    span.textContent = message;
    bubble.appendChild(span);
    var retry = document.createElement('button');
    retry.type = 'button';
    retry.className = 'btn btn-ghost btn-sm chat-retry';
    retry.textContent = 'Retry';
    retry.addEventListener('click', function () {
      bubble.remove();
      sendMessage(retryText);
    });
    bubble.appendChild(retry);
    messagesEl.appendChild(bubble);
    messagesEl.scrollTop = messagesEl.scrollHeight;
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

  function statusLabel(status) {
    if (status === 'completed') return 'Ready';
    if (status === 'failed') return 'Failed';
    if (status === 'processing') return 'Indexing…';
    return 'Pending';
  }

  function renderDocument(doc) {
    var li = document.createElement('li');
    li.className = 'chat-doc chat-doc-' + doc.status;
    li.dataset.docId = doc.id;

    var title = document.createElement('span');
    title.className = 'chat-doc-title';
    title.textContent = doc.title;
    li.appendChild(title);

    var badge = document.createElement('span');
    badge.className = 'chat-doc-badge';
    badge.textContent = statusLabel(doc.status);
    li.appendChild(badge);

    var removeButton = document.createElement('button');
    removeButton.type = 'button';
    removeButton.className = 'chat-doc-remove';
    removeButton.setAttribute('aria-label', 'Delete document');
    removeButton.textContent = '✕';
    removeButton.addEventListener('click', function () {
      deleteDocument(doc.id, li);
    });
    li.appendChild(removeButton);

    docsList.appendChild(li);
    return li;
  }

  async function loadDocuments() {
    try {
      var response = await fetch('/api/documents/');
      if (!response.ok) {
        return;
      }
      var data = await response.json();
      data.forEach(renderDocument);
    } catch (err) {
      // Silently skip — the widget still works without the document list.
    }
  }

  async function uploadDocument(file) {
    var formData = new FormData();
    formData.append('file', file);

    uploadButton.disabled = true;
    uploadInput.disabled = true;
    uploadButton.textContent = 'Indexing…';
    uploadStatus.textContent = '';

    try {
      // No Content-Type header here — fetch sets the multipart boundary
      // itself for a FormData body; overriding it breaks the upload.
      var response = await fetch('/api/documents/', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken() },
        body: formData,
      });
      var data = await response.json().catch(function () { return {}; });

      if (!response.ok) {
        var fieldError = data.file && data.file[0];
        uploadStatus.textContent = fieldError || 'Could not upload the document.';
        return;
      }

      renderDocument(data);
      uploadStatus.textContent = data.status === 'failed'
        ? 'Indexing failed: ' + data.error_message
        : 'Uploaded.';
    } catch (err) {
      uploadStatus.textContent = 'Could not reach the server. Please try again.';
    } finally {
      uploadButton.disabled = false;
      uploadInput.disabled = false;
      uploadButton.textContent = 'Upload';
      uploadInput.value = '';
    }
  }

  async function deleteDocument(id, li) {
    if (!window.confirm('Delete this document?')) {
      return;
    }
    try {
      var response = await fetch('/api/documents/' + id + '/', {
        method: 'DELETE',
        headers: { 'X-CSRFToken': csrfToken() },
      });
      if (response.ok) {
        li.remove();
      }
    } catch (err) {
      // Leave the item in place — the user can retry the delete.
    }
  }

  function handleUploadSubmit(event) {
    event.preventDefault();
    var file = uploadInput.files[0];
    if (!file) {
      return;
    }
    uploadDocument(file);
  }

  function openPanel() {
    panel.hidden = false;
    if (!historyLoaded) {
      historyLoaded = true;
      loadHistory();
    }
    if (!docsLoaded) {
      docsLoaded = true;
      loadDocuments();
    }
    input.focus();
  }

  function closePanel() {
    panel.hidden = true;
  }

  async function sendMessage(text) {
    appendMessage('user', text);
    input.disabled = true;
    var assistantBubble = appendMessage('assistant', 'Thinking…');
    assistantBubble.classList.add('chat-msg-pending');
    var receivedFirstChunk = false;

    try {
      var response = await fetch('/api/ai/chat/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken(),
        },
        body: JSON.stringify({ message: text }),
      });

      if (!response.ok) {
        assistantBubble.remove();
        var data = await response.json().catch(function () { return {}; });
        appendError(data.error || 'Something went wrong. Please try again.', text);
        return;
      }

      var reader = response.body.getReader();
      var decoder = new TextDecoder();
      while (true) {
        var result = await reader.read();
        if (result.done) {
          break;
        }
        var chunk = decoder.decode(result.value, { stream: true });
        if (!chunk) {
          continue;
        }
        if (!receivedFirstChunk) {
          assistantBubble.textContent = '';
          assistantBubble.classList.remove('chat-msg-pending');
          receivedFirstChunk = true;
        }
        assistantBubble.textContent += chunk;
        messagesEl.scrollTop = messagesEl.scrollHeight;
      }
      if (!receivedFirstChunk) {
        // Stream ended with no content at all (e.g. an empty upstream reply).
        assistantBubble.remove();
        appendError('The AI did not return a reply. Please try again.', text);
      }
    } catch (err) {
      if (receivedFirstChunk) {
        // Keep whatever text already streamed in rather than discarding it —
        // only the connection dropped, the partial reply is still real.
        assistantBubble.classList.remove('chat-msg-pending');
      } else {
        assistantBubble.remove();
      }
      appendError('Could not reach the AI service. Please try again.', text);
    } finally {
      input.disabled = false;
      input.focus();
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    var text = input.value.trim();
    if (!text) {
      return;
    }
    input.value = '';
    sendMessage(text);
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
  uploadForm.addEventListener('submit', handleUploadSubmit);
})();

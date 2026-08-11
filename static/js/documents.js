// Powers the dedicated document-management page (templates/todos/documents.html).
// Plain vanilla JS on purpose — this project has no build step or JS
// framework, matching static/js/chat_widget.js's conventions.
(function () {
  var statsEl = document.getElementById('doc-stats');
  var dropzone = document.getElementById('doc-dropzone');
  var fileInput = document.getElementById('doc-file-input');
  var docListArea = document.getElementById('doc-list-area');
  var docList = document.getElementById('doc-list');
  var emptyState = document.getElementById('doc-empty-state');
  var toastContainer = document.getElementById('toast-container');

  if (!docList) {
    return;
  }

  // Keep in sync with todos/indexing.py's ALLOWED_EXTENSIONS/MAX_UPLOAD_SIZE.
  var ALLOWED_EXTENSIONS = ['txt', 'md', 'pdf'];
  var MAX_UPLOAD_SIZE = 5 * 1024 * 1024;
  var POLL_INTERVAL_MS = 1500;

  var documentsById = {};
  var elementsById = {};
  var pendingDeleteTimeouts = {};

  function getCsrfToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  function validateFile(file) {
    var extension = file.name.indexOf('.') !== -1 ? file.name.split('.').pop().toLowerCase() : '';
    if (ALLOWED_EXTENSIONS.indexOf(extension) === -1) {
      return 'Only .txt, .md, and .pdf files are supported.';
    }
    if (file.size > MAX_UPLOAD_SIZE) {
      return 'File is too large — max ' + (MAX_UPLOAD_SIZE / (1024 * 1024)) + 'MB.';
    }
    return null;
  }

  function showToast(message, type) {
    var toast = document.createElement('div');
    toast.className = 'toast toast-' + (type || 'success');
    toast.textContent = message;
    toastContainer.appendChild(toast);
    setTimeout(function () {
      toast.remove();
    }, 4000);
  }

  function updateEmptyState() {
    emptyState.hidden = Object.keys(documentsById).length > 0;
  }

  function statCard(label, value, attention) {
    var card = document.createElement('div');
    card.className = 'stat-card' + (attention ? ' stat-card-attention' : '');
    var valueEl = document.createElement('span');
    valueEl.className = 'stat-card-value';
    valueEl.textContent = value;
    var labelEl = document.createElement('span');
    labelEl.className = 'stat-card-label';
    labelEl.textContent = label;
    card.appendChild(valueEl);
    card.appendChild(labelEl);
    return card;
  }

  function renderStats() {
    var docs = Object.keys(documentsById).map(function (id) { return documentsById[id]; });
    var attention = docs.filter(function (doc) { return doc.status === 'failed'; }).length;
    var totalChunks = docs.reduce(function (sum, doc) { return sum + (doc.chunk_count || 0); }, 0);

    statsEl.innerHTML = '';
    statsEl.appendChild(statCard('Total documents', docs.length, false));
    statsEl.appendChild(statCard('Needs attention', attention, attention > 0));
    statsEl.appendChild(statCard('Total chunks', totalChunks, false));
  }

  function fileIcon(fileType) {
    if (fileType === 'pdf') return '📕';
    if (fileType === 'md') return '📝';
    return '📄';
  }

  function fileIconClass(fileType) {
    if (fileType === 'pdf') return 'doc-icon-pdf';
    if (fileType === 'md') return 'doc-icon-md';
    return '';
  }

  function statusLabel(status) {
    if (status === 'completed') return 'Ready';
    if (status === 'failed') return 'Failed';
    if (status === 'processing') return 'Indexing…';
    return 'Pending';
  }

  function formatMeta(doc) {
    if (doc.status === 'failed') {
      return doc.error_message || 'Indexing failed.';
    }
    if (doc.status === 'pending') {
      return 'Waiting to be indexed…';
    }
    if (doc.status === 'processing') {
      return 'Indexing…';
    }
    var chunkLabel = doc.chunk_count === 1 ? 'chunk' : 'chunks';
    return doc.char_count.toLocaleString() + ' characters · ' + doc.chunk_count + ' ' + chunkLabel;
  }

  function buildCardSkeleton(id) {
    var li = document.createElement('li');
    li.className = 'doc-card';
    li.dataset.docId = id;

    var icon = document.createElement('div');
    icon.className = 'doc-icon';
    li.appendChild(icon);

    var body = document.createElement('div');
    body.className = 'doc-body';

    var title = document.createElement('div');
    title.className = 'doc-title';
    body.appendChild(title);

    var meta = document.createElement('div');
    meta.className = 'doc-meta';
    body.appendChild(meta);

    var progress = document.createElement('div');
    progress.className = 'doc-progress';
    var progressBar = document.createElement('div');
    progressBar.className = 'doc-progress-bar';
    progress.appendChild(progressBar);
    body.appendChild(progress);

    li.appendChild(body);

    var badge = document.createElement('span');
    badge.className = 'status-badge';
    li.appendChild(badge);

    var removeButton = document.createElement('button');
    removeButton.type = 'button';
    removeButton.className = 'doc-remove';
    removeButton.setAttribute('aria-label', 'Delete document');
    removeButton.textContent = '✕';
    removeButton.addEventListener('click', function () {
      handleDeleteClick(id, removeButton);
    });
    li.appendChild(removeButton);

    return li;
  }

  function getOrCreateCard(doc, insertMode) {
    var li = elementsById[doc.id];
    if (li) {
      return li;
    }
    li = buildCardSkeleton(doc.id);
    elementsById[doc.id] = li;
    if (insertMode === 'prepend') {
      docList.prepend(li);
    } else {
      docList.appendChild(li);
    }
    return li;
  }

  function renderDocumentCard(doc, insertMode) {
    var li = getOrCreateCard(doc, insertMode);

    var icon = li.querySelector('.doc-icon');
    icon.textContent = fileIcon(doc.file_type);
    icon.className = 'doc-icon ' + fileIconClass(doc.file_type);

    li.querySelector('.doc-title').textContent = doc.title;
    li.querySelector('.doc-meta').textContent = formatMeta(doc);
    li.querySelector('.doc-progress').hidden = doc.status !== 'pending' && doc.status !== 'processing';

    var badge = li.querySelector('.status-badge');
    badge.className = 'status-badge status-badge-' + doc.status;
    badge.textContent = statusLabel(doc.status);
  }

  function pollDocument(id) {
    setTimeout(async function poll() {
      try {
        var response = await fetch('/api/documents/' + id + '/');
        if (!response.ok) {
          return;
        }
        var doc = await response.json();
        documentsById[id] = doc;
        renderDocumentCard(doc);
        renderStats();

        if (doc.status === 'pending' || doc.status === 'processing') {
          setTimeout(poll, POLL_INTERVAL_MS);
        } else if (doc.status === 'completed') {
          showToast('"' + doc.title + '" is ready.', 'success');
        } else if (doc.status === 'failed') {
          showToast('"' + doc.title + '" failed: ' + doc.error_message, 'error');
        }
      } catch (err) {
        setTimeout(poll, POLL_INTERVAL_MS);
      }
    }, POLL_INTERVAL_MS);
  }

  async function uploadOneFile(file) {
    var formData = new FormData();
    formData.append('file', file);
    // No Content-Type header here — fetch sets the multipart boundary
    // itself for a FormData body; overriding it breaks the upload.
    var response = await fetch('/api/documents/', {
      method: 'POST',
      headers: { 'X-CSRFToken': getCsrfToken() },
      body: formData,
    });
    var data = await response.json().catch(function () { return {}; });
    if (!response.ok) {
      var fieldError = data.file && data.file[0];
      throw new Error(fieldError || 'Could not upload the document.');
    }
    return data;
  }

  async function uploadFiles(fileList) {
    var files = Array.prototype.slice.call(fileList);
    if (!files.length) {
      return;
    }

    var uploaded = 0;
    var rejected = 0;

    for (var i = 0; i < files.length; i++) {
      var file = files[i];
      var validationError = validateFile(file);
      if (validationError) {
        rejected += 1;
        showToast(file.name + ': ' + validationError, 'error');
        continue;
      }
      try {
        var doc = await uploadOneFile(file);
        uploaded += 1;
        documentsById[doc.id] = doc;
        renderDocumentCard(doc, 'prepend');
        if (doc.status === 'pending' || doc.status === 'processing') {
          pollDocument(doc.id);
        }
      } catch (err) {
        rejected += 1;
        showToast(file.name + ': ' + err.message, 'error');
      }
    }

    renderStats();
    updateEmptyState();

    if (files.length > 1) {
      var summary = uploaded + ' of ' + files.length + ' documents uploaded';
      if (rejected) {
        summary += ' — ' + rejected + ' rejected';
      }
      showToast(summary, rejected ? 'error' : 'success');
    } else if (uploaded === 1) {
      showToast('Document uploaded — indexing now.', 'success');
    }
  }

  function handleDeleteClick(id, button) {
    if (button.classList.contains('confirming')) {
      clearTimeout(pendingDeleteTimeouts[id]);
      delete pendingDeleteTimeouts[id];
      deleteDocument(id);
      return;
    }
    button.classList.add('confirming');
    button.textContent = 'Confirm delete?';
    pendingDeleteTimeouts[id] = setTimeout(function () {
      button.classList.remove('confirming');
      button.textContent = '✕';
      delete pendingDeleteTimeouts[id];
    }, 4000);
  }

  async function deleteDocument(id) {
    try {
      var response = await fetch('/api/documents/' + id + '/', {
        method: 'DELETE',
        headers: { 'X-CSRFToken': getCsrfToken() },
      });
      if (!response.ok) {
        showToast('Could not delete the document.', 'error');
        return;
      }
      var li = elementsById[id];
      if (li) {
        li.remove();
      }
      delete elementsById[id];
      delete documentsById[id];
      renderStats();
      updateEmptyState();
      showToast('Document deleted.', 'success');
    } catch (err) {
      showToast('Could not reach the server. Please try again.', 'error');
    }
  }

  async function loadDocuments() {
    try {
      var response = await fetch('/api/documents/');
      if (!response.ok) {
        return;
      }
      var docs = await response.json();
      docs.forEach(function (doc) {
        documentsById[doc.id] = doc;
        renderDocumentCard(doc, 'append');
        if (doc.status === 'pending' || doc.status === 'processing') {
          pollDocument(doc.id);
        }
      });
      renderStats();
      updateEmptyState();
    } catch (err) {
      showToast('Could not load documents.', 'error');
    }
  }

  function preventDefaults(event) {
    event.preventDefault();
    event.stopPropagation();
  }

  [dropzone, docListArea].forEach(function (target) {
    ['dragenter', 'dragover'].forEach(function (eventName) {
      target.addEventListener(eventName, function (event) {
        preventDefaults(event);
        target.classList.add('drag-over');
      });
    });
    ['dragleave', 'drop'].forEach(function (eventName) {
      target.addEventListener(eventName, function (event) {
        preventDefaults(event);
        target.classList.remove('drag-over');
      });
    });
    target.addEventListener('drop', function (event) {
      if (event.dataTransfer && event.dataTransfer.files.length) {
        uploadFiles(event.dataTransfer.files);
      }
    });
  });

  dropzone.addEventListener('click', function () {
    fileInput.click();
  });
  dropzone.addEventListener('keydown', function (event) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      fileInput.click();
    }
  });
  fileInput.addEventListener('change', function () {
    if (fileInput.files.length) {
      uploadFiles(fileInput.files);
      fileInput.value = '';
    }
  });

  renderStats();
  loadDocuments();
})();

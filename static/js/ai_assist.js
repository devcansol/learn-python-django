(function () {
  function csrfToken() {
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : '';
  }

  function showError(button, message) {
    var error = button.parentElement.querySelector('.ai-generate-error');
    if (!error) {
      error = document.createElement('span');
      error.className = 'ai-generate-error';
      error.style.color = '#c0392b';
      error.style.marginLeft = '0.5em';
      button.insertAdjacentElement('afterend', error);
    }
    error.textContent = message;
  }

  function clearError(button) {
    var error = button.parentElement.querySelector('.ai-generate-error');
    if (error) {
      error.textContent = '';
    }
  }

  async function handleClick(button) {
    var descriptionField = document.getElementById(button.dataset.descriptionField);
    var subjectField = document.getElementById(button.dataset.subjectField);
    var hintField = button.dataset.hintField ? document.getElementById(button.dataset.hintField) : null;
    if (!descriptionField || !subjectField) {
      return;
    }

    var subject = subjectField.value.trim();
    if (!subject) {
      showError(button, 'Enter a name first.');
      return;
    }

    clearError(button);
    var originalLabel = button.textContent;
    button.disabled = true;
    button.textContent = 'Generating…';

    try {
      var response = await fetch('/api/ai/generate-description/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken(),
        },
        body: JSON.stringify({
          kind: button.dataset.kind,
          subject: subject,
          hint: hintField ? hintField.value.trim() : '',
          parent_context: button.dataset.parentContext || '',
        }),
      });

      var data = await response.json();
      if (!response.ok) {
        showError(button, data.error || 'Something went wrong. Please try again.');
        return;
      }

      descriptionField.value = data.description;
    } catch (err) {
      showError(button, 'Could not reach the AI service. Please try again.');
    } finally {
      button.disabled = false;
      button.textContent = originalLabel;
    }
  }

  document.querySelectorAll('[data-ai-generate]').forEach(function (button) {
    button.addEventListener('click', function (event) {
      event.preventDefault();
      handleClick(button);
    });
  });
})();
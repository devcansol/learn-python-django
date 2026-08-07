document.addEventListener("DOMContentLoaded", function () {
  const toggleBtn = document.getElementById("chat-toggle-btn");
  const closeBtn = document.getElementById("chat-close-btn");
  const chatWindow = document.getElementById("chat-window");
  const messagesEl = document.getElementById("chat-messages");
  const form = document.getElementById("chat-input-form");
  const input = document.getElementById("chat-input");

  // ---- Edit this list to match your app's real features ----
  const FAQ = [
    { keywords: ["create", "add", "new task"], answer: "To create a task, click the '+ New Task' button on your dashboard, fill in the details, and click Save." },
    { keywords: ["delete", "remove"], answer: "Open the task, click the three-dot menu, then select 'Delete Task'." },
    { keywords: ["edit", "update"], answer: "Click on any task to open it, make your changes, then click 'Save'." },
    { keywords: ["password", "reset", "forgot"], answer: "Click 'Forgot your password?' on the login page to reset it via email." },
    { keywords: ["sign up", "register", "account"], answer: "Click 'Sign up' on the login page and fill in your details to create an account." },
    { keywords: ["due date", "deadline"], answer: "You can set a due date when creating or editing a task using the date picker." },
    { keywords: ["hello", "hi", "hey"], answer: "Hi there! Ask me anything about using TaskFlow." },
  ];
  const FALLBACK = "I'm not sure about that yet. Try asking about creating, editing, or deleting tasks, or your account.";

  function addMessage(text, sender) {
    const msg = document.createElement("div");
    msg.className = `chat-msg ${sender}`;
    msg.textContent = text;
    messagesEl.appendChild(msg);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function getAnswer(question) {
    const q = question.toLowerCase();
    const match = FAQ.find(item => item.keywords.some(k => q.includes(k)));
    return match ? match.answer : FALLBACK;
  }

  toggleBtn.addEventListener("click", () => {
    chatWindow.classList.toggle("hidden");
    if (!chatWindow.classList.contains("hidden") && messagesEl.children.length === 0) {
      addMessage("Hi! I'm the TaskFlow assistant. Ask me how to use the app.", "bot");
    }
  });

  closeBtn.addEventListener("click", () => chatWindow.classList.add("hidden"));

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    const question = input.value.trim();
    if (!question) return;
    addMessage(question, "user");
    input.value = "";
    setTimeout(() => addMessage(getAnswer(question), "bot"), 300);
  });
});
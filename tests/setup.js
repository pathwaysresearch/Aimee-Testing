// Minimal DOM scaffold that script.js expects on load.
// Jest runs this before each test file via setupFiles in package.json.
document.body.innerHTML = `
  <main id="messages"><div class="welcome"><p>Hello</p></div></main>
  <div id="tool-indicator" class="tool-indicator hidden"></div>
  <textarea id="input"></textarea>
  <button id="send-btn" disabled></button>
`;

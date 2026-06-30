export function renderChat(container, messages = []) { if (!container) return; container.innerHTML = messages.map((m) => `<div class="chat-row">${String(m.content || "")}</div>`).join(""); }

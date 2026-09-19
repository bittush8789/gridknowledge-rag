// GridKnowledge RAG Enterprise Frontend Engine (Vanilla JS)

const PRESET_ACCOUNTS = [
  { email: "admin@gridknowledge.internal", name: "System Administrator", role: "Admin", pass: "AdminPass123!" },
  { email: "engineer@gridknowledge.internal", name: "Lead Electrical Engineer", role: "Engineer", pass: "EngineerPass123!" },
  { email: "maintenance@gridknowledge.internal", name: "Substation Maintenance Tech", role: "Maintenance", pass: "MaintPass123!" },
  { email: "operations@gridknowledge.internal", name: "Grid Operations Controller", role: "Operations", pass: "OpsPass123!" },
  { email: "viewer@gridknowledge.internal", name: "Compliance Viewer", role: "Viewer", pass: "ViewerPass123!" },
];

class GridKnowledgeApp {
  constructor() {
    this.currentUser = null;
    this.authToken = localStorage.getItem("gridknowledge_token") || null;
    this.currentConversationId = null;

    this.initElements();
    this.bindEvents();
    this.initAuth();
  }

  initElements() {
    this.userDisplayName = document.getElementById("user-display-name");
    this.userRolePill = document.getElementById("user-role-pill");
    this.btnSwitchUser = document.getElementById("btn-switch-user");
    this.userModal = document.getElementById("user-modal");
    this.btnCloseUserModal = document.getElementById("btn-close-user-modal");
    this.userRoleSelectorList = document.getElementById("user-role-selector-list");

    this.navAdmin = document.getElementById("nav-admin") || document.getElementById("nav-admin-btn");
    this.adminModal = document.getElementById("admin-modal");
    this.btnCloseAdminModal = document.getElementById("btn-close-admin-modal");

    this.sourceModal = document.getElementById("source-modal");
    this.btnCloseSourceModal = document.getElementById("btn-close-source-modal");

    this.sourcesCatalogModal = document.getElementById("sources-catalog-modal");
    this.btnCloseSourcesCatalog = document.getElementById("btn-close-sources-catalog");
    this.navSourcesBtn = document.getElementById("nav-sources-btn") || document.getElementById("nav-sources");

    this.settingsModal = document.getElementById("settings-modal");
    this.btnCloseSettingsModal = document.getElementById("btn-close-settings-modal");
    this.navSettingsBtn = document.getElementById("nav-settings-btn") || document.getElementById("nav-settings");

    // Chat specific elements
    this.chatForm = document.getElementById("chat-form");
    this.chatInput = document.getElementById("chat-input");
    this.chatSubmitBtn = document.getElementById("chat-submit-btn");
    this.chatMessages = document.getElementById("chat-messages");
    this.conversationList = document.getElementById("conversation-list");
    this.btnNewChat = document.getElementById("btn-new-chat");
    this.welcomeCard = document.getElementById("welcome-message-card");
  }

  bindEvents() {
    // User Switcher Modal
    if (this.btnSwitchUser) {
      this.btnSwitchUser.addEventListener("click", () => this.openUserModal());
    }
    if (this.btnCloseUserModal) {
      this.btnCloseUserModal.addEventListener("click", () => this.closeModal(this.userModal));
    }

    // Admin Modal
    if (this.navAdmin) {
      this.navAdmin.addEventListener("click", () => this.openAdminModal());
    }
    if (this.btnCloseAdminModal) {
      this.btnCloseAdminModal.addEventListener("click", () => this.closeModal(this.adminModal));
    }

    // Sources Catalog Modal
    if (this.navSourcesBtn) {
      this.navSourcesBtn.addEventListener("click", () => this.openSourcesCatalog());
    }
    if (this.btnCloseSourcesCatalog) {
      this.btnCloseSourcesCatalog.addEventListener("click", () => this.closeModal(this.sourcesCatalogModal));
    }

    // Settings Modal
    if (this.navSettingsBtn) {
      this.navSettingsBtn.addEventListener("click", () => this.openSettingsModal());
    }
    if (this.btnCloseSettingsModal) {
      this.btnCloseSettingsModal.addEventListener("click", () => this.closeModal(this.settingsModal));
    }

    // Source Inspector Modal
    if (this.btnCloseSourceModal) {
      this.btnCloseSourceModal.addEventListener("click", () => this.closeModal(this.sourceModal));
    }

    // Chat events
    if (this.chatForm) {
      this.chatForm.addEventListener("submit", (e) => {
        e.preventDefault();
        this.handleSendMessage();
      });
    }

    if (this.btnNewChat) {
      this.btnNewChat.addEventListener("click", () => {
        this.startNewChat();
      });
    }

    // Admin Tabs
    document.querySelectorAll(".admin-tab").forEach(tabBtn => {
      tabBtn.addEventListener("click", () => {
        const tabId = tabBtn.getAttribute("data-tab");
        this.switchAdminTab(tabBtn, tabId);
      });
    });

    // Admin Action Buttons
    const btnIngest = document.getElementById("btn-admin-trigger-ingest");
    if (btnIngest) {
      btnIngest.addEventListener("click", () => this.triggerAdminIngest());
    }

    const btnReindex = document.getElementById("btn-admin-reindex");
    if (btnReindex) {
      btnReindex.addEventListener("click", () => this.triggerAdminReindex());
    }

    const btnEval = document.getElementById("btn-admin-run-eval");
    if (btnEval) {
      btnEval.addEventListener("click", () => this.triggerAdminEvaluation());
    }
  }

  async initAuth() {
    // If no token, log in as Engineer by default for a rich experience
    if (!this.authToken) {
      await this.loginUser(PRESET_ACCOUNTS[1].email, PRESET_ACCOUNTS[1].pass);
    } else {
      try {
        const res = await fetch("/api/auth/me", {
          headers: { Authorization: `Bearer ${this.authToken}` }
        });
        if (res.ok) {
          const data = await res.json();
          this.setCurrentUser(data.user);
        } else {
          await this.loginUser(PRESET_ACCOUNTS[1].email, PRESET_ACCOUNTS[1].pass);
        }
      } catch (e) {
        console.error("Auth verification error:", e);
      }
    }

    // If on chat page, load conversations and check for initial query
    if (this.chatMessages) {
      await this.loadConversations();
      this.checkInitialQuery();
    }
  }

  async loginUser(email, password) {
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      if (res.ok) {
        const data = await res.json();
        this.authToken = data.access_token;
        localStorage.setItem("gridknowledge_token", this.authToken);
        this.setCurrentUser(data.user);
        if (this.chatMessages) {
          await this.loadConversations();
        }
      }
    } catch (e) {
      console.error("Login failed:", e);
    }
  }

  setCurrentUser(user) {
    this.currentUser = user;
    if (this.userDisplayName) this.userDisplayName.textContent = user.full_name || user.email;
    if (this.userRolePill) this.userRolePill.textContent = user.role;

    // Show/hide admin link
    if (this.navAdmin) {
      this.navAdmin.style.display = (user.role === "Admin") ? "block" : "none";
    }
  }

  openUserModal() {
    if (!this.userRoleSelectorList) return;
    this.userRoleSelectorList.innerHTML = "";

    PRESET_ACCOUNTS.forEach(acc => {
      const isCurrent = this.currentUser && this.currentUser.email === acc.email;
      const btn = document.createElement("div");
      btn.className = "conversation-item";
      btn.style.padding = "12px 16px";
      btn.style.border = isCurrent ? "1.5px solid var(--primary)" : "1px solid var(--border-subtle)";
      btn.style.backgroundColor = isCurrent ? "var(--primary-light)" : "var(--bg-surface)";

      btn.innerHTML = `
        <div style="flex: 1;">
          <div style="font-weight: 600; font-size: 14px; color: var(--text-primary);">${acc.name}</div>
          <div style="font-size: 12px; color: var(--text-muted);">${acc.email}</div>
        </div>
        <span class="role-pill" style="margin-left: 10px;">${acc.role}</span>
      `;

      btn.addEventListener("click", async () => {
        await this.loginUser(acc.email, acc.pass);
        this.closeModal(this.userModal);
      });

      this.userRoleSelectorList.appendChild(btn);
    });

    this.userModal.classList.add("open");
  }

  closeModal(modal) {
    if (modal) modal.classList.remove("open");
  }

  // --- Chat Messaging & RAG Handling ---
  async handleSendMessage() {
    const query = this.chatInput.value.trim();
    if (!query) return;

    if (this.welcomeCard) {
      this.welcomeCard.remove();
      this.welcomeCard = null;
    }

    // Append user message
    this.appendMessageBubble("user", query);
    this.chatInput.value = "";
    this.chatSubmitBtn.disabled = true;

    // Show loading typing indicator
    const typingElem = this.appendTypingIndicator();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.authToken}`
        },
        body: JSON.stringify({
          query: query,
          conversation_id: this.currentConversationId
        })
      });

      typingElem.remove();

      if (res.ok) {
        const data = await res.json();
        this.currentConversationId = data.conversation_id;
        this.appendMessageBubble("assistant", data.answer, data.citations, data.latency_ms);
        await this.loadConversations();
      } else {
        const err = await res.json();
        this.appendMessageBubble(
          "assistant",
          err.detail || "Something went wrong. Please try again.",
          []
        );
      }
    } catch (e) {
      if (typingElem) typingElem.remove();
      this.appendMessageBubble("assistant", "Something went wrong. Please try again.", []);
    } finally {
      this.chatSubmitBtn.disabled = false;
      this.chatInput.focus();
    }
  }

  appendMessageBubble(role, text, citations = [], latencyMs = null) {
    const row = document.createElement("div");
    row.className = `message-row ${role}`;

    const bubble = document.createElement("div");
    bubble.className = `message-bubble ${role}`;

    // Format markdown bolding and bullet lists
    let formattedHtml = this.formatMarkdown(text);
    bubble.innerHTML = formattedHtml;

    // Append citations if present
    if (citations && citations.length > 0) {
      const citBox = document.createElement("div");
      citBox.className = "citations-box";
      citBox.innerHTML = `<div class="citations-header">📚 Approved Sources</div>`;

      const citList = document.createElement("div");
      citList.className = "citations-list";

      citations.forEach(cit => {
        const badge = document.createElement("div");
        badge.className = "citation-badge";
        badge.innerHTML = `
          <span>📄</span>
          <strong>${cit.document_title}</strong>
          <span>— Page ${cit.page} (v${cit.version})</span>
        `;
        badge.title = `Click to inspect verified source from ${cit.document_title} (${cit.section})`;
        badge.addEventListener("click", () => this.openSourceInspector(cit));
        citList.appendChild(badge);
      });

      citBox.appendChild(citList);
      bubble.appendChild(citBox);
    }

    row.appendChild(bubble);

    if (latencyMs !== null && role === "assistant") {
      const meta = document.createElement("div");
      meta.className = "message-meta";
      meta.innerHTML = `<span>⚡ Grounded in ${latencyMs} ms</span>`;
      row.appendChild(meta);
    }

    this.chatMessages.appendChild(row);
    this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
  }

  appendTypingIndicator() {
    const row = document.createElement("div");
    row.className = "message-row assistant";
    row.innerHTML = `
      <div class="message-bubble assistant">
        <div class="typing-dots">
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
        </div>
      </div>
    `;
    this.chatMessages.appendChild(row);
    this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    return row;
  }

  formatMarkdown(text) {
    // Escape HTML tags to prevent XSS
    let escaped = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // Headings
    escaped = escaped.replace(/^### (.*$)/gim, '<h4 style="margin: 10px 0 6px 0; font-size: 14.5px; font-weight: 700;">$1</h4>');
    escaped = escaped.replace(/^## (.*$)/gim, '<h3 style="margin: 12px 0 8px 0; font-size: 15.5px; font-weight: 700;">$1</h3>');

    // Bold & Italics
    escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    escaped = escaped.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Bullet lists
    escaped = escaped.replace(/^\* (.*$)/gim, '<li style="margin-left: 18px; margin-bottom: 4px;">$1</li>');
    escaped = escaped.replace(/^- (.*$)/gim, '<li style="margin-left: 18px; margin-bottom: 4px;">$1</li>');
    escaped = escaped.replace(/^\d+\. (.*$)/gim, '<li style="margin-left: 18px; margin-bottom: 4px;">$1</li>');

    // Line breaks
    escaped = escaped.replace(/\n\n/g, '<p style="margin-bottom: 8px;"></p>');
    escaped = escaped.replace(/\n/g, '<br>');

    return escaped;
  }

  // --- Source Inspector Modal ---
  openSourceInspector(citation) {
    const titleElem = document.getElementById("source-modal-title");
    const metaGrid = document.getElementById("source-meta-grid");
    const excerptBox = document.getElementById("source-excerpt-box");

    titleElem.textContent = citation.document_title;
    metaGrid.innerHTML = `
      <div class="source-meta-item">Document: <strong>${citation.document_title}</strong></div>
      <div class="source-meta-item">Section: <strong>${citation.section || 'General'}</strong></div>
      <div class="source-meta-item">Page Number: <strong>Page ${citation.page}</strong></div>
      <div class="source-meta-item">Version: <strong>v${citation.version}</strong></div>
    `;

    excerptBox.textContent = citation.excerpt || "No excerpt preview available.";
    this.sourceModal.classList.add("open");
  }

  // --- Conversation Sessions ---
  async loadConversations() {
    if (!this.conversationList) return;
    try {
      const res = await fetch("/api/conversations", {
        headers: { Authorization: `Bearer ${this.authToken}` }
      });
      if (res.ok) {
        const convs = await res.json();
        this.conversationList.innerHTML = "";

        convs.forEach(c => {
          const item = document.createElement("div");
          item.className = `conversation-item ${c.id === this.currentConversationId ? 'active' : ''}`;
          item.innerHTML = `
            <span class="conv-title" title="${c.title}">${c.title || 'Conversation'}</span>
            <span class="conv-delete" title="Delete conversation">&times;</span>
          `;

          item.querySelector(".conv-title").addEventListener("click", () => {
            this.switchConversation(c.id);
          });

          item.querySelector(".conv-delete").addEventListener("click", async (e) => {
            e.stopPropagation();
            await this.deleteConversation(c.id);
          });

          this.conversationList.appendChild(item);
        });
      }
    } catch (e) {
      console.error("Failed to load conversations:", e);
    }
  }

  async switchConversation(convId) {
    this.currentConversationId = convId;
    this.chatMessages.innerHTML = "";

    try {
      const res = await fetch(`/api/conversations/${convId}`, {
        headers: { Authorization: `Bearer ${this.authToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        data.messages.forEach(msg => {
          this.appendMessageBubble(msg.role, msg.content, msg.citations, msg.latency_ms);
        });
        await this.loadConversations();
      }
    } catch (e) {
      console.error("Failed to fetch conversation:", e);
    }
  }

  async deleteConversation(convId) {
    try {
      await fetch(`/api/conversations/${convId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${this.authToken}` }
      });
      if (this.currentConversationId === convId) {
        this.startNewChat();
      } else {
        await this.loadConversations();
      }
    } catch (e) {
      console.error("Delete conversation failed:", e);
    }
  }

  startNewChat() {
    this.currentConversationId = null;
    this.chatMessages.innerHTML = `
      <div id="welcome-message-card" style="text-align: center; margin: auto; max-width: 520px; padding: 40px 20px;">
        <div style="font-size: 42px; margin-bottom: 12px;">⚡</div>
        <h2 style="font-size: 20px; font-weight: 700; margin-bottom: 8px;">Grid Knowledge Assistant</h2>
        <p style="font-size: 14px; color: var(--text-secondary); line-height: 1.6;">
          Ask questions about approved electricity-grid operations, equipment manuals, maintenance procedures, or safety SOPs. All answers are strictly grounded with verifiable citations.
        </p>
      </div>
    `;
    this.welcomeCard = document.getElementById("welcome-message-card");
    if (this.conversationList) {
      document.querySelectorAll(".conversation-item").forEach(el => el.classList.remove("active"));
    }
  }

  checkInitialQuery() {
    const initQ = sessionStorage.getItem("gridknowledge_initial_query");
    if (initQ) {
      sessionStorage.removeItem("gridknowledge_initial_query");
      this.chatInput.value = initQ;
      this.handleSendMessage();
    }
  }

  // --- Admin Modal Actions ---
  openAdminModal() {
    if (!this.adminModal) return;
    this.adminModal.classList.add("open");
    this.loadAdminDocuments();
    this.loadAdminEvaluation();
    this.loadAdminUsers();
    this.loadAdminAudit();
  }

  switchAdminTab(clickedBtn, tabId) {
    document.querySelectorAll(".admin-tab").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".admin-tab-content").forEach(c => c.style.display = "none");

    clickedBtn.classList.add("active");
    const target = document.getElementById(tabId);
    if (target) target.style.display = "block";
  }

  async loadAdminDocuments() {
    const tbody = document.getElementById("admin-docs-table-body");
    if (!tbody) return;
    tbody.innerHTML = "<tr><td colspan='5'>Loading documents...</td></tr>";

    try {
      const res = await fetch("/api/admin/documents", {
        headers: { Authorization: `Bearer ${this.authToken}` }
      });
      if (res.ok) {
        const docs = await res.json();
        tbody.innerHTML = "";
        docs.forEach(d => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td><strong>${d.title}</strong></td>
            <td>${d.category}</td>
            <td>v${d.version}</td>
            <td><span class="role-pill">${d.access_level}</span></td>
            <td><span class="badge-tag active">${d.status}</span></td>
          `;
          tbody.appendChild(tr);
        });
      }
    } catch (e) {
      tbody.innerHTML = "<tr><td colspan='5'>Failed to load documents.</td></tr>";
    }
  }

  async triggerAdminIngest() {
    const btn = document.getElementById("btn-admin-trigger-ingest");
    if (btn) btn.disabled = true;
    try {
      const res = await fetch("/api/admin/ingest", {
        method: "POST",
        headers: { Authorization: `Bearer ${this.authToken}` }
      });
      if (res.ok) {
        alert("Knowledge base ingestion completed successfully.");
        await this.loadAdminDocuments();
      }
    } catch (e) {
      alert("Ingestion error: " + e.message);
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async triggerAdminReindex() {
    const btn = document.getElementById("btn-admin-reindex");
    if (btn) btn.disabled = true;
    try {
      const res = await fetch("/api/admin/reindex", {
        method: "POST",
        headers: { Authorization: `Bearer ${this.authToken}` }
      });
      if (res.ok) {
        alert("BM25 and Vector indices re-indexed successfully.");
      }
    } catch (e) {
      alert("Re-index error: " + e.message);
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async loadAdminEvaluation() {
    const tbody = document.getElementById("admin-eval-table-body");
    if (!tbody) return;

    try {
      const res = await fetch("/api/admin/evaluation", {
        headers: { Authorization: `Bearer ${this.authToken}` }
      });
      if (res.ok) {
        const evals = await res.json();
        tbody.innerHTML = "";
        if (evals.length > 0) {
          const latest = evals[0];
          document.getElementById("metric-overall-score").textContent = `${latest.overall_score}%`;
          const m = latest.metrics;
          if (m && m.retrieval) {
            document.getElementById("metric-precision").textContent = `${Math.round(m.retrieval.context_precision * 100)}%`;
          }
          if (m && m.generation) {
            document.getElementById("metric-faithfulness").textContent = `${Math.round(m.generation.faithfulness * 100)}%`;
          }
          if (m && m.safety) {
            document.getElementById("metric-safety").textContent = `${Math.round(m.safety.overall_safety_rate * 100)}%`;
          }

          evals.forEach(ev => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
              <td>${new Date(ev.run_timestamp).toLocaleString()}</td>
              <td><strong>${ev.overall_score}%</strong></td>
              <td>${ev.sample_count} test cases</td>
              <td>${ev.triggered_by}</td>
            `;
            tbody.appendChild(tr);
          });
        } else {
          tbody.innerHTML = "<tr><td colspan='4'>No benchmark runs recorded yet. Click 'Run Benchmark Now' above.</td></tr>";
        }
      }
    } catch (e) {
      console.error("Evaluation load failed:", e);
    }
  }

  async triggerAdminEvaluation() {
    const btn = document.getElementById("btn-admin-run-eval");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Running Benchmark...";
    }
    try {
      const res = await fetch("/api/admin/evaluation/run", {
        method: "POST",
        headers: { Authorization: `Bearer ${this.authToken}` }
      });
      if (res.ok) {
        alert("Evaluation benchmark completed!");
        await this.loadAdminEvaluation();
      }
    } catch (e) {
      alert("Evaluation run failed: " + e.message);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "Run Benchmark Now";
      }
    }
  }

  async loadAdminUsers() {
    const tbody = document.getElementById("admin-users-table-body");
    if (!tbody) return;

    try {
      const res = await fetch("/api/admin/users", {
        headers: { Authorization: `Bearer ${this.authToken}` }
      });
      if (res.ok) {
        const users = await res.json();
        tbody.innerHTML = "";
        users.forEach(u => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td><strong>${u.full_name}</strong></td>
            <td>${u.email}</td>
            <td><span class="role-pill">${u.role}</span></td>
            <td><span class="badge-tag active">${u.is_active ? 'Active' : 'Inactive'}</span></td>
          `;
          tbody.appendChild(tr);
        });
      }
    } catch (e) {
      console.error("Users load failed:", e);
    }
  }

  async loadAdminAudit() {
    const tbody = document.getElementById("admin-audit-table-body");
    if (!tbody) return;

    try {
      const res = await fetch("/api/admin/audit-logs", {
        headers: { Authorization: `Bearer ${this.authToken}` }
      });
      if (res.ok) {
        const logs = await res.json();
        tbody.innerHTML = "";
        logs.forEach(l => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td>${new Date(l.timestamp).toLocaleTimeString()}</td>
            <td><strong>${l.action}</strong></td>
            <td>${l.target_type || '-'}</td>
            <td>${l.ip_address || '127.0.0.1'}</td>
          `;
          tbody.appendChild(tr);
        });
      }
    } catch (e) {
      console.error("Audit load failed:", e);
    }
  }

  // --- Sources Catalog Modal ---
  async openSourcesCatalog() {
    if (!this.sourcesCatalogModal) return;
    this.sourcesCatalogModal.classList.add("open");

    const tbody = document.getElementById("sources-catalog-tbody");
    if (!tbody) return;
    tbody.innerHTML = "<tr><td colspan='6'>Loading approved documentation...</td></tr>";

    try {
      const res = await fetch("/api/admin/documents", {
        headers: { Authorization: `Bearer ${this.authToken}` }
      });
      if (res.ok) {
        const docs = await res.json();
        tbody.innerHTML = "";
        docs.forEach(d => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td><strong>${d.title}</strong></td>
            <td>${d.category}</td>
            <td>${d.equipment || 'Grid Asset'}</td>
            <td>v${d.version}</td>
            <td>${d.page_count}</td>
            <td><span class="role-pill">${d.access_level}</span></td>
          `;
          tbody.appendChild(tr);
        });
      }
    } catch (e) {
      tbody.innerHTML = "<tr><td colspan='6'>Documentation inventory currently unavailable.</td></tr>";
    }
  }

  // --- Settings Modal ---
  async openSettingsModal() {
    if (!this.settingsModal) return;
    this.settingsModal.classList.add("open");

    try {
      const res = await fetch("/api/health");
      if (res.ok) {
        const h = await res.json();
        document.getElementById("health-db-status").textContent = h.database;
        const modelElem = document.getElementById("health-model-status");
        if (modelElem) modelElem.textContent = h.active_model || h.llm_inference;
        document.getElementById("health-retrieval-status").textContent = `BM25 (${h.retrieval.bm25_indexed_chunks} chunks) + ${h.retrieval.vector_store}`;
        document.getElementById("health-obs-status").textContent = h.observability.langsmith_enabled ? "LangSmith (Active)" : "LangSmith (Configured)";
      }
    } catch (e) {
      console.error("Health check error:", e);
    }
  }
}

// Instantiate on DOM load
document.addEventListener("DOMContentLoaded", () => {
  window.gridKnowledgeApp = new GridKnowledgeApp();
});

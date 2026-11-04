(() => {
  const $ = id => document.getElementById(id);
  const STORE_KEY = "fixreadme.ai-settings";
  const THEME_KEY = "fixreadme.theme";
  const GH_KEY = "fixreadme.github-token";
  const GH_REMEMBER_KEY = "fixreadme.github-remember";
  const DEFAULTS = { provider: "ollama", api_key: "", base_url: "", model: "" };
  const STATE_TEXT = {
    checking: "Checking local AI", missing: "Local AI not installed", starting: "Starting local AI",
    pulling: "Downloading local model", ready: "Local AI ready", error: "Local AI unavailable", idle: "Local AI idle"
  };
  let providers = {
    ollama: { label: "Local Ollama (default)", short: "Ollama", base: "http://127.0.0.1:11434/v1", model: "qwen2.5:0.5b", key: false },
    openai: { label: "OpenAI or compatible API", short: "OpenAI", base: "https://api.openai.com/v1", model: "gpt-4o-mini", key: true },
    anthropic: { label: "Anthropic Claude", short: "Anthropic", base: "https://api.anthropic.com", model: "claude-haiku-5-5", key: true }
  };

  // ---------- helpers ----------
  async function postJson(url, payload) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    let data = {};
    try { data = await response.json(); } catch { /* not JSON */ }
    if (!response.ok) throw new Error(data.error || `The request failed (HTTP ${response.status}).`);
    return data;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function loadSettings() {
    try { return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(STORE_KEY) || "{}") }; }
    catch { return { ...DEFAULTS }; }
  }

  function saveSettings(settings) {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(settings)); } catch { /* storage disabled */ }
  }

  // ---------- GitHub token ----------
  // Kept in sessionStorage (cleared when the tab closes) unless "Remember on this device" is ticked.
  // It is sent only to this local server, which forwards it only to api.github.com.
  function githubRemembered() {
    try { return localStorage.getItem(GH_REMEMBER_KEY) === "1"; } catch { return false; }
  }

  function loadGithubToken() {
    try {
      return (githubRemembered() ? localStorage : sessionStorage).getItem(GH_KEY) || "";
    } catch { return ""; }
  }

  function saveGithubToken(token, remember) {
    try {
      localStorage.removeItem(GH_KEY);
      sessionStorage.removeItem(GH_KEY);
      localStorage.setItem(GH_REMEMBER_KEY, remember ? "1" : "0");
      if (token) (remember ? localStorage : sessionStorage).setItem(GH_KEY, token);
    } catch { /* storage disabled */ }
  }

  // ---------- theme ----------
  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  function applyTheme(theme, persist = true) {
    document.documentElement.setAttribute("data-theme", theme);
    $("themeToggle").setAttribute("aria-checked", String(theme === "dark"));
    if (persist) {
      try { localStorage.setItem(THEME_KEY, theme); } catch { /* storage disabled */ }
    }
  }

  $("themeToggle").addEventListener("click", () => applyTheme(currentTheme() === "dark" ? "light" : "dark"));
  // If the user has never picked a theme, follow the system setting when it changes.
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", event => {
    let saved = null;
    try { saved = localStorage.getItem(THEME_KEY); } catch { /* ignore */ }
    if (!saved) applyTheme(event.matches ? "dark" : "light", false);
  });
  applyTheme(currentTheme(), false);

  // ---------- status pill ----------
  let pollTimer = null;

  function setPill(state, text, title) {
    $("aiPill").dataset.state = state;
    $("aiPillText").textContent = text;
    $("aiPill").title = title || text;
  }

  async function refreshStatus() {
    const saved = loadSettings();
    let status = { state: "idle", message: "" };
    try {
      status = await (await fetch("/api/status", { cache: "no-store" })).json();
    } catch {
      status = { state: "error", message: "The local server is not responding." };
    }
    if (saved.provider !== "ollama" && saved.api_key) {
      const label = providers[saved.provider]?.short || saved.provider;
      setPill("cloud", `Using ${label}`, `AI requests go to ${label} with your key.`);
    } else {
      setPill(status.state, STATE_TEXT[status.state] || "Local AI", status.message);
    }
    const busy = ["checking", "starting", "pulling"].includes(status.state);
    clearTimeout(pollTimer);
    pollTimer = setTimeout(refreshStatus, busy ? 3000 : 15000);
  }

  // ---------- settings dialog ----------
  function fillProviderSelect() {
    $("providerSelect").innerHTML = Object.entries(providers)
      .map(([name, spec]) => `<option value="${escapeHtml(name)}">${escapeHtml(spec.label)}</option>`).join("");
  }

  function fillForm(settings) {
    $("providerSelect").value = providers[settings.provider] ? settings.provider : "ollama";
    $("apiKeyInput").value = settings.api_key || "";
    $("baseUrlInput").value = settings.base_url || "";
    $("modelInput").value = settings.model || "";
    setKeyVisible(false);
    $("githubTokenInput").value = loadGithubToken();
    $("githubTokenInput").type = "password";
    $("toggleGhBtn").textContent = "Show";
    $("toggleGhBtn").setAttribute("aria-pressed", "false");
    $("rememberGh").checked = githubRemembered();
    $("ghTestResult").textContent = "";
    $("ghTestResult").removeAttribute("data-state");
    $("testResult").textContent = "";
    $("testResult").removeAttribute("data-state");
    refreshProviderHints();
  }

  function readForm() {
    return {
      provider: $("providerSelect").value,
      api_key: $("apiKeyInput").value.trim(),
      base_url: $("baseUrlInput").value.trim(),
      model: $("modelInput").value.trim()
    };
  }

  function refreshProviderHints() {
    const name = $("providerSelect").value;
    const spec = providers[name] || {};
    $("baseUrlInput").placeholder = spec.base || "";
    $("modelInput").placeholder = spec.model || "";
    $("apiKeyInput").disabled = name === "ollama";
    $("apiKeyInput").placeholder = name === "ollama" ? "Not needed for local Ollama" : "Paste your API key";
    $("keyHint").textContent = name === "ollama" ? "not needed for local Ollama" : "required for hosted APIs";
    // The Show/Hide button stays usable so a visible key can always be hidden again.
    if (name === "ollama") setKeyVisible(false);
  }

  function setKeyVisible(show) {
    $("apiKeyInput").type = show ? "text" : "password";
    $("toggleKeyBtn").textContent = show ? "Hide" : "Show";
    $("toggleKeyBtn").setAttribute("aria-pressed", String(show));
  }

  $("settingsBtn").addEventListener("click", () => {
    fillForm(loadSettings());
    $("settingsDialog").showModal();
    $("providerSelect").focus();
  });
  $("providerSelect").addEventListener("change", refreshProviderHints);
  $("toggleKeyBtn").addEventListener("click", () => setKeyVisible($("apiKeyInput").type === "password"));
  $("toggleGhBtn").addEventListener("click", () => {
    const input = $("githubTokenInput");
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    $("toggleGhBtn").textContent = show ? "Hide" : "Show";
    $("toggleGhBtn").setAttribute("aria-pressed", String(show));
  });
  $("clearGhBtn").addEventListener("click", () => {
    $("githubTokenInput").value = "";
    saveGithubToken("", $("rememberGh").checked);
    $("ghTestResult").dataset.state = "";
    $("ghTestResult").textContent = "Token removed from this browser.";
  });
  $("testGhBtn").addEventListener("click", async () => {
    const result = $("ghTestResult");
    const button = $("testGhBtn");
    result.dataset.state = "";
    result.textContent = "Checking the token…";
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    try {
      const data = await postJson("/api/github/test", { github_token: $("githubTokenInput").value.trim() });
      const source = { browser: "your token", server: "the server's token", none: "no token" }[data.source] || "no token";
      result.dataset.state = data.authenticated || data.source === "none" ? "ok" : "error";
      result.textContent = `Using ${source}: ${data.remaining} of ${data.limit} reads left this hour (resets in about ${data.resets_in_minutes} min).`;
    } catch (error) {
      result.dataset.state = "error";
      result.textContent = error.message;
    } finally {
      button.disabled = false;
      button.removeAttribute("aria-busy");
    }
  });
  $("settingsForm").addEventListener("submit", event => {
    const choice = event.submitter?.value;
    if (choice === "save") {
      saveSettings(readForm());
      saveGithubToken($("githubTokenInput").value.trim(), $("rememberGh").checked);
    }
    $("githubTokenInput").value = "";
    $("githubTokenInput").type = "password";
    setKeyVisible(false);
    $("settingsDialog").close(choice === "save" ? "save" : "cancel");
    refreshStatus();
  });
  $("testBtn").addEventListener("click", async () => {
    const result = $("testResult");
    const button = $("testBtn");
    result.dataset.state = "";
    result.textContent = "Testing the connection…";
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    try {
      const data = await postJson("/api/settings/test", { ai: readForm() });
      result.dataset.state = "ok";
      result.textContent = `Connected. Model ${data.model} responded.`;
    } catch (error) {
      result.dataset.state = "error";
      result.textContent = error.message;
    } finally {
      button.disabled = false;
      button.removeAttribute("aria-busy");
    }
  });
  $("resetBtn").addEventListener("click", () => {
    fillForm({ ...DEFAULTS });
    $("testResult").textContent = "Switched to the local model. Save to apply.";
  });

  // ---------- clipboard ----------
  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      const area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      let ok = false;
      try { ok = document.execCommand("copy"); } catch { ok = false; }
      area.remove();
      return ok;
    }
  }

  const COPY_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';

  // ---------- minimal, safe Markdown renderer ----------
  // Every character is HTML-escaped before Markdown rules run, so pasted or AI text cannot inject markup.
  function escapeText(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function safeUrl(url) {
    const clean = url.replace(/&amp;/g, "&").trim();
    return /^(javascript|data|vbscript):/i.test(clean) ? "#" : escapeText(clean);
  }
  function renderInline(text) {
    const codes = [];
    let t = text.replace(/`([^`]+)`/g, (_, code) => { codes.push(`<code>${escapeText(code)}</code>`); return `\u0000${codes.length - 1}\u0000`; });
    t = escapeText(t);
    t = t.replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, (_, alt, url) => `<img alt="${alt}" src="${safeUrl(url)}" loading="lazy">`);
    t = t.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, label, url) => `<a href="${safeUrl(url)}" target="_blank" rel="noopener noreferrer">${label}</a>`);
    t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    t = t.replace(/(^|[\s(])_([^_]+)_/g, "$1<em>$2</em>");
    t = t.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    return t.replace(/\u0000(\d+)\u0000/g, (_, i) => codes[Number(i)]);
  }
  function codeBlock(lang, code) {
    return `<div class="codeblock"><div class="codebar"><span>${escapeText(lang || "text")}</span>` +
      `<button type="button" class="copy-btn" data-copy-btn aria-label="Copy ${escapeText(lang || "code")} to clipboard">${COPY_ICON}<span>Copy</span></button></div>` +
      `<pre><code>${escapeText(code)}</code></pre></div>`;
  }
  function renderMarkdown(src) {
    const lines = String(src).replace(/\r\n?/g, "\n").split("\n");
    const listItem = /^\s*([-*+]|\d+\.)\s+/;
    const tableRow = /^\s*\|.*\|\s*$/;
    const tableSep = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;
    const cells = row => row.trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim());
    let html = "";
    let para = [];
    let centered = 0;
    const flush = () => { if (para.length) { html += `<p>${renderInline(para.join(" "))}</p>`; para = []; } };
    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      const fence = line.match(/^```\s*([\w+.-]*)/);
      if (fence) {
        flush();
        const code = [];
        i++;
        while (i < lines.length && !/^```/.test(lines[i])) { code.push(lines[i]); i++; }
        i++;
        html += codeBlock(fence[1], code.join("\n"));
        continue;
      }
      // Only two pieces of raw HTML are understood, because READMEs use them for a centered header:
      // <div align="center"> ... </div>, and a single <img src width alt> line. Everything else stays escaped text.
      if (/^\s*<div\s+align=["']center["']\s*>\s*$/i.test(line)) { flush(); html += '<div class="md-center">'; centered++; i++; continue; }
      if (/^\s*<\/div>\s*$/i.test(line)) { flush(); if (centered > 0) { html += "</div>"; centered--; } i++; continue; }
      const rawImg = line.match(/^\s*<img\s+([^>]*)>\s*$/i);
      if (rawImg) {
        flush();
        const attr = name => (rawImg[1].match(new RegExp(name + '=["\']([^"\']*)["\']', "i")) || [])[1] || "";
        const width = Math.min(Math.max(parseInt(attr("width"), 10) || 0, 0), 600);
        html += `<p><img alt="${escapeText(attr("alt"))}" src="${safeUrl(escapeText(attr("src")))}"${width ? ` width="${width}"` : ""} loading="lazy"></p>`;
        i++;
        continue;
      }
      const heading = line.match(/^(#{1,6})\s+(.*)$/);
      if (heading) {
        flush();
        const level = heading[1].length;
        html += `<h${level}>${renderInline(heading[2].replace(/\s+#+\s*$/, ""))}</h${level}>`;
        i++;
        continue;
      }
      if (tableRow.test(line) && i + 1 < lines.length && tableSep.test(lines[i + 1])) {
        flush();
        const head = cells(line);
        i += 2;
        let body = "";
        while (i < lines.length && tableRow.test(lines[i])) {
          body += "<tr>" + cells(lines[i]).map(c => `<td>${renderInline(c)}</td>`).join("") + "</tr>";
          i++;
        }
        html += `<table><thead><tr>${head.map(c => `<th>${renderInline(c)}</th>`).join("")}</tr></thead><tbody>${body}</tbody></table>`;
        continue;
      }
      if (listItem.test(line)) {
        flush();
        const tag = /^\s*\d+\./.test(line) ? "ol" : "ul";
        const items = [];
        while (i < lines.length && listItem.test(lines[i])) { items.push(lines[i].replace(listItem, "")); i++; }
        html += `<${tag}>${items.map(item => `<li>${renderInline(item)}</li>`).join("")}</${tag}>`;
        continue;
      }
      if (/^>\s?/.test(line)) {
        flush();
        const quote = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) { quote.push(lines[i].replace(/^>\s?/, "")); i++; }
        html += `<blockquote><p>${renderInline(quote.join(" "))}</p></blockquote>`;
        continue;
      }
      if (/^\s*(---+|\*\*\*+)\s*$/.test(line)) { flush(); html += "<hr>"; i++; continue; }
      if (line.trim() === "") { flush(); i++; continue; }
      para.push(line.trim());
      i++;
    }
    flush();
    while (centered-- > 0) html += "</div>";
    return html;
  }

  // ---------- loading animation ----------
  // Plays static/loader.json with lottie-web when it is available, and falls back to a CSS version of the same dots.
  const LOADER_STEPS = ["Reading the repository…", "Analyzing the project files…", "Writing your README…"];
  let loaderAnim = null;
  let loaderTimer = null;

  function stopLoader() {
    clearInterval(loaderTimer);
    loaderTimer = null;
    if (loaderAnim) { try { loaderAnim.destroy(); } catch { /* ignore */ } loaderAnim = null; }
  }

  function showLoader(slow) {
    stopLoader();
    const preview = $("readmePreview");
    preview.innerHTML =
      '<div class="loader-state" role="status" aria-live="polite">' +
      '<div class="loader-art" id="loaderArt"><div class="dots-fallback" aria-hidden="true"><i></i><i></i><i></i><i></i></div></div>' +
      '<p class="loader-title" id="loaderTitle"></p>' +
      `<p class="loader-sub">${escapeHtml(slow)}</p></div>`;
    preview.scrollTop = 0;
    const title = $("loaderTitle");
    let step = 0;
    const setStep = () => {
      title.classList.remove("in");
      void title.offsetWidth;
      title.textContent = LOADER_STEPS[Math.min(step, LOADER_STEPS.length - 1)];
      title.classList.add("in");
      step++;
    };
    setStep();
    loaderTimer = setInterval(setStep, 3500);
    const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (window.lottie && !reduce) {
      try {
        loaderAnim = window.lottie.loadAnimation({
          container: $("loaderArt"), renderer: "svg", loop: true, autoplay: true,
          path: document.body.dataset.loaderSrc,
          // The dots span x 171-505 and y 207-390 over one loop (measured from loader.json), so the view box adds a margin on every side.
          rendererSettings: { viewBoxSize: "128 168 420 262", preserveAspectRatio: "xMidYMid meet", progressiveLoad: false }
        });
        loaderAnim.addEventListener("DOMLoaded", () => $("loaderArt")?.classList.add("lottie-on"));
      } catch { /* keep CSS fallback */ }
    }
  }

  function renderPreview(markdown) {
    const preview = $("readmePreview");
    stopLoader();
    if (!markdown.trim()) {
      preview.innerHTML = '<div class="empty-state"><p class="empty-title">Your README will appear here.</p><p>Add a GitHub link or some notes, then select Generate README. Commands in the result get a Copy button.</p></div>';
      return;
    }
    preview.innerHTML = renderMarkdown(markdown);
    preview.classList.remove("just-rendered"); void preview.offsetWidth; preview.classList.add("just-rendered");
    preview.scrollTop = 0;
  }

  // One listener handles every Copy button, including ones rendered later.
  $("readmePreview").addEventListener("click", async event => {
    const button = event.target.closest("[data-copy-btn]");
    if (!button) return;
    const code = button.closest(".codeblock")?.querySelector("code")?.textContent || "";
    const ok = await copyText(code);
    const label = button.querySelector("span");
    button.dataset.copied = String(ok);
    label.textContent = ok ? "Copied" : "Failed";
    setTimeout(() => { button.dataset.copied = "false"; label.textContent = "Copy"; }, 1400);
  });

  function setOutputView(view) {
    const preview = view === "preview";
    $("readmePreview").hidden = !preview;
    $("generated").hidden = preview;
    $("previewTab").classList.toggle("active", preview);
    $("codeTab").classList.toggle("active", !preview);
    $("previewTab").setAttribute("aria-selected", String(preview));
    $("codeTab").setAttribute("aria-selected", String(!preview));
  }
  $("previewTab").addEventListener("click", () => setOutputView("preview"));
  $("codeTab").addEventListener("click", () => setOutputView("source"));

  function showNotice(message) {
    $("aiNotice").hidden = !message;
    $("aiNotice").textContent = message || "";
  }

  function setIndexChip(analysis) {
    const files = analysis.file_count;
    const folders = analysis.folder_count;
    if (!files) { $("indexChip").hidden = true; return; }
    $("indexText").textContent = `${files} files indexed across ${folders} folders`;
    $("indexChip").hidden = false;
  }

  function renderAnalysis(analysis) {
    const rows = [];
    const add = (label, value) => {
      if (value) rows.push(`<div class="analysis-row"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`);
    };
    add("Written by", analysis.generator_label);
    add("Languages", (analysis.languages || []).join(", "));
    add("Frameworks", (analysis.frameworks || []).join(", "));
    add("Detected features", (analysis.features || []).join(" · "));
    add("Sections added", (analysis.sections_added || []).join(", ") || "None. The README already had every section.");
    add("Badges", String(analysis.badge_count ?? 0));
    $("analysisList").innerHTML = rows.join("");
    $("analysisPanel").hidden = false;
  }

  function hideAnalysis() {
    $("analysisList").innerHTML = "";
    $("analysisPanel").hidden = true;
  }

  async function generate() {
    const repoUrl = $("repoUrl").value.trim();
    const readmeText = $("readmeInput").value.trim();
    if (!repoUrl && !readmeText) {
      $("repoUrl").focus();
      return alert("Enter a public GitHub repository URL or add project notes first.");
    }
    const button = $("generateBtn");
    const label = button.querySelector("span");
    button.disabled = true;
    label.textContent = "Generating…";
    button.setAttribute("aria-busy", "true");
    showNotice("");
    $("generatorLine").textContent = "Working on it…";
    $("indexChip").hidden = true;
    showLoader("A local model can take a minute on a slow computer.");
    setOutputView("preview");
    try {
      const data = await postJson("/api/generate", {
        repo_url: repoUrl,
        readme_text: readmeText,
        use_ai: $("useAi").checked,
        ai: loadSettings(),
        github_token: loadGithubToken()
      });
      $("generated").value = data.readme;
      renderPreview(data.readme);
      $("generatorLine").textContent = data.analysis.generator_label || "README generated";
      showNotice(data.analysis.ai_status || "");
      setIndexChip(data.analysis);
      renderAnalysis(data.analysis || {});
    } catch (error) {
      renderPreview("");
      $("generatorLine").textContent = "Generation failed";
      showNotice(error.message);
      hideAnalysis();
    } finally {
      button.disabled = false;
      button.removeAttribute("aria-busy");
      label.textContent = "Generate README";
    }
  }

  $("generateBtn").addEventListener("click", generate);
  $("repoUrl").addEventListener("keydown", event => { if (event.key === "Enter") generate(); });
  $("clearRepo").addEventListener("click", () => { $("repoUrl").value = ""; $("repoUrl").focus(); });

  $("clearBtn").addEventListener("click", () => {
    $("repoUrl").value = "";
    $("readmeInput").value = "";
    $("generated").value = "";
    $("generatorLine").textContent = "Waiting for a project";
    $("indexChip").hidden = true;
    showNotice("");
    hideAnalysis();
    renderPreview("");
    setOutputView("preview");
  });

  $("copyBtn").addEventListener("click", async () => {
    const content = $("generated").value;
    if (!content) return alert("Generate a README first.");
    const ok = await copyText(content);
    const label = $("copyBtn").querySelector("span");
    label.textContent = ok ? "Copied" : "Failed";
    setTimeout(() => { label.textContent = "Copy"; }, 1400);
  });

  $("downloadBtn").addEventListener("click", () => {
    const content = $("generated").value;
    if (!content) return alert("Generate a README first.");
    const url = URL.createObjectURL(new Blob([content], { type: "text/markdown;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "README.md";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  });

  // ---------- startup ----------
  fillProviderSelect();
  fetch("/api/providers").then(r => r.json()).then(data => {
    providers = data;
    fillProviderSelect();
    refreshProviderHints();
  }).catch(() => { /* keep built-in defaults */ });
  refreshStatus();
})();

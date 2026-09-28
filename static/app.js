/* VisionAI frontend — vanilla JS, no framework. */
(() => {
  const $ = (id) => document.getElementById(id);
  const dropzone = $("dropzone"), fileInput = $("fileInput"), browseBtn = $("browseBtn");
  const dzEmpty = $("dzEmpty"), dzPreview = $("dzPreview");
  const previewImg = $("previewImg"), fileName = $("fileName"), fileDetails = $("fileDetails");
  const fileMeta = $("fileMeta"), fileError = $("fileError");
  const question = $("question"), charCount = $("charCount"), askError = $("askError");
  const analyzeBtn = $("analyzeBtn"), btnSpinner = $("btnSpinner"), clearBtn = $("clearBtn");
  const statusDot = $("statusDot"), statusText = $("statusText"), apiStatus = $("apiStatus");
  const resultEmpty = $("resultEmpty"), resultLoading = $("resultLoading");
  const resultError = $("resultError"), errorText = $("errorText");
  const resultBody = $("resultBody"), copyBtn = $("copyBtn"), modelTag = $("modelTag");
  const retryBtn = $("retryBtn"), removeBtn = $("removeBtn");

  const MAX_MB = 10;
  const ALLOWED = ["image/jpeg", "image/png", "image/webp", "image/gif"];
  let objectUrl = null;
  let lastAnswer = "";

  /* ---------- status ---------- */
  async function loadStatus() {
    apiStatus.classList.add("checking");
    try {
      const r = await fetch("/api/status");
      const d = await r.json();
      apiStatus.classList.remove("checking");
      if (d.configured) {
        apiStatus.classList.add("ok");
        statusText.textContent = "API connected · " + (d.model || "ready");
        statusText.title = d.message || "";
      } else {
        apiStatus.classList.add("bad");
        statusText.textContent = "API key missing — see README";
        statusText.title = d.message || "Add GROQ_API_KEY to .env";
      }
    } catch {
      apiStatus.classList.remove("checking");
      apiStatus.classList.add("bad");
      statusText.textContent = "Server unreachable";
    }
  }

  /* ---------- helpers ---------- */
  function show(el) { el.hidden = false; }
  function hide(el) { el.hidden = true; }
  function setFileError(msg) {
    if (!msg) { hide(fileError); fileError.textContent = ""; return; }
    fileError.textContent = msg; show(fileError);
  }
  function setAskError(msg) {
    if (!msg) { hide(askError); askError.textContent = ""; return; }
    askError.textContent = msg; show(askError);
  }
  function showState(which) {
    [resultEmpty, resultLoading, resultError, resultBody].forEach(hide);
    if (which === "empty") show(resultEmpty);
    if (which === "loading") show(resultLoading);
    if (which === "error") show(resultError);
    if (which === "body") show(resultBody);
  }
  function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function renderMarkdownLite(text) {
    // Minimal safe renderer: paragraphs, bullets, bold, inline code.
    const lines = escapeHtml(text).split("\n");
    let html = "", inList = false;
    for (const line of lines) {
      const t = line.trim();
      if (/^([-*•]\s+)/.test(t)) {
        if (!inList) { html += "<ul>"; inList = true; }
        html += "<li>" + t.replace(/^([-*•]\s+)/, "") + "</li>";
      } else if (/^\d+\.\s+/.test(t)) {
        if (!inList) { html += "<ul>"; inList = true; }
        html += "<li>" + t.replace(/^\d+\.\s+/, "") + "</li>";
      } else {
        if (inList) { html += "</ul>"; inList = false; }
        if (t === "") html += "<br>";
        else html += "<p style='margin:.4em 0'>" + t + "</p>";
      }
    }
    if (inList) html += "</ul>";
    return html
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`(.+?)`/g, "<code>$1</code>");
  }

  function updateCount() { charCount.textContent = question.value.length + " / 2000"; }

  function setFile(file) {
    setFileError("");
    if (!file) return;
    if (!ALLOWED.includes(file.type) && !/\.(jpe?g|png|webp|gif)$/i.test(file.name)) {
      setFileError("Unsupported file type '" + file.name + "'. Please upload a JPG, PNG, WEBP or GIF image.");
      return;
    }
    const mb = file.size / (1024 * 1024);
    if (mb > MAX_MB) {
      setFileError("Image is too large (" + mb.toFixed(1) + "MB — limit is " + MAX_MB + "MB). Please choose a smaller file.");
      return;
    }
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = URL.createObjectURL(file);
    previewImg.src = objectUrl;
    // stash the File object for upload
    previewImg._file = file;
    fileName.textContent = file.name;
    fileDetails.textContent = mb.toFixed(2) + " MB · " + (file.type || "image");
    fileMeta.textContent = file.name + " (" + mb.toFixed(2) + " MB)";
    hide(dzEmpty); show(dzPreview);
  }

  function clearAll() {
    fileInput.value = "";
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = null; previewImg.src = ""; previewImg._file = null;
    show(dzEmpty); hide(dzPreview);
    fileName.textContent = ""; fileDetails.textContent = "—";
    fileMeta.textContent = "No file selected";
    question.value = "Describe this image in detail.";
    updateCount(); setFileError(""); setAskError("");
    lastAnswer = ""; copyBtn.disabled = true; hide(modelTag);
    showState("empty");
  }

  /* ---------- events ---------- */
  browseBtn.addEventListener("click", (e) => { e.stopPropagation(); fileInput.click(); });
  dropzone.addEventListener("click", (e) => {
    if (e.target.closest("button") && e.target.id !== "dropzone") return;
    if (!dzPreview.hidden) return; // clicking preview shouldn't reopen unless intended
    fileInput.click();
  });
  dropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); }
  });
  fileInput.addEventListener("change", () => { if (fileInput.files[0]) setFile(fileInput.files[0]); });
  ["dragenter", "dragover"].forEach((ev) => dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) => dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove("drag"); }));
  dropzone.addEventListener("drop", (e) => {
    const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) setFile(f);
  });
  removeBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    fileInput.value = "";
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = null; previewImg.src = ""; previewImg._file = null;
    show(dzEmpty); hide(dzPreview);
    fileMeta.textContent = "No file selected"; setFileError("");
  });

  question.addEventListener("input", () => { updateCount(); setAskError(""); });
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => { question.value = chip.dataset.q; updateCount(); question.focus(); });
  });
  clearBtn.addEventListener("click", clearAll);
  retryBtn.addEventListener("click", () => analyzeBtn.click());

  copyBtn.addEventListener("click", async () => {
    if (!lastAnswer) return;
    try {
      await navigator.clipboard.writeText(lastAnswer);
      copyBtn.textContent = "✓ Copied";
      setTimeout(() => { copyBtn.textContent = "⧉ Copy"; }, 1600);
    } catch {
      // Fallback for non-HTTPS contexts
      const ta = document.createElement("textarea");
      ta.value = lastAnswer; document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); copyBtn.textContent = "✓ Copied"; } catch {}
      ta.remove();
      setTimeout(() => { copyBtn.textContent = "⧉ Copy"; }, 1600);
    }
  });

  async function analyze() {
    setFileError(""); setAskError("");
    const file = previewImg._file || fileInput.files[0];
    const q = question.value.trim();
    if (!file) { setFileError("Please upload an image first."); return; }
    if (!q) { setAskError("Please type a question about the image before analyzing."); question.focus(); return; }

    analyzeBtn.disabled = true; show(btnSpinner);
    document.querySelector(".btn-label").textContent = "Analyzing…";
    showState("loading"); copyBtn.disabled = true;

    try {
      const form = new FormData();
      form.append("image", file, file.name);
      form.append("question", q);
      const res = await fetch("/api/analyze", { method: "POST", body: form });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        errorText.textContent = data.error || ("Request failed (HTTP " + res.status + "). Please try again.");
        showState("error");
        return;
      }
      lastAnswer = data.answer || "";
      resultBody.innerHTML = renderMarkdownLite(lastAnswer);
      if (data.model) { modelTag.textContent = "◈ " + data.model; show(modelTag); }
      copyBtn.disabled = !lastAnswer;
      showState("body");
    } catch {
      errorText.textContent = "Could not reach the server. Make sure the app is running (uvicorn app:app) and try again.";
      showState("error");
    } finally {
      analyzeBtn.disabled = false; hide(btnSpinner);
      document.querySelector(".btn-label").innerHTML = "✦ &nbsp;Analyze image";
    }
  }
  analyzeBtn.addEventListener("click", analyze);

  /* ---------- init ---------- */
  updateCount();
  loadStatus();
})();

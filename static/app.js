"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const pageSize = 6;
  const state = { config: null, busy: false, image: null, results: [], page: 1, objectUrl: null };
  const motion = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";

  function showError(message) {
    $("error-message").textContent = message;
    $("error-message").hidden = false;
    $("error-message").scrollIntoView({ behavior: motion, block: "nearest" });
  }
  function clearError() { $("error-message").hidden = true; }
  function setBusy(busy) {
    state.busy = busy;
    $("generate-button").disabled = busy || !state.config || !$("prompt").value.trim();
    $("search-button").disabled = busy || !state.config || !state.image;
    $("drop-zone").disabled = busy || !state.config;
    $("image-file").disabled = busy || !state.config;
    $("clear-image").disabled = busy;
    $("prompt").disabled = busy;
    document.querySelectorAll(".example-chip").forEach((button) => { button.disabled = busy; });
  }
  function countPrompt() {
    $("prompt-count").textContent = `${$("prompt").value.length.toLocaleString()} / 1,500`;
    setBusy(state.busy);
  }
  function startTimer(id) {
    const started = performance.now();
    const update = () => { $(id).textContent = `${((performance.now() - started) / 1000).toFixed(1)}s`; };
    update();
    const interval = setInterval(update, 100);
    return () => { clearInterval(interval); update(); };
  }
  function xsrfToken() {
    const cookie = document.cookie.split("; ").find((value) => value.startsWith("_xsrf="));
    return cookie ? decodeURIComponent(cookie.slice(6)) : "";
  }
  async function request(path, body) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), path.endsWith("text-to-image") ? 300000 : 120000);
    try {
      const response = await fetch(path, {
        method: "POST", credentials: "same-origin", signal: controller.signal,
        headers: { "Content-Type": "application/json", "X-XSRFToken": xsrfToken() },
        body: JSON.stringify(body),
      });
      let data;
      try { data = await response.json(); }
      catch { throw new Error("The server returned an unreadable response. Check that it is still running."); }
      if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
      return data;
    } catch (error) {
      if (error.name === "AbortError") throw new Error("This request timed out. The server may still be working; wait a moment before retrying.");
      if (error instanceof TypeError) throw new Error("Could not reach the server. Check your connection and try again.");
      throw error;
    } finally { clearTimeout(timeout); }
  }
  function resetResults() {
    state.results = [];
    state.page = 1;
    $("results-grid").replaceChildren();
    $("results-section").hidden = true;
    $("pagination").hidden = true;
    $("empty-results").hidden = true;
  }
  function releaseObjectUrl() {
    if (state.objectUrl) URL.revokeObjectURL(state.objectUrl);
    state.objectUrl = null;
  }
  async function selectImage(url, caption, filename) {
    const image = new Image();
    image.src = url;
    try { await image.decode(); }
    catch { throw new Error("This image could not be opened. Try a PNG, JPG, or WebP file."); }
    if (image.naturalWidth * image.naturalHeight > 25000000) throw new Error("Please use an image smaller than 25 megapixels.");
    state.image = image;
    $("preview-image").src = url;
    $("preview-image").alt = caption;
    $("preview-image").hidden = false;
    $("empty-preview").hidden = true;
    $("image-caption").textContent = caption;
    $("download-image").href = url;
    $("download-image").download = filename;
    $("download-image").hidden = false;
    $("clear-image").hidden = false;
    resetResults();
  }
  function imagePayload() {
    if (!state.image) throw new Error("Choose an image before searching.");
    // Normalize both the SVG demo fixture and uploaded/generated images for the API.
    const canvas = document.createElement("canvas");
    const scale = Math.min(1, 1600 / Math.max(state.image.naturalWidth, state.image.naturalHeight));
    canvas.width = Math.max(1, Math.round(state.image.naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(state.image.naturalHeight * scale));
    const context = canvas.getContext("2d");
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(state.image, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.92);
  }

  $("generate-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.busy || !state.config) return;
    const prompt = $("prompt").value.trim();
    if (!prompt) { $("prompt").focus(); return; }
    clearError();
    setBusy(true);
    $("generation-loading").hidden = false;
    $("image-stage").setAttribute("aria-busy", "true");
    $("generate-label").textContent = "Generating…";
    const stop = startTimer("generation-timer");
    try {
      const data = await request("/api/text-to-image", { prompt });
      const demo = data.mode === "demo";
      const caption = demo ? "Demo image · fixed sneaker illustration" : `Generated in ${data.elapsed_seconds.toFixed(1)}s · seed ${data.seed}`;
      await selectImage(data.image_url, caption, demo ? "fashiongen-demo.svg" : "fashiongen-concept.png");
      releaseObjectUrl();
      $("file-caption").textContent = "";
      $("image-file").value = "";
    } catch (error) { showError(error.message); }
    finally {
      stop();
      $("generation-loading").hidden = true;
      $("image-stage").setAttribute("aria-busy", "false");
      $("generate-label").textContent = "Generate and Search";
      setBusy(false);
    }
  });

  async function acceptFile(file) {
    if (!file || state.busy || !state.config) return;
    clearError();
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
      showError("Choose a PNG, JPG, or WebP image."); return;
    }
    if (file.size > state.config.max_upload_bytes || !file.size) {
      showError("Images must be nonempty and 10 MB or smaller."); return;
    }
    const url = URL.createObjectURL(file);
    setBusy(true);
    try {
      await selectImage(url, "Uploaded image · ready to search", file.name);
      releaseObjectUrl();
      state.objectUrl = url;
      $("file-caption").textContent = file.name;
    } catch (error) { URL.revokeObjectURL(url); showError(error.message); }
    finally { setBusy(false); }
  }
  $("drop-zone").addEventListener("click", () => $("image-file").click());
  $("image-file").addEventListener("change", (event) => acceptFile(event.target.files[0]));
  ["dragenter", "dragover"].forEach((type) => $("drop-zone").addEventListener(type, (event) => {
    event.preventDefault();
    if (!state.busy) $("drop-zone").classList.add("dragging");
  }));
  ["dragleave", "drop"].forEach((type) => $("drop-zone").addEventListener(type, (event) => {
    event.preventDefault();
    $("drop-zone").classList.remove("dragging");
  }));
  $("drop-zone").addEventListener("drop", (event) => {
    if (event.dataTransfer.files.length > 1) { showError("Choose one image at a time."); return; }
    acceptFile(event.dataTransfer.files[0]);
  });
  // Dropping a file elsewhere should not replace the app with a browser image tab.
  window.addEventListener("dragover", (event) => event.preventDefault());
  window.addEventListener("drop", (event) => event.preventDefault());
  $("clear-image").addEventListener("click", () => {
    if (state.busy) return;
    releaseObjectUrl();
    state.image = null;
    $("preview-image").removeAttribute("src");
    $("preview-image").hidden = true;
    $("empty-preview").hidden = false;
    $("download-image").hidden = true;
    $("download-image").removeAttribute("href");
    $("clear-image").hidden = true;
    $("file-caption").textContent = "";
    $("image-file").value = "";
    $("image-caption").textContent = "Your image will appear here";
    resetResults();
    clearError();
    setBusy(false);
  });

  function element(tag, className, text) {
    const node = document.createElement(tag);
    node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function resultCard(item) {
    const card = element("article", "result-card");
    const media = element("div", "result-image-wrap");
    const image = element("img", "result-image");
    image.src = item.thumbnail || "/static/assets/image-placeholder.svg";
    image.alt = item.title;
    image.loading = "lazy";
    image.referrerPolicy = "no-referrer";
    image.addEventListener("error", () => { image.src = "/static/assets/image-placeholder.svg"; }, { once: true });
    media.append(image);
    if (item.premium) {
      const badge = element("span", "premium-badge", "✧ Premium");
      badge.title = "Above-average image resolution in this result set; not a product-quality rating.";
      media.append(badge);
    }
    const body = element("div", "result-body");
    body.append(element("p", "result-source", item.source), element("h3", "result-title", item.title));
    if (item.price) body.append(element("p", "result-price", item.price));
    const link = element("a", "view-item");
    link.href = item.link;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.append(element("span", "", "View item"), element("span", "", "↗"));
    link.setAttribute("aria-label", `View item: ${item.title} (opens a new tab)`);
    body.append(link);
    if (item.demo) body.append(element("p", "demo-link-note", "Demo link · opens a web search"));
    card.append(media, body);
    return card;
  }
  function renderPage(scroll = false) {
    const pageCount = Math.ceil(state.results.length / pageSize);
    const from = (state.page - 1) * pageSize;
    $("results-grid").replaceChildren(...state.results.slice(from, from + pageSize).map(resultCard));
    $("pagination").hidden = pageCount <= 1;
    $("previous-page").disabled = state.page <= 1;
    $("next-page").disabled = state.page >= pageCount;
    $("page-indicator").textContent = `Page ${state.page} of ${Math.max(1, pageCount)}`;
    if (scroll) $("results-title").focus({ preventScroll: true });
    if (scroll) $("results-section").scrollIntoView({ behavior: motion, block: "start" });
  }
  $("previous-page").addEventListener("click", () => { if (state.page > 1) { state.page--; renderPage(true); } });
  $("next-page").addEventListener("click", () => {
    if (state.page < Math.ceil(state.results.length / pageSize)) { state.page++; renderPage(true); }
  });
  $("search-button").addEventListener("click", async () => {
    if (state.busy || !state.image) return;
    clearError();
    resetResults();
    setBusy(true);
    $("results-section").hidden = false;
    $("search-progress").hidden = false;
    $("results-grid").setAttribute("aria-busy", "true");
    $("search-label").textContent = "Searching…";
    $("results-summary").textContent = "Finding visual matches for your image.";
    $("results-label").textContent = state.config.search_mode === "demo" ? "Demo results" : "Google Lens";
    $("search-progress-copy").textContent = state.config.search_mode === "demo" ? "Loading the fixed demo collection." : "Uploading your image, then searching Google Lens.";
    $("results-section").scrollIntoView({ behavior: motion, block: "start" });
    const stop = startTimer("search-timer");
    try {
      const data = await request("/api/image-search", { image: imagePayload() });
      state.results = data.results;
      state.page = 1;
      const type = data.mode === "demo" ? "sample items" : "visual matches";
      $("results-summary").textContent = `${data.total} ${type} · ${data.elapsed_seconds.toFixed(1)}s`;
      $("results-note").textContent = data.mode === "demo"
        ? "Fixed sample results for every image, as in the demo. Premium uses sample resolution values; links open web searches."
        : "Premium highlights above-average image resolution when dimensions are available. It does not measure product quality or similarity.";
      $("empty-results").hidden = state.results.length !== 0;
      renderPage();
    } catch (error) {
      $("results-summary").textContent = "Search could not be completed. Try again using the button above.";
      showError(error.message);
    } finally {
      stop();
      $("search-progress").hidden = true;
      $("results-grid").setAttribute("aria-busy", "false");
      $("search-label").textContent = "Search for Similar Items";
      setBusy(false);
    }
  });
  document.querySelectorAll(".example-chip").forEach((button) => button.addEventListener("click", () => {
    $("prompt").value = button.dataset.prompt;
    countPrompt();
    $("prompt").focus();
  }));
  $("prompt").addEventListener("input", countPrompt);

  async function initialize() {
    try {
      const response = await fetch("/api/health", { signal: AbortSignal.timeout(10000) });
      if (!response.ok) throw new Error("The server is not ready. Refresh the page once it has started.");
      state.config = await response.json();
      const generationDemo = state.config.generation_mode === "demo";
      const searchDemo = state.config.search_mode === "demo";
      $("generation-mode").textContent = generationDemo ? "Demo generation" : "Stable Diffusion 3.5";
      $("generation-mode").classList.toggle("live", !generationDemo);
      $("search-mode").textContent = searchDemo ? "Demo search" : "Live visual search";
      $("search-mode").classList.toggle("live", !searchDemo);
      $("search-mode").hidden = false;
      const messages = [];
      if (generationDemo) messages.push("Demo generation shows a fixed sneaker illustration, regardless of the prompt.");
      if (searchDemo) messages.push("Demo search returns a fixed sample collection for every image.");
      $("demo-notice").hidden = !messages.length;
      $("demo-notice-text").textContent = messages.join(" ");
      const minutes = Math.round(state.config.upload_expiration_seconds / 60);
      $("search-disclosure").textContent = searchDemo
        ? "Demo search stays local. Your image is not sent to an image host or search service."
        : `Searching uploads your image to a public ImgBB URL, set to expire after ${minutes} minutes, and shares that URL with SerpAPI/Google Lens.`;
      setBusy(false);
    } catch (error) {
      $("generation-mode").textContent = "Server unavailable";
      showError(error.message || "Could not connect to the server. Refresh the page to retry.");
    }
  }
  countPrompt();
  initialize();
})();

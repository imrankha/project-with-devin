(() => {
  const REQUIRED = window.REQUIRED_READS || 25;
  const $ = (id) => document.getElementById(id);

  const els = {
    surah: $("surah-select"), ayah: $("ayah-select"),
    prev: $("prev-ayah"), next: $("next-ayah"),
    message: $("message"), placeholder: $("placeholder"), view: $("ayah-view"),
    ref: $("ayah-ref"), memorizedBadge: $("memorized-badge"),
    arabic: $("arabic-text"), audio: $("ayah-audio"), play: $("play-audio"),
    en: $("trans-english"), hi: $("trans-hindi"), ur: $("trans-urdu"),
    words: $("words"),
    counterRing: $("counter-ring"), counterValue: $("counter-value"),
    progressFill: $("progress-fill"), readBtn: $("read-btn"), resetBtn: $("reset-btn"),
    locked: $("recite-locked"), unlocked: $("recite-unlocked"), readsLeft: $("reads-left"),
    micBtn: $("mic-btn"), stopBtn: $("stop-btn"), toggleType: $("toggle-type"),
    micUnsupported: $("mic-unsupported"), live: $("live-transcript"),
    typeArea: $("type-area"), typed: $("typed-recitation"), checkTyped: $("check-typed"),
    result: $("result"), verdict: $("result-verdict"), score: $("result-score"),
    resultWords: $("result-words"), resultExtra: $("result-extra"), resultTranscript: $("result-transcript"),
  };

  const state = { surahs: [], current: null, recognition: null, listening: false, finalText: "" };

  function userId() {
    let id = localStorage.getItem("hifz-user-id");
    if (!id) {
      id = (crypto.randomUUID && crypto.randomUUID()) ||
        "u-" + Math.random().toString(36).slice(2) + Date.now().toString(36);
      localStorage.setItem("hifz-user-id", id);
    }
    return id;
  }

  async function api(path, options = {}) {
    const res = await fetch(path, {
      ...options,
      headers: { "Content-Type": "application/json", "X-User-Id": userId(), ...(options.headers || {}) },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(data.error || `Request failed (${res.status})`);
      err.data = data;
      throw err;
    }
    return data;
  }

  function showMessage(text) {
    els.message.textContent = text;
    els.message.classList.toggle("hidden", !text);
  }

  function currentSurah() {
    return state.surahs.find((s) => s.id === Number(els.surah.value));
  }

  async function loadSurahs() {
    try {
      state.surahs = await api("/api/surahs");
    } catch (e) {
      els.surah.innerHTML = '<option value="">Could not load surahs</option>';
      showMessage(e.message);
      return;
    }
    els.surah.innerHTML = '<option value="">— Select surah —</option>' + state.surahs
      .map((s) => `<option value="${s.id}">${s.id}. ${s.name} (${s.name_arabic}) – ${s.translated_name}</option>`)
      .join("");
    els.surah.disabled = false;

    const params = new URLSearchParams(location.search);
    const surah = Number(params.get("surah"));
    const ayah = Number(params.get("ayah"));
    if (state.surahs.some((s) => s.id === surah)) {
      els.surah.value = surah;
      fillAyahs();
      if (ayah >= 1 && ayah <= currentSurah().verses_count) {
        els.ayah.value = ayah;
        loadAyah();
      }
    }
  }

  function fillAyahs() {
    const s = currentSurah();
    if (!s) {
      els.ayah.innerHTML = '<option value="">Select a surah first</option>';
      els.ayah.disabled = true;
      return;
    }
    let opts = '<option value="">— Select ayah —</option>';
    for (let i = 1; i <= s.verses_count; i++) opts += `<option value="${i}">Ayah ${i}</option>`;
    els.ayah.innerHTML = opts;
    els.ayah.disabled = false;
  }

  function updateNav() {
    const s = currentSurah();
    const a = Number(els.ayah.value);
    els.prev.disabled = !s || !a || a <= 1;
    els.next.disabled = !s || !a || a >= s.verses_count;
  }

  function escapeHtml(str) {
    return String(str ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  async function loadAyah() {
    const surah = Number(els.surah.value);
    const ayah = Number(els.ayah.value);
    updateNav();
    stopListening(true);
    if (!surah || !ayah) {
      els.view.classList.add("hidden");
      els.placeholder.classList.remove("hidden");
      return;
    }
    history.replaceState(null, "", `?surah=${surah}&ayah=${ayah}`);
    showMessage("");
    els.placeholder.classList.remove("hidden");
    els.placeholder.innerHTML = "<p>Loading ayah…</p>";
    els.view.classList.add("hidden");
    try {
      const data = await api(`/api/ayah/${surah}/${ayah}`);
      // Ignore stale responses if the user changed the selection meanwhile.
      if (Number(els.surah.value) !== surah || Number(els.ayah.value) !== ayah) return;
      state.current = data;
      renderAyah(data);
    } catch (e) {
      els.placeholder.innerHTML = "<p>Select a surah and an ayah to begin memorizing.</p>";
      showMessage(e.message);
    }
  }

  function renderAyah(data) {
    const s = currentSurah();
    els.ref.textContent = `${s.name} ${data.verse_key}`;
    els.arabic.textContent = data.arabic;
    els.arabic.classList.remove("concealed");
    els.en.textContent = data.translations.english;
    els.hi.textContent = data.translations.hindi;
    els.ur.textContent = data.translations.urdu;
    els.audio.src = data.audio_url || "";
    els.play.disabled = !data.audio_url;

    els.words.innerHTML = data.words.map((w, i) => `
      <div class="word" data-index="${i}" title="Play word">
        <div class="w-ar" lang="ar">${escapeHtml(w.arabic)}</div>
        <div class="w-tr">${escapeHtml(w.transliteration)}</div>
        <div class="w-en">${escapeHtml(w.meaning.english)}</div>
        <div class="w-hi" lang="hi">${escapeHtml(w.meaning.hindi)}</div>
        <div class="w-ur" lang="ur">${escapeHtml(w.meaning.urdu)}</div>
      </div>`).join("");

    els.result.classList.add("hidden");
    els.live.classList.add("hidden");
    els.typed.value = "";
    renderProgress(data.progress);
    els.placeholder.classList.add("hidden");
    els.view.classList.remove("hidden");
  }

  function renderProgress(p) {
    const count = p.read_count;
    const pct = Math.min(100, (count / REQUIRED) * 100);
    els.counterValue.textContent = count;
    els.counterRing.style.setProperty("--pct", pct);
    els.counterRing.classList.toggle("complete", count >= REQUIRED);
    els.progressFill.style.width = pct + "%";
    els.memorizedBadge.classList.toggle("hidden", !p.memorized);
    els.locked.classList.toggle("hidden", p.can_recite);
    els.unlocked.classList.toggle("hidden", !p.can_recite);
    const left = Math.max(0, REQUIRED - count);
    els.readsLeft.textContent = left ? `${left} more to go.` : "";
    if (state.current) state.current.progress = p;
  }

  async function addRead() {
    if (!state.current) return;
    els.readBtn.disabled = true;
    try {
      const [surah, ayah] = state.current.verse_key.split(":");
      const p = await api(`/api/progress/${surah}/${ayah}/read`, { method: "POST" });
      renderProgress(p);
    } catch (e) {
      showMessage(e.message);
    } finally {
      els.readBtn.disabled = false;
    }
  }

  async function resetProgress() {
    if (!state.current || !confirm("Reset the reading counter and memorization status for this ayah?")) return;
    const [surah, ayah] = state.current.verse_key.split(":");
    try {
      renderProgress(await api(`/api/progress/${surah}/${ayah}/reset`, { method: "POST" }));
      els.result.classList.add("hidden");
      els.arabic.classList.remove("concealed");
    } catch (e) {
      showMessage(e.message);
    }
  }

  // ---- Recitation ----
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  function startListening() {
    if (!SpeechRecognition) {
      els.micUnsupported.classList.remove("hidden");
      els.typeArea.classList.remove("hidden");
      return;
    }
    const rec = new SpeechRecognition();
    rec.lang = "ar-SA";
    rec.continuous = true;
    rec.interimResults = true;
    state.recognition = rec;
    state.finalText = "";
    state.listening = true;

    rec.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const r = event.results[i];
        if (r.isFinal) state.finalText += " " + r[0].transcript;
        else interim += " " + r[0].transcript;
      }
      els.live.textContent = (state.finalText + " " + interim).trim() || "…";
    };
    rec.onerror = (event) => {
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        showMessage("Microphone access was blocked. Allow it in your browser, or type the ayah instead.");
        state.listening = false;
      } else if (event.error !== "no-speech" && event.error !== "aborted") {
        showMessage(`Speech recognition error: ${event.error}`);
      }
    };
    rec.onend = () => {
      // Chrome ends sessions after silence; keep listening until the user presses Stop.
      if (state.listening) {
        try { rec.start(); return; } catch (_) { /* fall through */ }
      }
      setListeningUI(false);
      if (state.submitOnEnd) {
        state.submitOnEnd = false;
        submitRecitation(state.finalText.trim());
      }
    };

    showMessage("");
    els.result.classList.add("hidden");
    els.live.textContent = "Listening…";
    els.live.classList.remove("hidden");
    els.arabic.classList.add("concealed");
    setListeningUI(true);
    rec.start();
  }

  function stopListening(discard = false) {
    if (!state.recognition) return;
    state.listening = false;
    state.submitOnEnd = !discard;
    if (discard) state.recognition.abort();
    else state.recognition.stop();
    state.recognition = discard ? null : state.recognition;
    if (discard) setListeningUI(false);
  }

  function setListeningUI(on) {
    els.micBtn.classList.toggle("hidden", on);
    els.stopBtn.classList.toggle("hidden", !on);
    els.toggleType.disabled = on;
  }

  async function submitRecitation(transcript) {
    if (!state.current) return;
    if (!transcript) {
      showMessage("No recitation was captured. Please try again and speak clearly.");
      els.arabic.classList.remove("concealed");
      return;
    }
    const [surah, ayah] = state.current.verse_key.split(":");
    try {
      const result = await api(`/api/recite/${surah}/${ayah}`, {
        method: "POST",
        body: JSON.stringify({ transcript }),
      });
      renderResult(result);
      renderProgress(result.progress);
    } catch (e) {
      showMessage(e.message);
      if (e.data && e.data.progress) renderProgress(e.data.progress);
    } finally {
      els.arabic.classList.remove("concealed");
    }
  }

  function renderResult(r) {
    const pct = Math.round(r.accuracy * 100);
    els.verdict.textContent = r.memorized ? "✔ Memorized" : "✘ Not memorized yet";
    els.verdict.className = "verdict " + (r.memorized ? "pass" : "fail");
    els.score.textContent = `${r.correct} of ${r.total} words correct (${pct}% accuracy).` +
      (r.memorized ? " Excellent, move on to the next ayah!" : " Words in red were missed or wrong – keep practising.");
    els.resultWords.innerHTML = state.current.words
      .map((w, i) => `<span class="${r.words[i]}">${escapeHtml(w.arabic)}</span>`)
      .join(" ");
    els.resultExtra.textContent = r.extra_words.length ? `Extra / unrecognised words: ${r.extra_words.join(" ")}` : "";
    els.resultTranscript.textContent = r.transcript;
    els.result.classList.remove("hidden");
    els.live.classList.add("hidden");
  }

  // ---- Events ----
  els.surah.addEventListener("change", () => {
    fillAyahs();
    if (currentSurah()) {
      els.ayah.value = "1";
    }
    loadAyah();
  });
  els.ayah.addEventListener("change", loadAyah);
  els.prev.addEventListener("click", () => { els.ayah.value = Number(els.ayah.value) - 1; loadAyah(); });
  els.next.addEventListener("click", () => { els.ayah.value = Number(els.ayah.value) + 1; loadAyah(); });
  els.play.addEventListener("click", () => {
    if (els.audio.paused) els.audio.play().catch((e) => showMessage("Could not play audio: " + e.message));
    else els.audio.pause();
  });
  els.audio.addEventListener("play", () => { els.play.innerHTML = "&#10074;&#10074; Pause"; });
  els.audio.addEventListener("pause", () => { els.play.innerHTML = "&#9654; Listen"; });
  els.words.addEventListener("click", (e) => {
    const card = e.target.closest(".word");
    if (!card || !state.current) return;
    const url = state.current.words[Number(card.dataset.index)].audio_url;
    if (url) new Audio(url).play().catch(() => {});
  });
  els.readBtn.addEventListener("click", addRead);
  els.resetBtn.addEventListener("click", resetProgress);
  els.micBtn.addEventListener("click", startListening);
  els.stopBtn.addEventListener("click", () => stopListening(false));
  els.toggleType.addEventListener("click", () => {
    const show = els.typeArea.classList.contains("hidden");
    els.typeArea.classList.toggle("hidden", !show);
    els.arabic.classList.toggle("concealed", show);
    els.toggleType.textContent = show ? "Hide typing" : "Type instead";
    if (show) els.typed.focus();
  });
  els.checkTyped.addEventListener("click", () => submitRecitation(els.typed.value.trim()));

  if (!SpeechRecognition) els.micUnsupported.classList.remove("hidden");
  loadSurahs();
})();

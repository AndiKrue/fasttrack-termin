// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Andreas Krueger
// Server speech through Meterless Nightshift, shared by the web UI and the Telegram mini app.
// Telegram's Android WebView exposes webkitSpeechRecognition without a working service and often has no
// TTS voice, so speech runs on the server when /config says speech: true:
//   Speak:      MediaRecorder -> decoded and resampled to 16 kHz mono WAV here -> POST /stt -> text
//   Read aloud: POST /tts -> MP3 -> one shared <audio> element
// Callers fall back to the browser Web Speech API whenever a server call fails. Nothing auto-plays.
"use strict";

const FTSpeech = (() => {
  let server = false;      // /config speech flag
  let ttsServer = true;    // false after /tts answered 503 once: read with the browser from then on
  let sttServer = true;    // false after /stt answered 503 once: the next Speak uses browser dictation
  let playing = 0;         // bumped by stop(): a /tts answer that arrives after Stop is not played
  const config = fetch("/config").then((r) => r.json()).then((c) => { server = !!c.speech; }).catch(() => {});
  const audio = new Audio();
  audio.preload = "none";
  const SILENCE = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA=";
  const canRecord = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  const MAX_MS = 30000;

  function toWav(buffer) {
    // Channel 0, linear resample to 16 kHz, 16-bit PCM: what whisper reads directly.
    const src = buffer.getChannelData(0), rate = 16000;
    const n = Math.floor(src.length * rate / buffer.sampleRate), step = buffer.sampleRate / rate;
    const view = new DataView(new ArrayBuffer(44 + n * 2));
    const str = (o, s) => { for (let i = 0; i < s.length; i++) view.setUint8(o + i, s.charCodeAt(i)); };
    str(0, "RIFF"); view.setUint32(4, 36 + n * 2, true); str(8, "WAVE"); str(12, "fmt ");
    view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
    view.setUint32(24, rate, true); view.setUint32(28, rate * 2, true); view.setUint16(32, 2, true);
    view.setUint16(34, 16, true); str(36, "data"); view.setUint32(40, n * 2, true);
    for (let i = 0; i < n; i++) {
      const p = i * step, j = Math.floor(p), f = p - j;
      const s = Math.max(-1, Math.min(1, (src[j] || 0) * (1 - f) + (src[j + 1] || 0) * f));
      view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    return new Blob([view], { type: "audio/wav" });
  }

  // Starts recording; resolves to {stop}. stop() (or the 30 s cap) ends it; `done` gets the text or an Error.
  async function record(lang, done) {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const type = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"].find((t) => MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(t));
    const rec = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
    const chunks = [];
    rec.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
    rec.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      try {
        const Ctx = window.AudioContext || window.webkitAudioContext;
        const ctx = new Ctx();
        const raw = await new Blob(chunks, { type: rec.mimeType || type || "audio/webm" }).arrayBuffer();
        const decoded = await new Promise((ok, fail) => ctx.decodeAudioData(raw, ok, fail));
        ctx.close && ctx.close();
        const r = await fetch("/stt", { method: "POST", headers: { "Content-Type": "audio/wav", "X-Speech-Lang": lang.slice(0, 2) }, body: toWav(decoded) });
        const d = await r.json().catch(() => ({}));
        if (r.status === 503) sttServer = false;
        if (!r.ok) throw Object.assign(new Error(d.error || "Transcription failed"), { status: r.status });
        done(d.text || "");
      } catch (e) {
        done(e instanceof Error ? e : new Error("Transcription failed"));
      }
    };
    rec.start();
    const timer = setTimeout(() => { if (rec.state === "recording") rec.stop(); }, MAX_MS);
    return { stop() { clearTimeout(timer); if (rec.state === "recording") rec.stop(); } };
  }

  // Call inside the click handler: unlocks playback (iOS needs play() within the gesture).
  function unlock() { audio.src = SILENCE; audio.play().catch(() => {}); }

  // Plays text through /tts. Resolves when playback ends; rejects when the server cannot speak.
  async function say(text) {
    const mine = ++playing;
    const r = await fetch("/tts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
    if (r.status === 503) ttsServer = false;
    if (!r.ok) throw new Error("tts " + r.status);
    const blob = await r.blob();
    if (mine !== playing) return; // stopped while the audio was on its way
    const url = URL.createObjectURL(blob);
    audio.src = url;
    await new Promise((ok, fail) => {
      audio.onended = ok; audio.onerror = () => fail(new Error("audio playback failed"));
      audio.play().catch(fail);
    });
    URL.revokeObjectURL(url);
  }

  function stop() { playing++; audio.onended = null; audio.onerror = null; audio.pause(); audio.removeAttribute("src"); }

  // getUserMedia / decode errors as short button text (the pattern of the Web Speech errors).
  function micError(e) {
    if (e && e.status) return e.status === 503 ? "Speech service unavailable, tap again" : "Transcription failed, try again";
    const name = e && e.name;
    if (name === "NotAllowedError" || name === "SecurityError") return "Microphone blocked: allow it in the settings";
    if (name === "NotFoundError") return "No microphone found";
    if (name === "EncodingError") return "Recording unreadable, try again";
    return "Speech error: " + ((e && e.message) || name || "unknown");
  }

  return {
    config,
    micError,
    canRecord,
    record,
    unlock,
    say,
    stop,
    sttOn: () => server && sttServer && canRecord,
    ttsOn: (text) => server && ttsServer && text.length <= 1500,
  };
})();

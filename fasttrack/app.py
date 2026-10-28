# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Andreas Krueger
"""One page on localhost: ask, then read the routes, the reasons and the evidence behind them."""

from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .env import load_env
from .agent import investigate
from .llm import Nemotron

STATIC = Path(__file__).resolve().parent / "static"
STT_TYPES = {"audio/wav", "audio/webm", "audio/ogg", "audio/mp4"}
STT_MAX_BYTES = 2 * 1024 * 1024
STT_MAX_SECONDS = 60
TTS_MAX_CHARS = 1500

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>FastTrack Termin</title>
<style>
body{font:16px/1.5 system-ui,sans-serif;max-width:860px;margin:2rem auto;padding:0 1rem;color:#1d2433}
textarea{width:100%;height:5rem;font:inherit;padding:.5rem}button{font:inherit;padding:.5rem 1rem;margin-top:.5rem}
.route{border:1px solid #c9d1e0;border-radius:8px;padding:1rem;margin:1rem 0}.days{font-weight:600}
code,pre{background:#f3f5f9;padding:.1rem .3rem;border-radius:4px}pre{white-space:pre-wrap;padding:.6rem}
.ev{font-size:.85rem;color:#4a5568}.muted{color:#6b7280;font-size:.9rem}
</style></head><body>
<h1>FastTrack Termin</h1>
<p class="muted">Statutory-insurance patients in Berlin: the fastest route to a specialist appointment, with the reasons and the evidence for each step. Not medical advice; in an emergency call 112.</p>
<textarea id="q">I live in Köpenick, have knee pain for three weeks and a referral from my GP without urgency code. How do I get an orthopaedics appointment fastest?</textarea>
<button id="go">Find the fastest route</button>
<div id="out"></div>
<script>
const out=document.getElementById('out');
function el(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e}
document.getElementById('go').onclick=async()=>{
  out.replaceChildren(el('p','Planning, querying the sources, verifying ...','muted'));
  const r=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:document.getElementById('q').value})});
  const d=await r.json();out.replaceChildren();
  if(d.error){out.append(el('p','Error: '+d.error));return}
  d.routes.forEach((x,i)=>{const b=el('div',undefined,'route');
    b.append(el('h3',(i+1)+'. '+x.route));
    if(x.expected_days!==null&&x.expected_days!==undefined)b.append(el('p','Expected: about '+x.expected_days+' days','days'));
    b.append(el('p','Why: '+x.why));
    x.evidence.forEach(e=>{const v=d.evidence[e];const pre=el('pre',e+'  '+v.sql+'\\n'+JSON.stringify(v.row),'ev');b.append(pre);if(v.url){const a=el('a',v.url);a.href=v.url;a.target='_blank';a.rel='noopener';b.append(a)}});
    out.append(b)});
  (d.caveats||[]).forEach(c=>out.append(el('p','Note: '+c,'muted')));
  const det=el('details');det.append(el('summary','Trace: plan, queries, web, verifier'));
  d.trace.steps.forEach(st=>det.append(el('pre',JSON.stringify(st,null,1),'ev')));out.append(det);
  out.append(el('p','Run '+d.run_id+' | source '+d.trace.source+' | web '+(d.trace.web||'off')+' | memory '+d.trace.memory+' | '+d.model_calls.length+' Nemotron calls','muted'));
};
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    llm = None

    def _send(self, status, body: bytes, ctype: str):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] == "/config":
            # The Maps Embed key goes to the browser by design (it sits in the iframe URL); it is
            # restricted to the Maps Embed API and our referrers. The request log line never has it.
            key = os.environ.get("GOOGLE_MAPS_EMBED_KEY", "")
            body = {"maps": True, "embed_key": key} if key else {"maps": False}
            body["speech"] = bool(os.environ.get("METERLESS_BASE_URL"))  # server speech through Nightshift
            self._send(200, json.dumps(body).encode(), "application/json")
            return
        # "/" -> static/index.html when present (UI run), else the built-in page; "/miniapp" -> static/miniapp.html
        name ={"/": "index.html", "/miniapp": "miniapp.html"}.get(self.path.split("?")[0])
        if name is None and self.path.startswith("/static/"):
            name = self.path[len("/static/"):].split("?")[0]
        if name is not None:
            path = (STATIC / name).resolve()
            if path.is_file() and path.is_relative_to(STATIC):
                ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                self._send(200, path.read_bytes(), ctype + ("; charset=utf-8" if ctype.startswith("text/") else ""))
                return
            if name == "index.html":
                self._send(200, PAGE.encode(), "text/html; charset=utf-8")
                return
        self.send_error(404)

    def _question(self) -> str:
        length = min(int(self.headers.get("Content-Length") or 0), 8192)
        return str(json.loads(self.rfile.read(length) or b"{}").get("question", ""))[:2000]

    def _json(self, status, obj):
        self._send(status, json.dumps(obj, ensure_ascii=False).encode(), "application/json")

    def _speech(self, work):
        """Run one speech call; audio, text and tokens never reach the log."""
        try:
            return work()
        except RuntimeError as exc:  # Nightshift not configured, or its speech route is not served
            self._json(503, {"error": str(exc)[:200]})
        except Exception as exc:
            self._json(502, {"error": f"speech failed ({type(exc).__name__})"})
        return None

    def _stt(self):
        mime = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        mime = {"audio/x-wav": "audio/wav", "audio/wave": "audio/wav"}.get(mime, mime)
        if mime not in STT_TYPES:
            self._json(415, {"error": "send audio/wav, audio/webm, audio/ogg or audio/mp4"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > STT_MAX_BYTES:
            self._json(413, {"error": "audio is over 2 MB"})
            return
        audio = self.rfile.read(length)
        if mime == "audio/wav" and len(audio) >= 44:
            rate = int.from_bytes(audio[28:32], "little")  # bytes per second from the WAV header
            if rate and (len(audio) - 44) / rate > STT_MAX_SECONDS:
                self._json(413, {"error": "audio is over 60 s"})
                return
        if not os.environ.get("METERLESS_BASE_URL"):
            self._json(503, {"error": "speech needs Meterless Nightshift"})
            return
        text = self._speech(lambda: Handler.llm.transcribe(audio, mime, self.headers.get("X-Speech-Lang") or None))
        if text is not None:
            self._json(200, {"text": text})

    def _tts(self):
        length = min(int(self.headers.get("Content-Length") or 0), 16384)
        try:
            text = str(json.loads(self.rfile.read(length) or b"{}").get("text") or "").strip()
        except ValueError:
            text = ""
        if not text:
            self._json(400, {"error": "text is empty"})
            return
        if len(text) > TTS_MAX_CHARS:
            self._json(413, {"error": f"text is over {TTS_MAX_CHARS} characters"})
            return
        if not os.environ.get("METERLESS_BASE_URL"):
            self._json(503, {"error": "speech needs Meterless Nightshift"})
            return
        audio = self._speech(lambda: Handler.llm.speak(text))
        if audio is not None:
            self._send(200, audio, "audio/mpeg")

    def do_POST(self):
        if self.path == "/stt":
            self._stt()
            return
        if self.path == "/tts":
            self._tts()
            return
        if self.path == "/ask/stream":
            # NDJSON: one {"step": ...} line per agent step, then {"result": ...}
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

            def emit(obj):
                self.wfile.write((json.dumps(obj, ensure_ascii=False, default=str) + "\n").encode())
                self.wfile.flush()

            try:
                result = investigate(self._question(), Handler.llm, on_step=lambda st: emit({"step": st}))
                emit({"result": result})
            except Exception as exc:
                emit({"error": f"{type(exc).__name__}: {exc}"[:400]})
            return
        if self.path != "/ask":
            self.send_error(404)
            return
        try:
            result, status = investigate(self._question(), Handler.llm), 200
        except Exception as exc:  # shown to the local user, never a stack trace
            result, status = {"error": f"{type(exc).__name__}: {exc}"[:400]}, 500
        self._send(status, json.dumps(result, ensure_ascii=False, default=str).encode(), "application/json")


def main():
    load_env()
    Handler.llm = Nemotron()
    port = int(os.environ.get("FT_PORT", "8765"))
    print(f"FastTrack Termin on http://127.0.0.1:{port}")
    ThreadingHTTPServer((os.environ.get("FT_HOST", "127.0.0.1"), port), Handler).serve_forever()


if __name__ == "__main__":
    main()

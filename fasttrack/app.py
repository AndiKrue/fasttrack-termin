# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Andreas Krueger
"""One page on localhost: ask, then read the routes, the reasons and the evidence behind them."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .agent import investigate
from .llm import Nemotron

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
    x.evidence.forEach(e=>{const v=d.evidence[e];b.append(el('pre',e+'  '+v.sql+'\\n'+JSON.stringify(v.row),'ev'))});
    out.append(b)});
  (d.caveats||[]).forEach(c=>out.append(el('p','Note: '+c,'muted')));
  out.append(el('p','Run '+d.run_id+' | source '+d.trace.source+' | memory '+d.trace.memory+' | '+d.model_calls.length+' Nemotron calls','muted'));
};
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    llm = None

    def do_GET(self):
        body = PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/ask":
            self.send_error(404)
            return
        length = min(int(self.headers.get("Content-Length") or 0), 8192)
        try:
            question = str(json.loads(self.rfile.read(length) or b"{}").get("question", ""))[:2000]
            result = investigate(question, Handler.llm)
            status = 200
        except Exception as exc:  # shown to the local user, never a stack trace
            result, status = {"error": f"{type(exc).__name__}: {exc}"[:400]}, 500
        body = json.dumps(result, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    Handler.llm = Nemotron()
    port = int(os.environ.get("FT_PORT", "8765"))
    print(f"FastTrack Termin on http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()

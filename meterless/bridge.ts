// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Andreas Krueger
// Meterless H-MEM behind JSON on stdin/stdout. Persistent: state.json + ledger.jsonl in FT_HMEM_DIR.
import { HMEM } from "./hmem/src/index.ts";

const chunks: Buffer[] = [];
for await (const c of process.stdin) chunks.push(c as Buffer);
const req = JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
const hmem = new HMEM({ actor: "fasttrack-termin", persistDir: process.env.FT_HMEM_DIR ?? "runs/hmem" });

if (req.op === "remember") {
  const r = req.record;
  const m = hmem.add({
    // The patient's question is stored with the route: recall matches new questions against it.
    content: `${r.question} -> ${r.route}: ${r.why}`,
    type: "factual",
    layer: "working",
    tags: ["fasttrack", `run:${r.run_id}`],
    confidence: 0.8,
    source: `fasttrack:${r.run_id}`,
  });
  process.stdout.write(JSON.stringify({ id: m.id, ledger: hmem.ledger.history(m.id).map((e) => e.action) }));
} else if (req.op === "recall") {
  // H-MEM's default threshold (0.35 after confidence) drops paraphrased questions; 0.2 keeps related ones.
  const q = hmem.query(String(req.query ?? ""), { topN: Number(req.limit ?? 5), threshold: Number(process.env.FT_HMEM_THRESHOLD ?? 0.2) });
  process.stdout.write(
    JSON.stringify({
      records: q.memories.map((x) => ({
        id: x.memory.id,
        content: x.memory.content,
        source: x.memory.source,
        relevance: x.relevance,
      })),
      context: q.context,
      trace: q.trace,
    }),
  );
} else {
  process.stderr.write("unknown op");
  process.exit(2);
}

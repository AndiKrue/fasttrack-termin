# Zetaris Demo Challenge — FastTrack Termin video script

Window: opens **29 Oct 2026, 23:45 UTC**, closes **5 Nov 2026, 23:45 UTC** (Discord announcement 28 Oct; it
supersedes the earlier 2/3 Nov dates). Upload: https://www.dropbox.com/home/Zetaris%20Demo%20Submissions File name: `FASTTRACK-TERMIN_DDMMYY.mp4` with the upload date. English. Target length 2:30–3:00.

Judging (100): meaningful use of Zetaris 25 · how it helped you 15 · problem and impact 15 · technical execution 15 ·
working with Space XAI's coding agents 15 (Cursor with Grok / Composer: build one real change with it and show it) · creativity 10 · video quality 5.
Tie-break: higher "meaningful use of Zetaris". So Zetaris must be on screen and doing the work, live.

## Structure

| # | Time | On screen (recorded live) | Voice |
|---|---|---|---|
| 0 | 0:00–0:04 | Intro card (`intro.mp4`) | — |
| 1 | 0:04–0:20 | App start page, the question box | Narrator: the patient problem |
| 2 | 0:20–0:50 | **Zetaris UI** (`http://localhost:3000`): the three Lightning databases FT_RULES, FT_PRACTICES, FT_WAITS and their filestore tables | Narrator: three separate sources |
| 3 | 0:50–1:10 | Terminal: `python zetaris/register.py` → DDL + row counts 7 / 10 / 12 | Narrator: registered from plain CSV in seconds |
| 4 | 1:10–1:30 | **Zetaris SQL editor**: one federated query joining practices and waits (below) | Narrator: one SQL surface over all three |
| 5 | 1:30–1:55 | App run: step "Querying Zetaris (3 sources)", then a route card → "Why this route" shows `Zetaris FT_PRACTICES.practices + FT_WAITS.waits` and the exact SQL; footer `source zetaris-lightning` | Narrator: every claim traces to a Zetaris row |
| 6 | 1:55–2:50 | You on camera, or the app/Zetaris UI as b-roll | **Your own voice, 40–60 s** (talking points below) |
| 7 | 2:50–2:56 | Outro card with QR (`outro.mp4`) | — |

### Federated query for shot 4 (paste into the Zetaris SQL editor)

```sql
SELECT p.name, p.district, p.specialty, w.channel, w.days_to_appointment
FROM FT_PRACTICES.practices p
JOIN FT_WAITS.waits w ON p.practice_id = w.practice_id
WHERE p.specialty = 'orthopaedics'
ORDER BY w.days_to_appointment
```

## Narrator lines (shots 1–5, Kokoro af_heart, tempo 1.0)

1. "A patient in Berlin needs a specialist. The facts that decide how fast she gets one live in different places."
2. "The rules of the appointment system, the practice directory, and the waiting times people actually observed. Three sources that never meet."
3. "Zetaris registers each one straight from a plain CSV file, as its own Lightning database. Seven rules, ten practices, twelve waiting-time observations."
4. "Then one SQL query joins them, as if they were one database. No pipeline, no copies, no ETL."
5. "Our agent writes that SQL itself, one read-only query per question. Every row Zetaris returns becomes evidence the answer has to cite, and the app shows the exact table and query behind every claim."

## Your 40–60 s (own voice; facts only from this build)

Pick 4–5, speak freely, ~130 words:

- **One SQL surface:** "I had three separate sources and needed an agent to reason across them. With Zetaris they became one SQL surface, so the agent only has to learn one thing: SQL."
- **Fast to set up:** "Registering a CSV as a Lightning database is one DDL statement. The three sources were queryable in minutes, not after building a pipeline."
- **Explainability for free:** "Because every answer comes from a SQL row, I could make the agent cite evidence. Zetaris made 'show me why' a database feature, not a prompt trick."
- **Safety:** "The agent only runs read-only SELECTs over JDBC; Zetaris gives it access to the data without giving it the keys to change it."
- **Local:** "It runs locally in Docker next to my app, so patient-style questions never leave my machine for the data part."
- **How it helped me:** "It let a solo builder spend the hackathon on the agent and the patient, not on data plumbing."

Close with one sentence that also works as the write-up.

## One-sentence write-up (form field "why did you think it was amazing?")

"Zetaris turned three disconnected health-appointment sources into one SQL surface in minutes, so my agent could answer with evidence from every source and show the exact query behind each claim."

## Recording notes

- Shots 2–4: record the Zetaris UI with OBS (1280×720 or 1920×1080), no passwords or tokens on screen; log in before recording.
- Shot 5: the narrated take (FastTrack v5 script, results/why shots) or an OBS capture of one live run.
- Shot 6: own microphone; quiet room; read once, then speak freely.
- Assemble with ffmpeg (same concat as the hackathon video), name the file `FASTTRACK-TERMIN_DDMMYY.mp4`.

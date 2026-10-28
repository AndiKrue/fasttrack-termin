<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
# Closeout: WO-FT-REVIEW-01 (built 28 Oct 2026, deploy after 6 Nov 16:00 UTC)

| Field | Value |
|---|---|
| Branch | `review`, based on `post-hackathon` `4bc32ef` (includes the specialty fix) |
| Commits | `17f661b` part 1, `f20c954` part 2, `5bc9a1b` part 3, `6f4abb4` part 4, `582d6ed` part 5, `f10cd80` /ask draft, `b3d9a6f` part 1 follow-up |
| Tests | 47 passed, clean env (`env -i`), in the app image; the H-MEM bridge test ran with tsx (not skipped) |
| Live test | Image `fasttrack-termin-review` as `ft-review-test` on 127.0.0.1:8766: Zetaris Lightning, Nightshift, Firecrawl, H-MEM in `runs-review/` |
| Deployed | **No.** Nothing merged into `post-hackathon` or `main`; the live stack was not rebuilt from `review`. |

## Verified live on :8766

- **Questions run:** Köpenick knee (twice), Friedrichshain HNO (German), Pankow cardiology, plus the web page through the test tunnel.
- **Part 1, SQL catalogue and nicknames: verified.**
  - The planner returned the stored specialty in every run (`orthopaedics`, `ENT`, `cardiology`).
  - 0-row queries were redrafted once, and both attempts appear in the trace.
  - The first Köpenick run wrote `lower(p.district) = 'treptow-koepenick'`. That spelling was not in the map, so it needed the redraft; the follow-up commit `b3d9a6f` adds it. In the second run the SQL that actually ran had `'treptow-köpenick'`.
- **Part 2, rules always queried: verified.**
  - In all four runs the planner asked no rules question.
  - The fixed rules SELECT added 7 rule rows each time, and routes cited R1, R4, R5 and R7.
- **Part 3, revision: not triggered live.** Every run kept 3 or 4 routes on the first verify. Covered by unit tests only.
- **Part 4, degraded run: verified live.**
  - **Nightshift fallback:** happened by itself in the Pankow run. The answer call timed out on Nightshift after 120 s (ReadTimeout); the NVIDIA API then answered with 200, 185.7 s in all. The call list shows 12 calls on meterless-nightshift and 1 on nvidia-api.
  - **Sample mode:** checked in the test container in-process with `FT_SAMPLE=1`: `local-sqlite`, web off, `local-jsonl`, 3 SAMPLE routes, provider `sample`.
  - **JDBC fallback:** with an unreachable Lightning port, the connect failed after 1.0 s, was logged, and the run used `local-sqlite`.
- **Part 5, H-MEM: partly verified.**
  - Stored memories are now spelled out (`koepenick`, `ueberweisung`).
  - Recall with "Koepenick" finds the Köpenick memory.
  - The memory guard is unit-tested only; no bridge failure happened live.
- **/ask draft: partly verified.**
  - In the container with `FT_ASK_AUTH=on`: no key or a wrong key gets 401; the right key reaches the agent.
  - With the default (off), the web page answered normally through the tunnel.
  - The mini app initData path was not tried on a phone.

## Open

1. **H-MEM recall quality.** The 64-dimension hash embedder (Grok finding 6, second half) is not in this WO.
   - The German query "Ich wohne in Köpenick, Knieschmerzen, Orthopäde" recalls the German Friedrichshain HNO memory before the English Köpenick knee memory. Shared filler words outweigh the place and the specialty.
   - Recalled records go to the answer as "earlier verified findings". They cannot be cited, so no route can rest on them, but they may still steer the wording.
   - Options: a better embedder, filtering recall by specialty, or a higher threshold.
2. **Old memories** in the live `runs/hmem` keep their unnormalised spelling ("penick"). New ones are spelled out.
3. **Answer quality not covered by the WO:**
   - Kept routes still mix averages across channels.
   - One kept route sent a patient without an urgency code to the appointment service, which R1 does not support.
4. **/ask decision:** the options in `docs/wo/WO-FT-ASK-01.md` (A/B/C, test-bot token, retention).
5. **WO-FT-REVIEW-01 § 6 items:** table whitelist, JDBC reuse, httpx retry, seed rows without phone, German UI.
6. **Enable-thinking item:** HANDOFF-2 known issue 3 (`enable_thinking` through Nightshift) is still separate.

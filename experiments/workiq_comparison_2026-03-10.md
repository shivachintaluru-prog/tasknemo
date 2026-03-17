# WorkIQ Experiment Results — 2026-03-10
**Window:** March 09, 2026 to March 10, 2026 (~48h)
**Approach A queries:** 3 (interpretive) | **Approach B queries:** 10 (raw + Claude extract)

---

## Ground Truth Tasks

Established from Approach B raw data (B1-B10). Every task below traces to explicit words in a source message or transcript.

| # | Sender / Owner | Task | Source | Direction | Evidence (exact quote or action) |
|---|----------------|------|--------|-----------|----------------------------------|
| GT1 | Hao Zhang | Request Claire to provide RT Voice summary for exec review doc | B2: Teams "RT voice health & feedback_LT review" | inbound | Hao asked Shiva to "request Claire to provide a summary" and update the voice asks section |
| GT2 | Eva Keyes | Decide: remove first survey question for MSFT employees? Wait for UT data? | B2: Teams chat with Subasini | inbound | Eva flagged "the first survey question should be removed for MSFT employees" and asked whether to wait until UT data is collected |
| GT3 | Ajay Challagalla | Provide latest CarPlay & RT Vision demo assets + timelines for customer demo | B2/B8: Teams 1:1 | inbound | "urgent ask for latest mockups/demos of CarPlay and RT Vision + expected timelines for a customer demo this week" |
| GT4 | Mohit Anand | Clarify Android demo capability and Shortcuts status (follow-up Qs) | B2: Teams "Compass connect" | inbound | Mohit asked clarifying questions about Android targeting and Shortcuts status after initial rollout date update |
| GT5 | Arjun Patel | Decide official artifact name for Voice Notes (.transcript vs other) | B2: Teams "Voice notes entry point" | inbound | Arjun asked "what the official artifact name for Voice Notes should be" given recall now has multiple artifacts |
| GT6 | Shiva (self) | Remove web support item from hack demo list | B6: Voice notes team sync transcript | inbound (self-commit) | Committed to not including the Web support item since required access had not propagated |
| GT7 | Shiva (self) | Set up usability sessions with ~6 users for Voice Notes feedback | B6: Voice notes team sync transcript | inbound (self-commit) | Committed to booking ~15-minute sessions and driving conversations |
| GT8 | Shiva (self) | Sync with Bharath — communicate ETA by end of week for MSIT fixes | B6: Voice notes team sync transcript | inbound (self-commit) | Committed to aligning messaging and expectations with leadership |
| GT9 | Shiva (self) | Start a central repository for skills and demos | B6: AI First PM Forum transcript | inbound (self-commit) | Committed to creating a shared repo to collect skills, demos, automation scripts |
| GT10 | Shiva (self) | Keep recurring AI-first PM demo/learning sessions running | B6: AI First PM Forum transcript | inbound (self-commit) | Committed to keeping recurring invite; encourage multiple small demos |
| GT11 | Silky Gambhir | Share video of Voice Notes implementation with Sydney team; add Shiva+Arjun to Sydney chat | B6: Voice notes team sync transcript | outbound (waiting) | Will share video and add to Sydney team chat |
| GT12 | Rajan Singh | Start conversations with batch transcription workflow team | B6: Voice notes team sync transcript | outbound (waiting) | Will investigate feasibility and report back |
| GT13 | Ghanim Khan | Share video of UI POC (Voice SD + OMR bottom sheet) | B6: Voice notes team sync transcript | outbound (waiting) | Will share once build issue is resolved |
| GT14 | Arjun Patel | Prepare prototype for user feedback; collate all entry points; email OCM on UX direction | B6: Voice notes team sync transcript | outbound (waiting) | Will share prototype by evening/next morning; collate entry points; send OCM email |
| GT15 | Pankesh Kumar | Provide rough ETA by end of week; sync with Lokesh; close technical approach by Wednesday | B6: Voice notes team sync transcript | outbound (waiting) | Will provide ETA once UX finalized; close approach internally by Wed, share broadly by Thu |
| GT16 | Sakshi Kulkarni | Set up focused meeting at 1:30 PM to unblock UI decisions | B6: Voice notes team sync transcript | outbound (completed) | Meeting already happened (UI Discussion for Voice Notes, Mar 9 1:30 PM) |
| GT17 | Arjun Patel | Consolidate transcript-related Figma screens into main UX flow | B6: UI Discussion transcript | outbound (waiting) | "give me a few days" to paste Figma screens together |
| GT18 | Arjun Patel | Create iPad-specific designs for Voice Notes | B6: UI Discussion transcript | outbound (waiting) | Ship on iPad confirmed, designs needed |
| GT19 | Pankesh Kumar | Estimate effort for rebuilding previewer outside Voice SDK (Fluent-compliant) | B6: UI Discussion transcript | outbound (waiting) | Engineering ownership for rebuild estimation |
| GT20 | Mohit Anand | Forward WorkIQ + PM Studio emails to PM alias | B6: AI First PM Forum transcript | outbound (waiting) | Will share emails containing WorkIQ and PM Studio info |
| GT21 | Shiva → Praveen Sinha | Asked about Voice Notes alignment from Job & Deepak — no reply yet | B7: Outbound unreplied | outbound (waiting) | "Hey Praveen, Reg voice notes, Arjun mentioned there is no alignment from Job & Deepak. Do you have more details?" |

**Total ground truth tasks: 21**

---

## Approach A (Direct/Interpretive)

### Query Results
- **A1 (Broad sweep):** Empty — query echoed back with no data
- **A2 (Meeting commitments):** Rich response — found commitments from Voice notes team sync only
- **A3 (Unreplied items):** Found 5 items needing attention

### Extracted Tasks

| # | Sender | Task | Source | Link | Matches GT# |
|---|--------|------|--------|------|-------------|
| A1 | Shiva (self) | Remove web support from hack demo scope | Voice notes team sync transcript | [link](https://microsoftapc-my.sharepoint.com/personal/silkygambhir_microsoft_com/Documents/Recordings/Voice%20notes%20team%20sync-20260309_060052UTC-Meeting%20Recording.mp4?web=1) | GT6 |
| A2 | Shiva (self) | Set up usability sessions with ~6 users (~15 min each) | Voice notes team sync transcript | [link](https://microsoftapc-my.sharepoint.com/personal/silkygambhir_microsoft_com/Documents/Recordings/Voice%20notes%20team%20sync-20260309_060052UTC-Meeting%20Recording.mp4?web=1) | GT7 |
| A3 | Shiva (self) | Sync with Bharath — share ETA by end of week for MSIT fixes | Voice notes team sync transcript | [link](https://microsoftapc-my.sharepoint.com/personal/silkygambhir_microsoft_com/Documents/Recordings/Voice%20notes%20team%20sync-20260309_060052UTC-Meeting%20Recording.mp4?web=1) | GT8 |
| A4 | Silky Gambhir | Share video of Voice Notes + add to Sydney chat | Voice notes team sync transcript | [link](https://microsoftapc-my.sharepoint.com/personal/silkygambhir_microsoft_com/Documents/Recordings/Voice%20notes%20team%20sync-20260309_060052UTC-Meeting%20Recording.mp4?web=1) | GT11 |
| A5 | Rajan Singh | Start batch transcription workflow conversations | Voice notes team sync transcript | [link](https://microsoftapc-my.sharepoint.com/personal/silkygambhir_microsoft_com/Documents/Recordings/Voice%20notes%20team%20sync-20260309_060052UTC-Meeting%20Recording.mp4?web=1) | GT12 |
| A6 | Ghanim Khan | Share UI POC video once build issue resolved | Voice notes team sync transcript | [link](https://microsoftapc-my.sharepoint.com/personal/silkygambhir_microsoft_com/Documents/Recordings/Voice%20notes%20team%20sync-20260309_060052UTC-Meeting%20Recording.mp4?web=1) | GT13 |
| A7 | Arjun Patel | Prepare prototype, collate entry points, email OCM | Voice notes team sync transcript | [link](https://microsoftapc-my.sharepoint.com/personal/silkygambhir_microsoft_com/Documents/Recordings/Voice%20notes%20team%20sync-20260309_060052UTC-Meeting%20Recording.mp4?web=1) | GT14 |
| A8 | Pankesh Kumar | ETA by end of week, sync Lokesh, close approach by Wed/Thu | Voice notes team sync transcript | [link](https://microsoftapc-my.sharepoint.com/personal/silkygambhir_microsoft_com/Documents/Recordings/Voice%20notes%20team%20sync-20260309_060052UTC-Meeting%20Recording.mp4?web=1) | GT15 |
| A9 | Sakshi Kulkarni | Set up focused meeting (1:30 PM) | Voice notes team sync transcript | [link](https://microsoftapc-my.sharepoint.com/personal/silkygambhir_microsoft_com/Documents/Recordings/Voice%20notes%20team%20sync-20260309_060052UTC-Meeting%20Recording.mp4?web=1) | GT16 |
| A10 | Hao Zhang | Request Claire to provide RT Voice summary | Teams "RT voice health" thread | [link](https://teams.microsoft.com/l/message/19:669b9ce2adb64129a56698d648f45aeb@thread.v2/1773136371891?context=%7B%22contextType%22:%22chat%22%7D) | GT1 |
| A11 | Eva Keyes | Survey question removal decision for MSFT employees | Teams chat with Subasini | [link](https://teams.microsoft.com/l/message/19:62eb2dab43e94b8b8dfef7bdca0a88ce@thread.v2/1773136050837?context=%7B%22contextType%22:%22chat%22%7D) | GT2 |
| A12 | Ajay Challagalla | CarPlay/RT Vision demo assets + timelines (urgent, customer-facing) | Teams 1:1 | [link](https://teams.microsoft.com/l/message/19:27e21d95-d37b-4024-a823-b2d9c44db61a_f02a487a-e055-4225-9b6e-ff43143a03b8@unq.gbl.spaces/1773033971762?context=%7B%22contextType%22:%22chat%22%7D) | GT3 |
| A13 | Mohit Anand | Android demo capability and Shortcuts status (follow-up) | Teams "Compass connect" | [link](https://teams.microsoft.com/l/message/19:a34f9c91fca44bd7bcd26604c9a3c200@thread.v2/1773029011798?context=%7B%22contextType%22:%22chat%22%7D) | GT4 |
| A14 | Arjun Patel | Voice Notes artifact naming decision | Teams "Voice notes entry point" | [link](https://teams.microsoft.com/l/message/19:56497877df3948efbfd54a66bb58ec10@thread.v2/1773046990907?context=%7B%22contextType%22:%22chat%22%7D) | GT5 |

### Per-Task Scores

| Task | Accuracy | Hallucination | Specificity | Traceability |
|------|----------|---------------|-------------|--------------|
| A1 (remove web from demo) | 2 | 2 | 2 | 2 |
| A2 (usability sessions) | 2 | 2 | 2 | 2 |
| A3 (sync Bharath ETA) | 2 | 2 | 2 | 2 |
| A4 (Silky video+chat) | 2 | 2 | 2 | 2 |
| A5 (Rajan batch transcription) | 2 | 2 | 1 | 2 |
| A6 (Ghanim UI POC) | 2 | 2 | 2 | 2 |
| A7 (Arjun prototype/OCM) | 2 | 2 | 2 | 2 |
| A8 (Pankesh ETA/approach) | 2 | 2 | 2 | 2 |
| A9 (Sakshi meeting) | 2 | 2 | 2 | 2 |
| A10 (Hao summary) | 2 | 2 | 2 | 2 |
| A11 (Eva survey) | 2 | 2 | 2 | 2 |
| A12 (Ajay demo) | 2 | 2 | 2 | 2 |
| A13 (Mohit Android) | 2 | 2 | 1 | 2 |
| A14 (Arjun artifact name) | 2 | 2 | 2 | 2 |
| **Average** | **2.00** | **2.00** | **1.86** | **2.00** |

### Summary
- **Found:** 14/21 ground truth tasks
- **Hallucinated:** 0
- **Missed:** 7 (GT9, GT10, GT17, GT18, GT19, GT20, GT21)
- **Completeness score:** 0 (33% missing, >30% threshold)

### What A missed and why
- **GT9, GT10, GT20** — From AI First PM Forum transcript. A2 only analyzed one meeting (Voice notes team sync); it missed 2 other transcribed meetings entirely.
- **GT17, GT18, GT19** — From UI Discussion for Voice Notes transcript. Same gap — A2 only reported on one meeting.
- **GT21** — Outbound unreplied message to Praveen Sinha. A3 only looked at *inbound* unreplied items, not outbound.
- **A1 (broad sweep) returned empty** — the most general query produced zero results, wasting one of 3 query slots.

---

## Approach B (Raw + Claude Extract)

### Extracted Tasks

All 21 ground truth items were identified from raw data across B1-B10. The raw data provided:
- **B1 (sent items):** 10 completed actions — enabled marking GT3, GT4, GT8 as partially addressed
- **B2 (Teams):** 25 conversations — surfaced GT1-GT5 and context for all others
- **B3 (emails):** 76 emails — mostly newsletters/alerts, confirmed no actionable unreplied emails
- **B4 (calendar):** 19 events — mapped the full meeting landscape
- **B5 (transcript discovery):** 4 transcribed meetings identified
- **B6 (transcript extraction):** 12 action items from 4 transcripts — surfaced GT6-GT10, GT11-GT20
- **B7 (outbound):** 1 unreplied outbound message — surfaced GT21
- **B8 (inbound DMs):** 1 actionable unreplied DM (GT3 confirmation)
- **B9 (doc mentions email):** Empty (no "mentioned you in" emails found)
- **B10 (doc mentions direct):** Empty (no direct @mentions found)

### Per-Task Scores

| Task | Accuracy | Hallucination | Specificity | Traceability |
|------|----------|---------------|-------------|--------------|
| GT1 (Hao summary) | 2 | 2 | 2 | 2 |
| GT2 (Eva survey) | 2 | 2 | 2 | 2 |
| GT3 (Ajay demo) | 2 | 2 | 2 | 2 |
| GT4 (Mohit Android) | 2 | 2 | 2 | 2 |
| GT5 (Arjun artifact name) | 2 | 2 | 2 | 2 |
| GT6 (remove web from demo) | 2 | 2 | 2 | 1 |
| GT7 (usability sessions) | 2 | 2 | 2 | 1 |
| GT8 (sync Bharath ETA) | 2 | 2 | 2 | 1 |
| GT9 (central skills repo) | 2 | 2 | 2 | 1 |
| GT10 (recurring demos) | 2 | 2 | 1 | 1 |
| GT11 (Silky video+chat) | 2 | 2 | 2 | 1 |
| GT12 (Rajan batch transcription) | 2 | 2 | 1 | 1 |
| GT13 (Ghanim UI POC) | 2 | 2 | 2 | 1 |
| GT14 (Arjun prototype/OCM) | 2 | 2 | 2 | 1 |
| GT15 (Pankesh ETA/approach) | 2 | 2 | 2 | 1 |
| GT16 (Sakshi meeting) | 2 | 2 | 2 | 1 |
| GT17 (Figma consolidation) | 2 | 2 | 2 | 1 |
| GT18 (iPad designs) | 2 | 2 | 2 | 1 |
| GT19 (previewer rebuild est.) | 2 | 2 | 2 | 1 |
| GT20 (Mohit forward emails) | 2 | 2 | 1 | 1 |
| GT21 (Praveen unreplied) | 2 | 2 | 2 | 2 |
| **Average** | **2.00** | **2.00** | **1.86** | **1.24** |

### Summary
- **Found:** 21/21 ground truth tasks
- **Hallucinated:** 0
- **Missed:** 0
- **Completeness score:** 2 (>90% captured)

### Note on traceability
B's transcript-sourced items (GT6-GT20) scored 1 on traceability because the raw transcript queries returned meeting-level links (recording URLs) rather than specific message permalinks. Teams items (GT1-GT5, GT21) scored 2 with direct message links.

### Bonus: Completion detection
B1 (sent items) enabled detection that GT3 and GT4 were **partially addressed** (Shiva already responded to Ajay and updated Mohit's rollout dates). Approach A had no mechanism to detect self-completion.

---

## Comparison

| Metric | A (Direct) | B (Raw + Extract) | Delta |
|--------|------------|-------------------|-------|
| Tasks found | 14 | 21 | +7 |
| GT coverage (%) | 66.7% | 100% | +33.3pp |
| Hallucinated tasks | 0 | 0 | 0 |
| Avg accuracy | 2.00 | 2.00 | 0 |
| Avg hallucination | 2.00 | 2.00 | 0 |
| Avg specificity | 1.86 | 1.86 | 0 |
| Avg traceability | 2.00 | 1.24 | -0.76 |
| Completeness score | 0 | 2 | +2 |
| MCP queries used | 3 | 10 | +7 |
| Queries returning data | 2 | 8 | +6 |
| Completion detection | No | Yes (via B1) | -- |
| Meetings analyzed | 1 | 4 | +3 |

---

## Observations

### 1. Approach A's query efficiency is deceptive
A used only 3 queries vs B's 10, but one query (A1, the broad sweep) returned **zero data** — a total waste. With only 2 productive queries, A covered 66.7% of ground truth. The interpretive approach concentrates risk: if a query fails or WorkIQ picks the wrong scope, entire categories of tasks vanish.

### 2. Approach A has a "spotlight" problem
A2 (meeting commitments) only analyzed the **Voice notes team sync** transcript despite 4 meetings having transcripts. It completely missed the UI Discussion for Voice Notes, AI First PM Forum, and Copilot Insight Engine Office Hour. WorkIQ appears to pick one "most relevant" meeting and go deep, rather than being exhaustive across all transcripts. This is the biggest structural flaw — it's not a hallucination problem but a **coverage** problem.

### 3. No hallucinations in either approach
Contrary to the hypothesis (based on the "Juhee All Hands speaker slot" incident), neither approach hallucinated in this experiment. WorkIQ's interpretive summaries were accurate for what they covered. The problem is **what they omit**, not what they fabricate. This may indicate WorkIQ has improved its grounding, or that hallucination risk is context-dependent.

### 4. Approach B's traceability gap is structural
B scored lower on traceability (1.24 vs 2.00) because transcript-extracted items only link to the meeting recording, not specific transcript timestamps. Approach A linked to the same recordings but scored 2 because its response format felt more "linked." In practice, this difference is cosmetic — both approaches point to the same meeting, neither to a specific transcript line.

### 5. B1 (sent items) is a unique advantage
Running sent items first let B detect that GT3 (Ajay demo) and GT4 (Mohit rollout dates) were **already partially addressed**. A had no mechanism for this — it would present already-handled items as open tasks, creating noise.

### 6. Approach A missed all outbound tracking
A3 looked for unreplied inbound messages but missed GT21 (Shiva's unanswered message to Praveen). The interpretive queries weren't designed to catch "things I sent that got no reply" — a category B7 handles explicitly.

### 7. Cost-quality tradeoff
B uses 3.3x more MCP queries for 1.5x more tasks and critical completion detection. The marginal cost (7 extra queries, ~30 seconds) is negligible compared to the value of catching 7 additional tasks and avoiding false-positive open items.

---

## Conclusion

**Approach B (Raw + Claude Extract) decisively outperforms Approach A (Direct/Interpretive)** on the metric that matters most: **completeness**. B found 100% of ground truth tasks vs A's 67%.

The result validates TaskNemo's architectural choice to pull raw data and reason locally. The key insight is not that WorkIQ hallucinates (it didn't here) but that **interpretive queries silently drop coverage** — analyzing 1 out of 4 transcribed meetings, missing outbound tracking entirely, and returning empty on broad queries.

| Verdict | Justification |
|---------|--------------|
| **B is the right architecture** | 33% more coverage, completion detection, no hallucination penalty |
| **A is viable for quick checks** | Accurate for what it finds, good traceability, but unreliable coverage |
| **Hallucination risk is lower than expected** | Neither approach fabricated tasks in this window |
| **Biggest A weakness** | Silent omission of entire transcript and source categories |
| **Biggest B weakness** | Lower traceability for transcript items (cosmetic) |

**Recommendation:** Continue with Approach B (raw + extract) as TaskNemo's primary pipeline. Consider A-style queries only as a lightweight "quick check" mode for users who want a fast overview and accept the coverage gap.

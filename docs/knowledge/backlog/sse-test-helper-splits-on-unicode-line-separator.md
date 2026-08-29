---
type: Backlog Item
title: The chat SSE test helper splits frames on U+2028, truncating any payload that carries one
description: tests/integration/chat/_helpers.py::parse_sse_body uses str.splitlines(), which treats U+2028 LINE SEPARATOR as a line break; a recorded EDA study description contains one, so the helper cuts the search_eda_studies tool-output-available frame in two while the wire frame itself is one intact data line. Found 2026-08-28 by the batch-3 end-to-end verifier, which asserts on persisted rows to sidestep it.
tags: [tests, sse, chat, eda]
generated: { by: claude-code/fable-5, at: 2026-08-28T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-28T00:00:00Z }
status: stable
---

**What I did.** Drove the batch-3 EDA end-to-end conversation through
`POST /api/v1/chat` with the mock provider and parsed the SSE body with the
existing `parse_sse_body` helper.

**What I got.** The `tool-output-available` frame for `search_eda_studies`
came back truncated in the parsed result, while the raw body held one intact
`data:` line with valid JSON.

**Why that is wrong.** Any test that asserts on a parsed frame whose payload
carries U+2028 (the recorded description "All 159 isolates included in this
study." does) sees a half frame and either fails for a false reason or, worse,
asserts on the surviving half and passes vacuously.

**Why it happens.** `str.splitlines()` splits on U+2028 and U+2029 as well as
`\n`; SSE frames are delimited by `\n` only.

**Fix.** Split on `"\n"` (or `"\r\n"`/`"\n"`) explicitly in `parse_sse_body`,
and add a test with a payload carrying U+2028 that asserts the frame survives
whole.

**What you would get.** One parsed frame per wire frame, regardless of the
payload's unicode.

# Step 1 findings (no parse calls made)
Gateway (A1 session 189e1f0e..., 2026-11-19 02:11Z, protocosmo2 agent sqlite, read-only):
- model anthropic/claude-opus-5-5, api anthropic-messages, thinkLevel=medium, reasoningLevel=off, fastMode=false
- tools sent: [] ; system prompt 458,591 chars (trajectory stored truncated at 32,768); catalog 452,409 B -> ~6.2k chars of OpenClaw wrapper
- catalog placement: under "## Conversation Context", after the first cache boundary (source: dist system-prompt-params, 11-10 report); not byte-recorded here
- temperature: installed dist forwards it but drops it when thinking is on -> temp 0 did NOT reach Anthropic for A1
- per call: input 4, cacheRead 175,373, cacheWrite 428 (1h), output 1,146, gateway-priced cost $0.0614
- A1 calls.jsonl: 124 calls, prompt 21,573,503 tok, cached 21,573,007, out 188,181; prompt_sha 2826a9c35b29942f
- A1 window (gateway table): 290 big-prompt calls, $21.95 (~$0.076/call)
Direct (semantic-parse.py @660127d9 --provider anthropic):
- catalog templates/generated/PROMPT_CATALOG.txt sha 2826a9c35b29942f (= A1), 452,409 B
- system=[catalog + cache_control ephemeral (5 min)], API version 2026-10-21 refuses sampling fields -> no temperature (same as gateway in practice)
- effort default low; gateway ran medium -> use --effort medium to match
Key: no ANTHROPIC_API_KEY in env, *.env files, or secrets.json. Auth store has anthropic:andy (OAuth token, not an API key) and singularitycompute api_key. Config anthropic-api provider points to profile anthropic-api:manual, which does not exist in the store. -> no direct key on pop-os.
Spend estimate D (2 runs x 124 = 248 calls): ~248 x $0.076 = ~$19 + up to ~5 cold cache writes (~$1 each) = ~$20-25; G = $0 (reuse A1 + r1-r3). Under the $30 cap. Basis: the gateway's price table, not Anthropic invoices.

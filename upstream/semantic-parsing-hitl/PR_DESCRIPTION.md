# Add the Anthropic provider to semantic-parse.py

Base: semantic-parsing-hitl @ 1f1a7a6f ("Do a major repo cleanup and re-org").
Patches: 0001 (the Anthropic provider), 0002 (its tests), 0003 (the chat-completions provider, below, with its
tests). Apply with `git am 000*.patch`.

## What
`class Anthropic` replaces the placeholder. It talks to the Messages REST API
(`https://api.anthropic.com/v1/messages`, `anthropic-version: 2023-06-01`) through the module's
own `_post_json`. There is no new dependency (no SDK), the same as the other providers.

- Key: `ANTHROPIC_API_KEY`, from the environment only. A missing key raises `ProviderError("set ANTHROPIC_API_KEY")`.
  `--dry-run` shows `<key>` and never the key.
- Model: `--model`, else `default_model` (left as in the placeholder, `claude-sonnet-5-5`).
- Prompt caching: the catalog (the system prompt) is sent as one text block that ends in a
  `cache_control: {"type": "ephemeral"}` breakpoint, and the item goes in the user message. The first call
  writes the cache, and later calls within the lifetime read it. The new `--no-cache` flag drops the breakpoint.
- Thinking: `--effort` none sends no thinking. low/medium/high/xhigh/max map to thinking budgets of
  1024/4096/16384/32768/63999 tokens. `max_tokens` defaults to the budget + 8192 (or 8192 without thinking),
  and `--max-tokens` overrides it. `--no-thinking` turns thinking off whatever the effort. With thinking on,
  `--temperature` is not sent, because the API refuses values other than 1.
- Usage, in the shape the other providers use: `input` = uncached + cache read + cache write, `cached` = cache read,
  `cache_write` = cache creation, plus `output`, `total`, `finish` (stop_reason), `service_tier`. Anthropic's own
  fields are kept in `raw_usage`. That's enough to cost each item at the published input / cache-write /
  cache-read / output rates.
- Retries: 429 and 529 (overloaded) get the patient waits that the other providers use for capacity errors.
- `--dry-run`: the catalog text inside the system block is shown as `<N chars of PATH>`, like the other
  providers' instructions.

## Tests
`templates/tests/test_anthropic.py` has 9 tests, all mocked, with no network and no key: the provider is registered,
the key comes from the env only, the request shape and cache breakpoint, `--no-cache`, thinking budgets/temperature/max_tokens,
reply text and thoughts and usage arithmetic, HTTP error -> ProviderError, `parse_sentence` end to end, and the dry-run redaction.
Run with `cd templates && python tests/test_anthropic.py`.

All the other test files give the same results before and after the patch. `test_emit` (1 error) and
`test_validate` (1 failure, 1 error) already fail at 1f1a7a6f in an environment without the `petta`
package, and the patch doesn't change that.

## Not tested
No live API call yet: there was no key in the authoring environment. The first real run should check that
`cache_read_input_tokens` > 0 from the second item on. If the catalog is shorter than the model's minimum
cacheable length, the API silently sends it uncached.

## Also: the chat-completions provider (patch 0003)
`--provider chat-completions --base-url <url> --model <name>` sends to any OpenAI-compatible Chat Completions
endpoint (`<base-url>/chat/completions`: a self-hosted model server, a gateway, a proxy). It reuses DeepSeek's
client (streamed, `_post_json` retries, `_read_sse`); the bearer key comes from the variable named by
`--api-key-env` (default `CHAT_COMPLETIONS_API_KEY`). `--base-url` and `--model` are required. Only portable
fields are sent (model, messages, stream with `stream_options.include_usage`, max_tokens, temperature).
Usage is in the shared shape: cache read from `prompt_tokens_details.cached_tokens` (or
`prompt_cache_hit_tokens`), cache write from `cache_creation_input_tokens`; a field the server does not
report stays None, never zero. Tests: `templates/tests/test_chat_completions.py` (7, no network, no key).

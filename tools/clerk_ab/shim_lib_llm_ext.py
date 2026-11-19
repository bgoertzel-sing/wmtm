"""SHIM (t-2026-11-18-wmtm-clerk-ab): minimal stand-in for hypernoia lib_llm_ext.
NOT the upstream library (absent from host). Implements only the contract parser_clerk.preview's
'compatible' path and tests/host_live/fakes.py rely on: _provider_parts, _primary_call_limits, _chat,
_deadline_bound_create, _call_with_hard_deadline, _CLIENTS, ARTIFACTS, _PRICE_IN/_PRICE_OUT, useOpenRouter,
spend meter ARTIFACTS/spend.json {cycles, cost}. No retries, no <think>/_quote_ rewriting of replies."""
import json, os, signal, threading, time
from pathlib import Path
# SCRATCH: kit's child runs `python -I` (no user site); preview.compatible_call imports openai right after loading
# this module, and openai lives only in user site-packages. Expose it at import time (scratch shim only).
import sys as _sys0
_US0 = os.path.expanduser('~/.local/lib/python%d.%d/site-packages' % _sys0.version_info[:2])
if _US0 not in _sys0.path: _sys0.path.append(_US0)

_INSTANCE = Path(os.environ.get('HYPERNOIA_INSTANCE_DIR') or '.').expanduser().resolve()
ARTIFACTS = _INSTANCE / 'artifacts'
_CLIENTS = {}
_PRICE_IN = 0.0   # $/token, used only when usage.cost absent
_PRICE_OUT = 0.0
_MARKER_PREFIX = '===YOUR LIVE MIND'


def _provider_parts(content):
    """'PROMPT: ' + system + '\\n' + marker + user  ->  (system, marker + user)."""
    body = content[len('PROMPT: '):] if content.startswith('PROMPT: ') else content
    i = body.find(_MARKER_PREFIX)
    if i < 0:
        return None, body
    return body[:i].rstrip('\n'), body[i:]


def _primary_call_limits():
    return int(os.environ.get('HYPERNOIA_MAX_TOKENS', '4096')), float(os.environ.get('HYPERNOIA_TIMEOUT', '120'))


class _Deadline(Exception):
    pass


def _call_with_hard_deadline(fn, seconds):
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError('hard deadline requires the main thread')
    def fire(*_):
        raise _Deadline('hard deadline %ss' % seconds)
    old = signal.signal(signal.SIGALRM, fire)
    signal.setitimer(signal.ITIMER_REAL, float(seconds))
    try:
        return fn()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def _deadline_bound_create(client, kwargs, deadline_at):
    remaining = max(1.0, deadline_at - time.monotonic())
    return _call_with_hard_deadline(lambda: client.chat.completions.create(**kwargs), remaining + 5)


def _meter_add(cost):
    try:
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        f = ARTIFACTS / 'spend.json'
        held = json.loads(f.read_text()) if f.exists() else {'cycles': 0, 'cost': 0.0}
        held['cycles'] += 1
        held['cost'] += cost
        f.write_text(json.dumps(held))
    except Exception as e:
        print('meter write failed', type(e).__name__)


def _chat(client, model, content, system=None, max_tokens=4096, max_retries=1, request_timeout=120,
          max_tokens_field='max_tokens', **extra):
    messages = ([{'role': 'system', 'content': system}] if system else []) + [{'role': 'user', 'content': content}]
    kwargs = {'model': model, 'messages': messages, max_tokens_field: max_tokens}
    for k in ('reasoning_effort', 'response_format'):
        if extra.get(k) is not None:
            kwargs[k] = extra[k]
    try:
        r = _deadline_bound_create(client, kwargs, time.monotonic() + request_timeout)
    except Exception as e:
        print('provider call failed:', type(e).__name__)
        return ''
    u = getattr(r, 'usage', None)
    cost = getattr(u, 'cost', None)
    if not isinstance(cost, (int, float)):
        cost = (getattr(u, 'prompt_tokens', 0) or 0) * _PRICE_IN + (getattr(u, 'completion_tokens', 0) or 0) * _PRICE_OUT
    _meter_add(float(cost))
    return (r.choices[0].message.content or '') if r.choices else ''


def _client(name='openrouter'):
    if name not in _CLIENTS:
        # SCRATCH: kit starts its child with python -I (no user site); openai lives in user site-packages.
        import sys as _sys
        _us = os.path.expanduser('~/.local/lib/python%d.%d/site-packages' % _sys.version_info[:2])
        if _us not in _sys.path: _sys.path.append(_us)
        import openai
        _CLIENTS[name] = openai.OpenAI(api_key=os.environ.get('OPENROUTER_API_KEY') or 'x',
                                       base_url=os.environ.get('HYPERNOIA_BASE_URL', 'https://openrouter.ai/api/v1'),
                                       max_retries=0)
    return _CLIENTS[name]


def useOpenRouter(content):
    system, user = _provider_parts(content)
    m, t = _primary_call_limits()
    return _chat(_client('openrouter'), os.environ.get('HYPERNOIA_MODEL'), user, system=system, max_tokens=m,
                 request_timeout=t)

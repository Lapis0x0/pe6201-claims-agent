"""Model backends for the claims agent.

Two of them, behind one method:

  ScriptedBackend  replays a fixed sequence of responses. No network, no key,
                   no cost, and the same trajectory every time. This is the
                   default backend of the submitted code (D5a) and the one the
                   guardrail checklist (D3b) and the failure reproductions (D7)
                   run against.

  LiveBackend      calls a real model through OpenRouter's OpenAI-compatible
                   API. Used for the D2b prompt rewrite and the D5b model
                   battery. It also records token usage so the cost model (D6)
                   has measured numbers rather than estimates.
"""

import config


class ScriptedBackend:
    """Replay a recorded list of model responses, in order.

    Each element of `script` is one complete model response in the ReAct
    format the agent parses: Thought / Action / Action Input, or Thought /
    Final Answer.
    """

    name = "scripted"

    def __init__(self, script, label="scripted"):
        self.script = list(script)
        self.label = label
        self.step = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def generate(self, messages):
        if self.step >= len(self.script):
            # A script that runs out is a bug in the script, not in the agent.
            # Say so in-band so the run fails visibly instead of hanging.
            return (
                "Thought: the script is exhausted; there is no recorded "
                "response for this turn.\n"
                'Final Answer: {"decision": "escalate", "detail": '
                '{"trigger": "unparseable_model_output", '
                '"note": "scripted backend exhausted"}}'
            )
        response = self.script[self.step]
        self.step += 1
        return response


class LiveBackend:
    """Call a real model through OpenRouter (OpenAI-compatible)."""

    name = "live"

    def __init__(self, model=config.DEFAULT_MODEL, api_key=None,
                 base_url=config.OPENROUTER_BASE_URL,
                 temperature=config.DEFAULT_TEMPERATURE,
                 max_tokens=config.DEFAULT_MAX_TOKENS):
        import openai  # imported lazily so scripted runs need no dependency

        if not api_key:
            raise ValueError(
                "LiveBackend needs an API key. Pass --api-key or set "
                "OPENROUTER_API_KEY."
            )
        self.client = openai.OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.label = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.prompt_tokens = 0
        self.completion_tokens = 0
        # D6's caching/reasoning disclosure needs these to check for either
        # effect after the fact rather than assume neither occurred. Only
        # some providers populate these breakdown fields; both stay 0 if
        # the response doesn't carry them, which is itself the answer.
        self.cached_tokens = 0
        self.reasoning_tokens = 0

    def generate(self, messages):
        # max_tokens matters beyond cost control here: OpenRouter checks
        # whether the account can afford the WORST-CASE completion size
        # before a call is even attempted. Leaving it unset defaults to the
        # model's own ceiling (16,384 for gpt-4o-mini) regardless of how
        # much a turn actually needs (~100 tokens, measured in
        # measure_parallel.py) - and low-balance accounts get a 402 before
        # the request is ever billed for real usage.
        #
        # Retry once on an empty completion: observed live against
        # deepseek/deepseek-v4-flash at temperature=0 (so not sampling
        # noise) - an upstream provider OpenRouter routed to occasionally
        # returns message.content=None with finish_reason="stop". A second
        # attempt succeeds; without this, one transient empty response
        # crashes the whole paid battery run rather than just this turn.
        content = None
        for attempt in range(2):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            usage = getattr(response, "usage", None)
            if usage is not None:
                self.prompt_tokens += usage.prompt_tokens or 0
                self.completion_tokens += usage.completion_tokens or 0
                prompt_details = getattr(usage, "prompt_tokens_details", None)
                if prompt_details is not None:
                    self.cached_tokens += (
                        getattr(prompt_details, "cached_tokens", None) or 0)
                completion_details = getattr(
                    usage, "completion_tokens_details", None)
                if completion_details is not None:
                    self.reasoning_tokens += (
                        getattr(completion_details, "reasoning_tokens", None)
                        or 0)
            content = response.choices[0].message.content
            if content is not None:
                return content
        return ""  # both attempts empty - let the loop's own parse-failure
                   # counter (MAX_PARSE_FAILURES) handle it, not a crash

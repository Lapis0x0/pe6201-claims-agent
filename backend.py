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
                 temperature=config.DEFAULT_TEMPERATURE):
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
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def generate(self, messages):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
        )
        usage = getattr(response, "usage", None)
        if usage is not None:
            self.prompt_tokens += usage.prompt_tokens or 0
            self.completion_tokens += usage.completion_tokens or 0
        return response.choices[0].message.content

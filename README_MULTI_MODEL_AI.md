# Multi-model AI router (foundation)

The app can route text-generation requests to OpenAI, Anthropic Claude, Google Gemini,
xAI Grok, or a local Ollama model. This is a provider adapter, not a model trained
from scratch. Each cloud provider requires its own API key, enabled model and account
quota. ChatGPT subscriptions do not automatically pay for OpenAI API usage.

## Configure on Oracle

Edit the Oracle server's private `.env` file (do not commit it to GitHub):

```dotenv
AI_PROVIDER=ollama
AI_MAX_OUTPUT_TOKENS=1200
AI_DAILY_REQUEST_LIMIT=20
AI_USAGE_DB=data/ai_usage.sqlite3

# Choose one cloud provider and enter a model enabled for your account.
OPENAI_API_KEY=
OPENAI_MODEL=
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=
GEMINI_API_KEY=
GEMINI_MODEL=
XAI_API_KEY=
XAI_MODEL=

# Or run Ollama locally; install/pull a model separately on the Oracle host.
LOCAL_LLM_URL=http://127.0.0.1:11434
LOCAL_LLM_MODEL=
```

The quota is 20 requests per provider per UTC day by default. Set
`AI_DAILY_REQUEST_LIMIT=0` to disable that software-side request cap; provider-side
quotas and billing still apply. The cap counts failed cloud requests too, since a
provider may bill a request even if the response could not be parsed. Output token
requests are capped at 1,200 by default; adjust the cap deliberately if needed.

For local use, install Ollama and a model separately. The Oracle A1 instance is CPU-only,
so large local models may be slow or fail for memory; local inference is not guaranteed
to be free of compute, storage or hosting costs. The module only permits local Ollama
URLs on localhost.

## Call it from Python

```python
from ct_ai_router import complete

caption = complete(
    "Write a short Tamil and English caption for this original story chapter.",
    provider="gemini",  # or openai, anthropic/claude, xai/grok, ollama
    system_prompt="Write accurate, engaging copy. Do not invent story facts.",
    max_output_tokens=500,
)
print(caption)
```

Install project dependencies and set the environment on Oracle first. Never put
provider keys in source files, browser JavaScript, prompts, chat messages or commits.
Image/video generation, voice, story ingestion and social publishing are separate
features and need their own provider/platform integrations. A text router alone does
not activate automatic publishing.

## Provider references

- OpenAI Responses API: https://platform.openai.com/docs/api-reference/responses
- Anthropic Messages API: https://docs.anthropic.com/en/api/messages
- Gemini generateContent: https://ai.google.dev/api/generate-content
- xAI Responses API: https://docs.x.ai/developers/rest-api-reference/inference/responses
- Ollama chat API: https://github.com/ollama/ollama/blob/main/docs/api.md

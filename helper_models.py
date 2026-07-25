from dataclasses import dataclass


@dataclass(frozen=True)
class HelperModelConfig:
    label: str
    provider: str
    model: str
    base_url: str


HELPER_MODEL_OPTIONS = [
    "gpt-5.4-mini",
    "GPT-5.4 (Reseller)",
    "Claude Sonnet 5 (Reseller)",
    "gpt-5-mini",
    "gpt-4o-mini",
    "o4-mini",
    "o3-mini",
    "o1-mini",
    "gpt-5.1-codex-mini",
    "codex-mini-latest",
    "gpt-5.4-nano",
    "gpt-5-nano",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "MiniMax M3 (OpenCode Go)",
    "GLM-5.2 (OpenCode Go)",
    "Qwen3.7 Max (OpenCode Go)",
    "DeepSeek V4 Flash",
    "Gemini 3.5 Flash",
    "Gemini 2.5 Flash",
    "Bedrock Claude 4.6 Sonnet",
    "Bedrock Claude 3.5 Sonnet",
    "Bedrock Claude 3 Haiku",
    "Bedrock Claude 3.5 Haiku",
    "Bedrock Llama 3.3 70B",
    "claude-haiku-4-5-20251001",
    "Özel (Custom)",
]

_ALIASES = {
    "deepseek v4 flash": "DeepSeek V4 Flash",
    "deepseek-v4-flash": "DeepSeek V4 Flash",
    "deepseek_v4_flash": "DeepSeek V4 Flash",
    "gemini 3.5 flash": "Gemini 3.5 Flash",
    "gemini-3.5-flash": "Gemini 3.5 Flash",
    "gemini_3.5_flash": "Gemini 3.5 Flash",
    "gemini 3.0 flash": "Gemini 3.5 Flash",
    "gemini-3.0-flash": "Gemini 3.5 Flash",
    "gemini_3.0_flash": "Gemini 3.5 Flash",
    "gemini 3 flash": "Gemini 3.5 Flash",
    "gemini-3-flash": "Gemini 3.5 Flash",
    "gemini 2.5 flash": "Gemini 2.5 Flash",
    "gemini-2.5-flash": "Gemini 2.5 Flash",
    "gemini_2.5_flash": "Gemini 2.5 Flash",
    "gpt-5.4-mini": "gpt-5.4-mini",
    "gpt-5.4 (reseller)": "GPT-5.4 (Reseller)",
    "gpt-5.4-reseller": "GPT-5.4 (Reseller)",
    "reseller gpt-5.4": "GPT-5.4 (Reseller)",
    "claude sonnet 5 (reseller)": "Claude Sonnet 5 (Reseller)",
    "claude-sonnet-5-reseller": "Claude Sonnet 5 (Reseller)",
    "claude-sonnet-5": "Claude Sonnet 5 (Reseller)",
    "reseller claude-sonnet-5": "Claude Sonnet 5 (Reseller)",
    "gpt-5-mini": "gpt-5-mini",
    "gpt-4o-mini": "gpt-4o-mini",
    "o4-mini": "o4-mini",
    "o3-mini": "o3-mini",
    "o1-mini": "o1-mini",
    "gpt-5.1-codex-mini": "gpt-5.1-codex-mini",
    "codex-mini-latest": "codex-mini-latest",
    "gpt-5.4-nano": "gpt-5.4-nano",
    "gpt-5-nano": "gpt-5-nano",
    "gpt-4.1-mini": "gpt-4.1-mini",
    "gpt-4.1-nano": "gpt-4.1-nano",
    "minimax m3": "MiniMax M3 (OpenCode Go)",
    "minimax-m3": "MiniMax M3 (OpenCode Go)",
    "opencode-go/minimax-m3": "MiniMax M3 (OpenCode Go)",
    "minimax m3 opencode go": "MiniMax M3 (OpenCode Go)",
    "minimax m3 (opencode go)": "MiniMax M3 (OpenCode Go)",
    "opencode go minimax m3": "MiniMax M3 (OpenCode Go)",
    "glm-5.2": "GLM-5.2 (OpenCode Go)",
    "glm 5.2": "GLM-5.2 (OpenCode Go)",
    "glm5.2": "GLM-5.2 (OpenCode Go)",
    "opencode-go/glm-5.2": "GLM-5.2 (OpenCode Go)",
    "glm 5.2 opencode go": "GLM-5.2 (OpenCode Go)",
    "glm-5.2 (opencode go)": "GLM-5.2 (OpenCode Go)",
    "opencode go glm 5.2": "GLM-5.2 (OpenCode Go)",
    "qwen3.7 max": "Qwen3.7 Max (OpenCode Go)",
    "qwen3.7-max": "Qwen3.7 Max (OpenCode Go)",
    "qwen 3.7 max": "Qwen3.7 Max (OpenCode Go)",
    "qwen3.7max": "Qwen3.7 Max (OpenCode Go)",
    "opencode-go/qwen3.7-max": "Qwen3.7 Max (OpenCode Go)",
    "qwen3.7 max opencode go": "Qwen3.7 Max (OpenCode Go)",
    "qwen3.7 max (opencode go)": "Qwen3.7 Max (OpenCode Go)",
    "opencode go qwen3.7 max": "Qwen3.7 Max (OpenCode Go)",
    "bedrock claude 4.6 sonnet": "Bedrock Claude 4.6 Sonnet",
    "bedrock-claude-4-6-sonnet": "Bedrock Claude 4.6 Sonnet",
    "bedrock-claude-4.6-sonnet": "Bedrock Claude 4.6 Sonnet",
    "anthropic.claude-sonnet-4-6": "Bedrock Claude 4.6 Sonnet",
    "bedrock claude 3.5 sonnet": "Bedrock Claude 3.5 Sonnet",
    "bedrock-claude-3-5-sonnet": "Bedrock Claude 3.5 Sonnet",
    "bedrock-claude-3.5-sonnet": "Bedrock Claude 3.5 Sonnet",
    "anthropic.claude-3-5-sonnet-20241022-v2:0": "Bedrock Claude 3.5 Sonnet",
    "bedrock claude 3 haiku": "Bedrock Claude 3 Haiku",
    "bedrock-claude-3-haiku": "Bedrock Claude 3 Haiku",
    "anthropic.claude-3-haiku-20240307-v1:0": "Bedrock Claude 3 Haiku",
    "bedrock claude 3.5 haiku": "Bedrock Claude 3.5 Haiku",
    "bedrock-claude-3-5-haiku": "Bedrock Claude 3.5 Haiku",
    "anthropic.claude-3-5-haiku-20241022-v1:0": "Bedrock Claude 3.5 Haiku",
    "bedrock llama 3.3 70b": "Bedrock Llama 3.3 70B",
    "bedrock-llama-3.3-70b": "Bedrock Llama 3.3 70B",
    "meta.llama3-3-70b-instruct-v1:0": "Bedrock Llama 3.3 70B",
    "claude-haiku-4-5-20251001": "claude-haiku-4-5-20251001",
    # MiniMax kaldırıldı — eski ayarlar otomatik olarak gpt-5.4-mini'ye göç eder
    "minimax m2.7": "gpt-5.4-mini",
    "minimax-m2.7": "gpt-5.4-mini",
    "minimax-m2_7": "gpt-5.4-mini",
    "minimax text 01": "gpt-5.4-mini",
    "minimax-text-01": "gpt-5.4-mini",
    "minimax m1": "gpt-5.4-mini",
    "minimax-m1": "gpt-5.4-mini",
    "abab6.5s-chat": "gpt-5.4-mini",
}

_CONFIGS = {
    "DeepSeek V4 Flash": HelperModelConfig(
        label="DeepSeek V4 Flash",
        provider="deepseek",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
    ),
    "Gemini 3.5 Flash": HelperModelConfig(
        label="Gemini 3.5 Flash",
        provider="openai",
        model="gemini-3.5-flash",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    ),
    "Gemini 2.5 Flash": HelperModelConfig(
        label="Gemini 2.5 Flash",
        provider="openai",
        model="gemini-2.5-flash",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    ),
    "gpt-5.4-mini": HelperModelConfig(
        label="gpt-5.4-mini",
        provider="openai",
        model="gpt-5.4-mini",
        base_url="https://api.openai.com/v1",
    ),
    "GPT-5.4 (Reseller)": HelperModelConfig(
        label="GPT-5.4 (Reseller)",
        provider="openai",
        model="gpt-5.4",
        base_url="https://api.shuaiapi.com/v1",
    ),
    "Claude Sonnet 5 (Reseller)": HelperModelConfig(
        label="Claude Sonnet 5 (Reseller)",
        provider="openai",
        model="claude-sonnet-5",
        base_url="https://api.shuaiapi.com/v1",
    ),
    "gpt-5-mini": HelperModelConfig(
        label="gpt-5-mini",
        provider="openai",
        model="gpt-5-mini",
        base_url="https://api.openai.com/v1",
    ),
    "gpt-4o-mini": HelperModelConfig(
        label="gpt-4o-mini",
        provider="openai",
        model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
    ),
    "o4-mini": HelperModelConfig(
        label="o4-mini",
        provider="openai",
        model="o4-mini",
        base_url="https://api.openai.com/v1",
    ),
    "o3-mini": HelperModelConfig(
        label="o3-mini",
        provider="openai",
        model="o3-mini",
        base_url="https://api.openai.com/v1",
    ),
    "o1-mini": HelperModelConfig(
        label="o1-mini",
        provider="openai",
        model="o1-mini",
        base_url="https://api.openai.com/v1",
    ),
    "gpt-5.1-codex-mini": HelperModelConfig(
        label="gpt-5.1-codex-mini",
        provider="openai",
        model="gpt-5.1-codex-mini",
        base_url="https://api.openai.com/v1",
    ),
    "codex-mini-latest": HelperModelConfig(
        label="codex-mini-latest",
        provider="openai",
        model="codex-mini-latest",
        base_url="https://api.openai.com/v1",
    ),
    "gpt-5.4-nano": HelperModelConfig(
        label="gpt-5.4-nano",
        provider="openai",
        model="gpt-5.4-nano",
        base_url="https://api.openai.com/v1",
    ),
    "gpt-5-nano": HelperModelConfig(
        label="gpt-5-nano",
        provider="openai",
        model="gpt-5-nano",
        base_url="https://api.openai.com/v1",
    ),
    "gpt-4.1-mini": HelperModelConfig(
        label="gpt-4.1-mini",
        provider="openai",
        model="gpt-4.1-mini",
        base_url="https://api.openai.com/v1",
    ),
    "gpt-4.1-nano": HelperModelConfig(
        label="gpt-4.1-nano",
        provider="openai",
        model="gpt-4.1-nano",
        base_url="https://api.openai.com/v1",
    ),
    "MiniMax M3 (OpenCode Go)": HelperModelConfig(
        label="MiniMax M3 (OpenCode Go)",
        provider="anthropic",
        model="minimax-m3",
        base_url="https://opencode.ai/zen/go/v1/messages",
    ),
    "GLM-5.2 (OpenCode Go)": HelperModelConfig(
        label="GLM-5.2 (OpenCode Go)",
        provider="openai",
        model="glm-5.2",
        base_url="https://opencode.ai/zen/go/v1",
    ),
    "Qwen3.7 Max (OpenCode Go)": HelperModelConfig(
        label="Qwen3.7 Max (OpenCode Go)",
        provider="anthropic",
        model="qwen3.7-max",
        base_url="https://opencode.ai/zen/go/v1/messages",
    ),
    "Bedrock Claude 4.6 Sonnet": HelperModelConfig(
        label="Bedrock Claude 4.6 Sonnet",
        provider="bedrock",
        model="anthropic.claude-sonnet-4-6",
        base_url="https://bedrock.dummy",
    ),
    "Bedrock Claude 3.5 Sonnet": HelperModelConfig(
        label="Bedrock Claude 3.5 Sonnet",
        provider="bedrock",
        model="anthropic.claude-3-5-sonnet-20241022-v2:0",
        base_url="https://bedrock.dummy",
    ),
    "Bedrock Claude 3 Haiku": HelperModelConfig(
        label="Bedrock Claude 3 Haiku",
        provider="bedrock",
        model="anthropic.claude-3-haiku-20240307-v1:0",
        base_url="https://bedrock.dummy",
    ),
    "Bedrock Claude 3.5 Haiku": HelperModelConfig(
        label="Bedrock Claude 3.5 Haiku",
        provider="bedrock",
        model="anthropic.claude-3-5-haiku-20241022-v1:0",
        base_url="https://bedrock.dummy",
    ),
    "Bedrock Llama 3.3 70B": HelperModelConfig(
        label="Bedrock Llama 3.3 70B",
        provider="bedrock",
        model="meta.llama3-3-70b-instruct-v1:0",
        base_url="https://bedrock.dummy",
    ),
    "claude-haiku-4-5-20251001": HelperModelConfig(
        label="claude-haiku-4-5-20251001",
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        base_url="https://147ai.online/v1/messages",
    ),
}


def normalize_helper_model_label(value: str) -> str:
    key = (value or "").strip()
    if key in _CONFIGS:
        return key
    return _ALIASES.get(key.lower(), "gpt-5.4-mini")


def resolve_helper_model(value: str) -> HelperModelConfig:
    key = normalize_helper_model_label(value)
    if key not in _CONFIGS:
        return _CONFIGS["gpt-5.4-mini"]
    return _CONFIGS[key]


def is_deepseek_helper_model(value: str) -> bool:
    return resolve_helper_model(value).provider == "deepseek"


def call_bedrock_converse(model_id: str, messages: list, temperature: float = None, max_tokens: int = None, api_key_str: str = None, base_url: str = None):
    import os
    try:
        import boto3
    except ImportError:
        raise RuntimeError("AWS Bedrock'ı kullanabilmek için lütfen 'boto3' kütüphanesini kurun: pip install boto3")

    # AWS Access Key ID, Secret Access Key ve Region bilgilerini parse et
    aws_access_key = None
    aws_secret_key = None
    region_name = None

    if api_key_str and api_key_str.strip() and not api_key_str.startswith("sk-") and not api_key_str.startswith("http"):
        parts = api_key_str.split(":")
        if len(parts) >= 2:
            aws_access_key = parts[0].strip()
            aws_secret_key = parts[1].strip()
            if len(parts) >= 3:
                region_name = parts[2].strip()

    if not region_name:
        if base_url and ("bedrock" in base_url or "aws" in base_url):
            import re
            m = re.search(r"bedrock-runtime\.([a-z0-9-]+)\.amazonaws\.com", base_url)
            if m:
                region_name = m.group(1)
        if not region_name:
            region_name = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION") or "eu-north-1"

    session_kwargs = {}
    if aws_access_key and aws_secret_key:
        session_kwargs["aws_access_key_id"] = aws_access_key
        session_kwargs["aws_secret_access_key"] = aws_secret_key
    if region_name:
        session_kwargs["region_name"] = region_name

    session = boto3.Session(**session_kwargs)
    client = session.client("bedrock-runtime")

    system_prompts = []
    bedrock_messages = []

    def _to_bedrock_content(content):
        if isinstance(content, str):
            return [{"text": content}]
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        parts.append({"text": part.get("text", "")})
                    elif part.get("type") == "image_url":
                        url = (part.get("image_url") or {}).get("url", "")
                        if url.startswith("data:") and "," in url:
                            import base64
                            meta, b64 = url.split(",", 1)
                            fmt = meta.split("/", 1)[1].split(";", 1)[0]
                            parts.append({
                                "image": {
                                    "format": fmt,
                                    "source": {"bytes": base64.b64decode(b64)},
                                }
                            })
            return parts or [{"text": ""}]
        return [{"text": str(content)}]

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role in ("system", "developer"):
            system_prompts.append({"text": content if isinstance(content, str) else str(content)})
        elif role in ("user", "assistant"):
            bedrock_messages.append({
                "role": role,
                "content": _to_bedrock_content(content)
            })

    converse_args = {
        "modelId": model_id,
        "messages": bedrock_messages
    }

    if system_prompts:
        converse_args["system"] = system_prompts

    inference_config = {}
    if temperature is not None:
        t = float(temperature)
        if t > 1.0:
            t = 1.0
        elif t < 0.0:
            t = 0.0
        inference_config["temperature"] = t

    if max_tokens is not None:
        inference_config["maxTokens"] = int(max_tokens)

    if inference_config:
        converse_args["inferenceConfig"] = inference_config

    try:
        response = client.converse(**converse_args)
    except Exception as e:
        raise RuntimeError(f"AWS Bedrock çağrısı başarısız oldu: {e}")

    output_text = response["output"]["message"]["content"][0]["text"]

    usage_data = response.get("usage", {})
    input_tokens = usage_data.get("inputTokens", 0)
    output_tokens = usage_data.get("outputTokens", 0)
    total_tokens = usage_data.get("totalTokens", 0)

    class DummyUsage:
        def __init__(self, in_t, out_t, tot_t):
            self.input_tokens = in_t
            self.output_tokens = out_t
            self.prompt_tokens = in_t
            self.completion_tokens = out_t
            self.total_tokens = tot_t

    class DummyChoice:
        def __init__(self, text):
            self.message = DummyMessage(text)
            self.finish_reason = "stop"

    class DummyMessage:
        def __init__(self, text):
            self.content = text
            self.role = "assistant"

    class DummyResponse:
        def __init__(self, text, in_t, out_t, tot_t):
            self.choices = [DummyChoice(text)]
            self.usage = DummyUsage(in_t, out_t, tot_t)

    return DummyResponse(output_text, input_tokens, output_tokens, total_tokens)


def _anthropic_messages_url(base_url: str | None) -> str:
    """Anthropic-compatible bir taban URL'yi tekil /v1/messages uç noktasına getirir."""
    url = (base_url or "https://api.anthropic.com/v1").strip().rstrip("/")
    if url.lower().endswith("/chat/completions"):
        url = url[:-17].rstrip("/")
    if url.lower().endswith("/messages"):
        return url
    if not url.lower().endswith("/v1"):
        url += "/v1"
    return url + "/messages"


def call_anthropic_messages(model_id: str, messages: list, temperature: float = None, max_tokens: int = None, api_key_str: str = None, base_url: str = None):
    import json
    import urllib.request
    import urllib.error

    system_prompt = ""
    anthropic_messages = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role in ("system", "developer"):
            if system_prompt:
                system_prompt += "\n" + content
            else:
                system_prompt = content
        else:
            anthropic_messages.append({"role": role, "content": content})

    data = {
        "model": model_id,
        "messages": anthropic_messages,
    }
    if system_prompt:
        data["system"] = system_prompt
    if temperature is not None:
        data["temperature"] = float(temperature)
    if max_tokens is not None:
        data["max_tokens"] = int(max_tokens)
    else:
        data["max_tokens"] = 1024

    headers = {
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
        "User-Agent": "SubtitleTranslator/2.0",
    }
    if api_key_str:
        url_check = (base_url or "").lower().rstrip("/")
        is_anthropic_native = url_check.endswith("/v1") or "api.anthropic.com" in url_check or url_check.endswith("/messages") or "opencode.ai" in url_check
        if is_anthropic_native:
            headers["x-api-key"] = api_key_str
        else:
            headers["Authorization"] = f"Bearer {api_key_str}"

    url = _anthropic_messages_url(base_url)

    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            res = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:2000]
        except Exception:
            body = "(okunamadı)"
        raise RuntimeError(f"Anthropic API çağrısı başarısız oldu: {e}\nYanıt: {body}")
    except Exception as e:
        raise RuntimeError(f"Anthropic API çağrısı başarısız oldu: {e}")

    output_text = ""
    for item in res.get("content", []):
        if item.get("type") == "text":
            output_text += item.get("text", "")

    usage_data = res.get("usage", {})
    input_tokens = usage_data.get("input_tokens", 0)
    output_tokens = usage_data.get("output_tokens", 0)
    total_tokens = input_tokens + output_tokens

    class DummyUsage:
        def __init__(self, in_t, out_t, tot_t):
            self.input_tokens = in_t
            self.output_tokens = out_t
            self.prompt_tokens = in_t
            self.completion_tokens = out_t
            self.total_tokens = tot_t

    class DummyChoice:
        def __init__(self, text):
            self.message = DummyMessage(text)
            self.finish_reason = "stop"

    class DummyMessage:
        def __init__(self, text):
            self.content = text
            self.role = "assistant"

    class DummyResponse:
        def __init__(self, text, in_t, out_t, tot_t):
            self.choices = [DummyChoice(text)]
            self.usage = DummyUsage(in_t, out_t, tot_t)

    return DummyResponse(output_text, input_tokens, output_tokens, total_tokens)


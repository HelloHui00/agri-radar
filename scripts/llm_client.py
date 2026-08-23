"""Direct LLM API client (OpenAI-compatible). Provider-agnostic.
Priority: env vars > config/server.json > hardcoded defaults.
"""
import os, json, urllib.request, urllib.error

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_llm_cfg():
    cfg = {"provider": os.environ.get("LLM_PROVIDER", "deepseek"),
           "base_url": os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1"),
           "model": os.environ.get("LLM_MODEL", "deepseek-chat"),
           "api_key_env": "LLM_API_KEY"}
    cfg_path = os.path.join(BASE_DIR, "config", "server.json")
    if os.path.exists(cfg_path):
        with open(cfg_path, encoding="utf-8") as f:
            file_cfg = json.load(f).get("llm", {})
            for k in ["provider", "base_url", "model"]:
                cfg[k] = file_cfg.get(k, cfg[k])
    return cfg

def chat(prompt, system=None, max_tokens=4096, temperature=0.3, timeout=300):
    cfg = load_llm_cfg()
    api_key = os.environ.get(cfg.get("api_key_env", "LLM_API_KEY"), "")
    if not api_key:
        raise RuntimeError(f"环境变量 {cfg.get('api_key_env', 'LLM_API_KEY')} 未设置")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = {"model": cfg["model"], "messages": messages,
            "max_tokens": max_tokens, "temperature": temperature}

    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    req = urllib.request.Request(url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key.strip()}"})

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:200]
        raise RuntimeError(f"LLM API error {e.code}: {detail}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"LLM 连接失败: {e.reason}")

    return result["choices"][0]["message"]["content"].strip()

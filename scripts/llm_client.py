"""Direct LLM API client (OpenAI-compatible). Provider-agnostic.

Reads config from config/server.json (llm section) and env vars.
"""
import os, json, urllib.request, urllib.error

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_llm_cfg():
    cfg_path = os.path.join(BASE_DIR, "config", "server.json")
    default = {"provider": "kimi", "model": "Kimi-K3",
               "base_url": "https://5625862916391497.cn-beijing.pai-eas.aliyuncs.com/api/predict/quickstart_deploy_20260805_mfh8/v1",
               "api_key_env": "LLM_API_KEY"}
    if not os.path.exists(cfg_path):
        return default
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg.get("llm", default)


def chat(prompt, system=None, max_tokens=4096, temperature=0.3, timeout=300):
    """Call an OpenAI-compatible chat completion API. Returns text."""
    cfg = load_llm_cfg()
    api_key = os.environ.get(cfg.get("api_key_env", "LLM_API_KEY"), "")
    if not api_key:
        raise RuntimeError(
            f"环境变量 {cfg.get('api_key_env', 'LLM_API_KEY')} 未设置，"
            f"请 export 该变量后重试")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": cfg["model"],
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    req = urllib.request.Request(url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"})

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:200]
        raise RuntimeError(f"LLM API error {e.code}: {detail}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"LLM 连接失败: {e.reason}")

    return result["choices"][0]["message"]["content"].strip()

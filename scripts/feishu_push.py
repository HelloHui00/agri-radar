"""Push the daily brief to a Feishu group bot (custom webhook).

Usage:
    # 真实推送
    python scripts/feishu_push.py brief_2026-08-23.md

    # 仅查看效果,不发送
    python scripts/feishu_push.py --dry-run brief_2026-08-23.md
"""
import sys, os, json, time, hashlib, base64, hmac, re
import urllib.request, urllib.parse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_server_cfg():
    cfg_path = os.path.join(BASE, "config", "server.json")
    if not os.path.exists(cfg_path):
        return {}
    try:
        with open(cfg_path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def resolve_feishu_credentials():
    """Return (webhook_url, secret) with env taking precedence over server.json.

    Priority:
      1. env FEISHU_WEBHOOK_URL / FEISHU_SECRET   (GitHub Actions secrets)
      2. config/server.json → feishu.webhook_url / feishu.secret  (local dev)

    Either may be empty.
    """
    env_url = os.environ.get("FEISHU_WEBHOOK_URL", "").strip()
    env_secret = os.environ.get("FEISHU_SECRET", "").strip()
    if env_url:
        return env_url, env_secret
    cfg = load_server_cfg()
    f = (cfg.get("feishu") or {})
    return (f.get("webhook_url", "") or "").strip(), \
           (f.get("secret", "") or "").strip()


def sign(timestamp, secret):
    """Feishu webhook signature."""
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(string_to_sign.encode("utf-8"),
                         digestmod=hashlib.sha256).digest()
    return base64.b64encode(hmac_code).decode("utf-8")


def convert_md_to_feishu(md_text, max_len=25000):
    """Markdown -> Feishu lark_md (chunked).
    Feishu 单条 lark_md 元素上限 30000 字节，留 buffer。"""
    # 清理开头/结尾非内容部分
    md_text = md_text.strip()
    # 去掉 LLM 可能加的 ```markdown ... ``` 外层包裹
    if md_text.startswith("```"):
        first_end = md_text.find("\n")
        if first_end > 0:
            md_text = md_text[first_end:].strip()
        if md_text.endswith("```"):
            md_text = md_text[:-3].strip()
    md_text = re.sub(r"^好的.*?[\r\n]+[-—=]+[\r\n]+", "", md_text)  # 去掉开场白
    md_text = re.sub(r"^#+\s*🌾", "🌾", md_text, flags=re.M)
    md_text = re.sub(r"\n{3,}", "\n\n", md_text)
    # 切掉结尾的 TRIAGE_RESULT / ```json 残留块
    for marker in ["TRIAGE_RESULT", "```json", " shown_ids"]:
        if marker in md_text:
            md_text = md_text[:md_text.index(marker)]
    md_text = md_text.rstrip()

    if len(md_text.encode("utf-8")) <= max_len:
        return [md_text]
    chunks, cur = [], ""
    for line in md_text.split("\n"):
        if len((cur + line + "\n").encode("utf-8")) > max_len:
            chunks.append(cur)
            cur = ""
        cur += line + "\n"
    if cur.strip():
        chunks.append(cur)
    return chunks


def build_card(markdown_text, date_str=None):
    """Build a Feishu interactive-card payload (测试验证过的格式)."""
    title = f"🌾 农业遥感日报 · {date_str or '今日'}"
    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "blue",
                "title": {"tag": "plain_text", "content": title}
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": markdown_text
                    }
                },
                {"tag": "hr"},
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": "💬 反馈: 「多推xx」「少推xx」「跟踪xx」 · 🤖 agri-radar"
                        }
                    ]
                }
            ]
        }
    }


def push(webhook_url, secret, payload):
    ts = str(int(time.time()))
    body = dict(payload)
    body["timestamp"] = ts
    body["sign"] = sign(ts, secret)
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook_url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: feishu_push.py [--dry-run] <brief.md>")
        sys.exit(1)
    dry_run = "--dry-run" in sys.argv
    md_path = [a for a in sys.argv[1:] if a != "--dry-run"][0]
    with open(md_path, encoding="utf-8") as f:
        md_text = f.read()

    # 推断日期
    date_str = None
    m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(md_path))
    if m:
        date_str = m.group(1)

    webhook_url, secret = resolve_feishu_credentials()
    chunks = convert_md_to_feishu(md_text)

    if dry_run:
        print(f"准备推送 {len(chunks)} 张卡片 (dry-run, 不实际发送)")
        print(f"credentials: webhook_url={'set' if webhook_url else 'MISSING'}, "
              f"secret={'set' if secret else 'MISSING'}")
        for i, c in enumerate(chunks):
            print(f"\n--- 卡片 {i + 1} ({len(c.encode('utf-8'))} bytes) ---")
            print(c[:500])
            if len(c) > 500:
                print(f"... 剩余 {len(c)-500} 字符")
        return

    if not webhook_url:
        print("ERROR: 未配置飞书 webhook。")
        print("      优先读取 env FEISHU_WEBHOOK_URL / FEISHU_SECRET,")
        print("      其次回落 config/server.json 中 feishu.webhook_url/secret。")
        sys.exit(1)

    for i, chunk in enumerate(chunks):
        payload = build_card(chunk, date_str)
        result = push(webhook_url, secret, payload)
        print(f"卡片 {i + 1} 推送结果: {result}")
        if i < len(chunks) - 1:
            time.sleep(1)  # 飞书频率限制


if __name__ == "__main__":
    main()

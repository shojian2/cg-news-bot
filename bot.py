#!/usr/bin/env python3
"""Generate a CG news digest with OpenAI and post it to Slack."""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


JST = timezone(timedelta(hours=9))
STATE_PATH = Path(os.getenv("STATE_PATH", "state/preferences.json"))
DEFAULT_CHANNEL_ID = "C0BF1N5GDFV"
DEFAULT_OWNER_ID = "U01MSCG4RUJ"
URL_RE = re.compile(r"https?://[^\s<>|]+")
DIRECTIVE_RE = re.compile(r"^\s*(方針|設定|除外|深掘り)\s*[:：]\s*(.+?)\s*$")


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


def http_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 180,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {"User-Agent": "cg-news-bot/1.0", **(headers or {})}
    if body is not None:
        request_headers.setdefault("Content-Type", "application/json; charset=utf-8")
    request = urllib.request.Request(
        url, data=body, headers=request_headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc


def slack_api(
    method: str,
    token: str,
    *,
    query: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"https://slack.com/api/{method}"
    if query:
        url += "?" + urllib.parse.urlencode(query)
    result = http_json(
        url,
        method="POST" if payload is not None else "GET",
        headers={"Authorization": f"Bearer {token}"},
        payload=payload,
    )
    if not result.get("ok"):
        raise RuntimeError(f"Slack API {method} failed: {result.get('error', result)}")
    return result


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    default = {
        "last_slack_ts": "0",
        "guidance": [],
        "exclusions": [],
        "deep_dive_queue": [],
        "recent_urls": [],
    }
    if not path.exists():
        return default
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return {**default, **loaded}


def save_state(state: dict[str, Any], path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_directives(messages: list[dict[str, Any]], owner_id: str) -> list[tuple[str, str, str]]:
    directives: list[tuple[str, str, str]] = []
    for message in sorted(messages, key=lambda item: float(item.get("ts", 0))):
        if message.get("user") != owner_id:
            continue
        for line in str(message.get("text", "")).splitlines():
            match = DIRECTIVE_RE.match(line)
            if match:
                directives.append((match.group(1), match.group(2), str(message["ts"])))
    return directives


def read_new_directives(
    token: str, channel_id: str, owner_id: str, state: dict[str, Any]
) -> list[str]:
    result = slack_api(
        "conversations.history",
        token,
        query={
            "channel": channel_id,
            "oldest": str(state.get("last_slack_ts", "0")),
            "inclusive": "false",
            "limit": "200",
        },
    )
    messages = result.get("messages", [])
    applied: list[str] = []
    for kind, value, ts in parse_directives(messages, owner_id):
        if kind in ("方針", "設定") and value not in state["guidance"]:
            state["guidance"].append(value)
        elif kind == "除外" and value not in state["exclusions"]:
            state["exclusions"].append(value)
        elif kind == "深掘り":
            state["deep_dive_queue"].append(value)
        applied.append(f"{kind}: {value}")
        state["last_slack_ts"] = max(
            str(state.get("last_slack_ts", "0")), ts, key=float
        )
    if messages:
        state["last_slack_ts"] = max(
            str(state.get("last_slack_ts", "0")),
            *(str(message.get("ts", "0")) for message in messages),
            key=float,
        )
    return applied


def extract_output_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"].strip()
    pieces: list[str] = []
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                pieces.append(content["text"])
    if not pieces:
        raise RuntimeError("OpenAI response did not contain output text")
    return "\n".join(pieces).strip()


def generate_digest(
    api_key: str, model: str, state: dict[str, Any], applied: list[str]
) -> str:
    now = datetime.now(JST)
    start = now - timedelta(days=7)
    deep_dive = state["deep_dive_queue"][0] if state["deep_dive_queue"] else "なし"
    recent_urls = [entry["url"] for entry in state["recent_urls"] if entry.get("url")]
    prompt = f"""
現在日時は {now:%Y-%m-%d %H:%M} JST。対象期間は {start:%Y-%m-%d %H:%M} から {now:%Y-%m-%d %H:%M} JST。

CG、リアルタイムレンダリング、グラフィックスプログラミング、ゲームエンジン、DCCツール、制作パイプラインの日本語朝刊を作成してください。Web検索を使い、各候補の公開日または実質更新日を一次情報で確認してください。

厳守事項:
- 通常トピックは上記7日間に初回公開または実質更新された情報だけ。日付を確認できない候補は除外。
- 公式リリースノート、公式ブログ、論文原典、標準団体、開発元・著者を優先。
- 二次情報は「報道」と明記。噂や性能主張を事実と混同しない。
- 同じ製品やAI/3DGSだけに偏らない。新着が少なければ3件未満でもよい。
- 過去の掲載URLは再掲載しない: {json.dumps(recent_urls[-100:], ensure_ascii=False)}
- Slack向けに簡潔にし、表は使わない。URLは <URL|短いラベル> の形式。
- 本文は原則2,500字以内。

現在の恒久方針:
{json.dumps(state['guidance'], ensure_ascii=False)}

除外対象:
{json.dumps(state['exclusions'], ensure_ascii=False)}

今回の深掘り指示: {deep_dive}
深掘りがある場合も中心ニュースは7日以内に限定。古い公式資料は「背景資料（7日以前）」と明記。

形式:
*CG / Real-Time / DCC 朝刊 — {now:%Y-%m-%d}*
対象期間: ... JST（過去7日間）

*今日の要点*
2〜3文

*注目トピック*
重要度順に3〜6件。各件にタイトル・種別、公開/更新日、最大2文の要約、実務への影響、原典URL。

深掘り指示がある場合だけ *深掘り* を追加し、400〜700字で仕組み・実務への影響・検証点を説明。

*今日のチェックポイント*
1〜3件

今回Slackから新しく反映した指示があれば末尾に *反映した指示* として記載: {json.dumps(applied, ensure_ascii=False)}
""".strip()
    response = http_json(
        "https://api.openai.com/v1/responses",
        method="POST",
        headers={"Authorization": f"Bearer {api_key}"},
        payload={
            "model": model,
            "reasoning": {"effort": "medium"},
            "tools": [{"type": "web_search"}],
            "input": prompt,
        },
        timeout=300,
    )
    return extract_output_text(response)


def post_digest(token: str, channel_id: str, text: str) -> str:
    result = slack_api(
        "chat.postMessage",
        token,
        payload={
            "channel": channel_id,
            "text": text[:39000],
            "unfurl_links": False,
            "unfurl_media": False,
        },
    )
    return str(result.get("ts", ""))


def update_recent_urls(state: dict[str, Any], digest: str) -> None:
    now = int(time.time())
    cutoff = now - 30 * 24 * 60 * 60
    existing = {
        entry["url"]: entry
        for entry in state["recent_urls"]
        if entry.get("url") and int(entry.get("seen_at", 0)) >= cutoff
    }
    for raw_url in URL_RE.findall(digest):
        url = raw_url.rstrip(".,。、）」)]}")
        existing[url] = {"url": url, "seen_at": now}
    state["recent_urls"] = sorted(existing.values(), key=lambda item: item["seen_at"])[-200:]


def main() -> int:
    api_key = require_env("OPENAI_API_KEY")
    slack_token = require_env("SLACK_BOT_TOKEN")
    channel_id = os.getenv("SLACK_CHANNEL_ID", DEFAULT_CHANNEL_ID)
    owner_id = os.getenv("SLACK_OWNER_USER_ID", DEFAULT_OWNER_ID)
    model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

    state = load_state()
    applied = read_new_directives(slack_token, channel_id, owner_id, state)
    digest = generate_digest(api_key, model, state, applied)
    post_digest(slack_token, channel_id, digest)
    update_recent_urls(state, digest)
    if state["deep_dive_queue"]:
        state["deep_dive_queue"].pop(0)
    save_state(state)
    print("Digest posted successfully.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # GitHub Actions should surface a concise failure.
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

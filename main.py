import os
import json
import requests
from slack_sdk import WebClient

COPILOT_API_KEY = os.getenv("COPILOT_API_KEY")
SLACK_TOKEN = os.getenv("SLACK_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL")

COPILOT_URL = "https://api.copilot.microsoft.com/v1/chat/completions"

def fetch_cg_news():
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {COPILOT_API_KEY}"
    }

    prompt = """
あなたは CG 技術ニュース専門のアシスタントです。
今週の CG 関連ニュースを収集し、以下のカテゴリ別に JSON 形式で返してください。

カテゴリ:
- Rendering
- DCC Tools
- Game Engines
- Research
- AI Generative

各ニュース項目は以下のフィールドを含むオブジェクトにしてください:
- タイトル
- 要点
- 技術的背景
- 実務的影響
- URL

出力は JSON のみ。
"""

    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"}
    }

    response = requests.post(COPILOT_URL, headers=headers, data=json.dumps(payload))
    return response.json()

def format_news(news_json):
    message = "【今週のCGニュースまとめ】\n\n"
    for category, items in news_json.items():
        message += f"■ {category}\n"
        for item in items:
            message += f"- *{item['タイトル']}*\n"
            message += f"  - {item['要点']}\n"
            message += f"  - {item['技術的背景']}\n"
            message += f"  - {item['実務的影響']}\n"
            message += f"  - {item['URL']}\n"
        message += "\n"
    return message

def post_to_slack(text):
    client = WebClient(token=SLACK_TOKEN)
    client.chat_postMessage(channel=SLACK_CHANNEL, text=text)

if __name__ == "__main__":
    news = fetch_cg_news()
    slack_message = format_news(news)
    post_to_slack(slack_message)

# cg-news-bot

毎日09:00 JSTに、過去7日以内のCG・リアルタイムレンダリング・DCC関連ニュースを `#codex_news` へ投稿するGitHub Actionsボットです。PCやCodexアプリを起動しておく必要はありません。

## 必要な設定

GitHubリポジトリの **Settings → Secrets and variables → Actions** で次を登録します。

### Secrets

- `OPENAI_API_KEY`: OpenAI PlatformのAPIキー（ChatGPT契約とは別にAPI課金設定が必要）
- `SLACK_BOT_TOKEN`: Slack AppのBot User OAuth Token（`xoxb-...`）

### Variables（省略可能）

- `OPENAI_MODEL`: 既定は `gpt-5.6-luna`
- `SLACK_CHANNEL_ID`: 既定は `C0BF1N5GDFV`
- `SLACK_OWNER_USER_ID`: 既定は `U01MSCG4RUJ`

Slack Appには次のBot Token Scopesを付け、`#codex_news` に招待してください。

- `chat:write`
- `channels:history`

## 軌道調整と深掘り

`#codex_news` にオーナーが以下の形式で投稿すると、次回実行時に読み取られます。

```text
方針: HoudiniとUSDを優先
設定: 論文より制作現場向け情報を多めに
除外: 未確認リーク
深掘り: Blender Cyclesの最新レンダリング更新
```

`方針`・`設定`・`除外` は `state/preferences.json` に保存され、以後も反映されます。`深掘り` は1回の朝刊で1件ずつ消化します。

## 手動テスト

Actionsの **Daily CG news → Run workflow** から実行できます。ローカルの単体テストは次で実行します。

```bash
python -m unittest discover -s tests -v
```

# Last30Days WeCom Daily Brief

This is a minimal cloud setup for running `mvanhorn/last30days-skill` every day
on GitHub Actions and sending the digest to an Enterprise WeChat group robot.

It does not need your WeChat or WeCom password. It only needs a revocable group
robot webhook URL stored in GitHub Secrets.

## What You Get

- A scheduled GitHub Actions workflow
- Manual trigger support from the GitHub UI
- A topic list in `config/topics.yml`
- Enterprise WeChat robot delivery
- Markdown and JSON artifacts saved for each run
- Optional API-key slots for richer sources

## First Setup

1. Create a new GitHub repository.
2. Copy these files into that repository.
3. In Enterprise WeChat, create a group such as `AI Daily Brief`.
4. Add a group robot and copy its webhook URL.
5. In GitHub, open `Settings -> Secrets and variables -> Actions -> New repository secret`.
6. Add this required secret:

```text
WECOM_BOT_WEBHOOK
```

7. Optional but useful secrets:

```text
OPENAI_API_KEY
GOOGLE_API_KEY
GEMINI_API_KEY
BRAVE_API_KEY
SERPER_API_KEY
EXA_API_KEY
SCRAPECREATORS_API_KEY
XAI_API_KEY
BSKY_HANDLE
BSKY_APP_PASSWORD
```

8. Edit `config/topics.yml`.
9. Open `Actions -> Daily Last30Days WeCom Brief -> Run workflow` to test it.

When running manually, the workflow shows an optional `topics` input. Enter
comma-separated or newline-separated topics there to override `config/topics.yml`
for that one run.

## Getting The WeCom Webhook

In Enterprise WeChat:

1. Create or open a group chat.
2. Open group settings.
3. Choose `Group Robot` / `群机器人`.
4. Add a robot, give it a name such as `AI Daily Brief`.
5. Copy the webhook URL.

The URL looks like this:

```text
https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...
```

Put that full URL into the GitHub secret named `WECOM_BOT_WEBHOOK`.

If your WeCom admin has disabled group robots, use a self-built WeCom app
instead. That path needs `CorpID`, `AgentID`, and `Secret`, so it is more
configuration than the group robot version.

## Schedule

The workflow currently runs at:

```yaml
cron: "30 0 * * *"
```

GitHub cron is UTC, so this is 08:30 Asia/Shanghai.

## Source Coverage

The skill decides where to search. Your keys decide which sources are available.

- No extra keys: Reddit, Hacker News, Polymarket, and some GitHub/web behavior
  can work in degraded/basic mode.
- `yt-dlp`: YouTube transcripts become more available.
- `BRAVE_API_KEY`, `SERPER_API_KEY`, or `EXA_API_KEY`: stronger web search.
- `SCRAPECREATORS_API_KEY`: TikTok, Instagram, Threads, Pinterest, and comments.
- `XAI_API_KEY` or X cookies: X/Twitter. For cloud deployments, API keys are
  cleaner than browser cookies.
- `BSKY_HANDLE` and `BSKY_APP_PASSWORD`: Bluesky.

## Can Topics Come From WeCom Messages?

Yes, but that is a second component.

GitHub Actions can run on a schedule and can accept manual inputs, but it cannot
directly receive messages from an Enterprise WeChat group. For WeCom messages to
control topics, add a small HTTPS receiver:

```text
WeCom self-built app or callback -> Cloudflare Worker / Tencent Cloud Function
-> GitHub repository_dispatch -> this workflow with TOPICS_TEXT
```

The current repo already supports the last step: dynamic topics can be passed as
the workflow `topics` input or the `TOPICS_TEXT` environment variable.

For the first version, keep daily topics in `config/topics.yml`. Add the WeCom
message receiver after the scheduled brief is stable.

## Safety Notes

- Do not put account passwords in this repo.
- Do not commit API keys.
- Use GitHub Secrets for every token, key, or webhook.
- If a token leaks, revoke it and create a new one.

## Local Dry Run

After cloning the upstream skill locally:

```bash
git clone --depth 1 https://github.com/mvanhorn/last30days-skill.git .last30days-skill
python scripts/daily_last30days.py --skill-dir .last30days-skill --dry-run
```

Dry run prints the message instead of sending it to WeCom.

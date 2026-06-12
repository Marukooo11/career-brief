# Last30Days Daily Brief

This is a minimal cloud setup for running `mvanhorn/last30days-skill` every day
on GitHub Actions and sending the digest by email.

It does not need your email account password if your provider supports app
passwords. Use an SMTP app password or token and store it in GitHub Secrets.

## What You Get

- A scheduled GitHub Actions workflow
- Manual trigger support from the GitHub UI
- A topic list in `config/topics.yml`
- Email delivery over SMTP
- Optional Enterprise WeChat robot delivery
- Markdown and JSON artifacts saved for each run
- Optional API-key slots for richer sources

## First Setup

1. Create a new GitHub repository.
2. Copy these files into that repository.
3. In GitHub, open `Settings -> Secrets and variables -> Actions -> New repository secret`.
4. Add these required email secrets:

```text
SMTP_HOST
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD
EMAIL_TO
```

Common examples:

```text
Gmail: SMTP_HOST=smtp.gmail.com, SMTP_PORT=587
QQ Mail: SMTP_HOST=smtp.qq.com, SMTP_PORT=465 or 587
Outlook: SMTP_HOST=smtp.office365.com, SMTP_PORT=587
163 Mail: SMTP_HOST=smtp.163.com, SMTP_PORT=465 or 994
```

`SMTP_PASSWORD` should normally be an app password or SMTP authorization code,
not your normal mailbox login password.

5. Optional delivery secrets:

```text
EMAIL_FROM
EMAIL_SUBJECT
WECOM_BOT_WEBHOOK
```

If `EMAIL_FROM` is empty, the script uses `SMTP_USERNAME`.

6. Optional but useful data-source secrets:

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

7. Edit `config/topics.yml`.
8. Open `Actions -> Daily Last30Days WeCom Brief -> Run workflow` to test it.

When running manually, the workflow shows an optional `topics` input. Enter
comma-separated or newline-separated topics there to override `config/topics.yml`
for that one run.

## Optional WeCom Webhook

Email is the default delivery method. WeCom is optional.

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

Then change the workflow env var:

```yaml
DELIVERY: both
```

Use `DELIVERY: wecom` if you want WeCom only.

If your WeCom admin has disabled group robots, use a self-built WeCom app
instead. That path needs `CorpID`, `AgentID`, and `Secret`, so it is more
configuration than the group robot version.

## Schedule

The workflow currently runs every 2 days at 12:00 Asia/Shanghai:

```yaml
cron: "0 4 */2 * *"
```

GitHub cron is UTC, so 12:00 Asia/Shanghai is 04:00 UTC.

## Source Coverage

The skill decides where to search. Your keys decide which sources are available.

For Chinese job-search intelligence, keep topic names in Chinese but write
English-heavy search terms. Each topic can use multiple query fields:

```yaml
query_jd: real job descriptions and hiring signals
query_companies: relevant companies and product examples
query_skills: skills, requirements, and interview keywords
query_learning: learning paths and capability-building advice
query_experience: practitioners' experience, interviews, and lessons learned
query_portfolio: portfolio projects and preparation ideas
```

The email output is Chinese.
If `OPENAI_API_KEY` is configured, ad-hoc Chinese manual topics are translated
into English search queries, and each source gets a short Chinese explanation.
Without a model key, the workflow still sends a Chinese-formatted email, but
English source titles and snippets remain mostly untranslated.

By default, each topic/search direction is sent as a separate email
(`SPLIT_EMAIL_BY_TOPIC=true`) so long briefs do not crowd out another direction.

The brief format is:

```text
主题
本次搜索拆分
找到多少条线索 / 来源分布
这个岗位大概做什么
常见工作内容
需要补的能力
求职关注点
岗位 JD / 招聘信号：相关来源观点
如何新增能力 / 学习路径：相关来源观点
岗位经验分享 / 从业者视角：相关来源观点
1. 来源标题
   观点总结：中文总结这条帖子/来源的核心观点和求职信号
   来源：平台/作者
   信号分：排序分
   链接：原文链接
```

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

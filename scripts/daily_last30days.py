#!/usr/bin/env python3
"""Run last30days topics and send a daily digest.

The workflow clones mvanhorn/last30days-skill, then calls this wrapper.
This file deliberately avoids storing secrets. Configure keys in GitHub
Actions secrets and pass them as environment variables.
"""

from __future__ import annotations

import argparse
import datetime as dt
import email.message
import json
import os
import re
import smtplib
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOPICS_FILE = ROOT / "config" / "topics.yml"


def load_topics(path: Path) -> list[dict[str, str]]:
    """Load a tiny topics.yml without requiring PyYAML."""
    text = path.read_text(encoding="utf-8")
    topics: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line == "topics:":
            continue
        if line.startswith("- "):
            if current:
                topics.append(current)
            current = {}
            line = line[2:].strip()
            if line:
                key, value = parse_yaml_pair(line)
                current[key] = value
            continue
        if current is not None and ":" in line:
            key, value = parse_yaml_pair(line)
            current[key] = value
    if current:
        topics.append(current)
    return [t for t in topics if t.get("query") or t.get("name")]


def load_topics_text(value: str) -> list[dict[str, str]]:
    topics: list[dict[str, str]] = []
    for part in re.split(r"[\n,]+", value):
        query = part.strip()
        if query:
            topics.append({"name": query, "query": query})
    return topics


def parse_yaml_pair(line: str) -> tuple[str, str]:
    key, value = line.split(":", 1)
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        value = value[1:-1]
    return key.strip(), value


def run_last30days(skill_dir: Path, topic: dict[str, str], timeout: int) -> dict[str, Any]:
    display_name = topic.get("name") or topic.get("query") or "未命名主题"
    query = topic.get("query") or topic["name"]
    query = maybe_translate_query(query)
    skill_dir = skill_dir.resolve()
    script = skill_dir / "skills" / "last30days" / "scripts" / "last30days.py"
    cmd = [
        sys.executable,
        str(script),
        query,
        "--emit=json",
        "--quick",
        "--lookback-days",
        os.getenv("LAST30DAYS_LOOKBACK_DAYS", "30"),
    ]
    result = subprocess.run(
        cmd,
        cwd=str(skill_dir),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        return {
            "name": topic.get("name", query),
            "query": query,
            "status": "failed",
            "error": (result.stderr or result.stdout)[-1200:],
        }

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "name": topic.get("name", query),
            "query": query,
            "status": "failed",
            "error": "last30days 返回的不是 JSON 输出",
            "raw": result.stdout[-1200:],
        }

    all_items = extract_items(payload)
    items = enrich_items_for_brief(all_items[: int(os.getenv("MAX_ITEMS_PER_TOPIC", "5"))])
    return {
        "name": display_name,
        "query": query,
        "status": "ok",
        "items": items,
        "source_counts": count_sources(all_items),
        "raw_count": len(all_items),
    }


def maybe_translate_query(query: str) -> str:
    """Convert ad-hoc Chinese topics into English search queries when possible."""
    if not contains_cjk(query) or not os.getenv("OPENAI_API_KEY"):
        return query
    prompt = (
        "把下面的中文求职/行业情报主题改写成适合英文社媒、新闻、论坛搜索的英文 query。"
        "只输出 query 本身，不要解释。保留核心职业、行业和 AI 关键词。\n\n"
        f"主题：{query}"
    )
    translated = call_openai_text(prompt, max_tokens=120)
    return translated or query


def contains_cjk(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value))


def enrich_items_for_brief(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not os.getenv("OPENAI_API_KEY"):
        for item in items:
            item["brief_summary"] = fallback_item_summary(item)
        return items

    enriched: list[dict[str, Any]] = []
    for item in items:
        summary = summarize_item_in_chinese(item)
        item["brief_summary"] = summary or fallback_item_summary(item)
        enriched.append(item)
    return enriched


def summarize_item_in_chinese(item: dict[str, Any]) -> str:
    title = item.get("title") or ""
    text = item.get("text") or ""
    source = item.get("source") or "unknown"
    prompt = (
        "你在帮一位中文产品经理找 AI+社区、AI+出海电商方向的工作机会和行业信号。"
        "请把下面这条英文或中文来源压缩成一句自然中文说明，说明它是什么、为什么可能有参考价值。"
        "不要编造链接、公司、岗位；不要超过 60 个中文字。\n\n"
        f"来源：{source}\n标题：{title}\n摘要：{text}"
    )
    return call_openai_text(prompt, max_tokens=180)


def call_openai_text(prompt: str, max_tokens: int = 200) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return ""
    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": "你是一个谨慎的中文研究助理，只基于给定材料总结。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return ""
    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )
    return clean_text(content)


def fallback_item_summary(item: dict[str, Any]) -> str:
    title = item.get("title") or "这条线索"
    text = item.get("text") or ""
    if text and text != title:
        return f"这是一条关于“{title}”的来源，摘要显示：{text[:120]}"
    return f"这是一条关于“{title}”的外部来源，可作为趋势或讨论线索继续查看。"


def extract_items(payload: Any) -> list[dict[str, Any]]:
    """Best-effort extraction from the upstream JSON schema."""
    if isinstance(payload, dict):
        ranked_candidates = payload.get("ranked_candidates")
        if isinstance(ranked_candidates, list) and ranked_candidates:
            return dedupe_and_sort(
                [normalize_item(item) for item in ranked_candidates if isinstance(item, dict)]
            )

        items_by_source = payload.get("items_by_source")
        if isinstance(items_by_source, dict) and items_by_source:
            source_items: list[dict[str, Any]] = []
            for source, items in items_by_source.items():
                if not isinstance(items, list):
                    continue
                for item in items:
                    if isinstance(item, dict):
                        merged = dict(item)
                        merged.setdefault("source", source)
                        source_items.append(merged)
            return dedupe_and_sort([normalize_item(item) for item in source_items])

    candidates: list[Any] = []
    if isinstance(payload, dict):
        for key in ("items", "results", "findings", "sources"):
            value = payload.get(key)
            if isinstance(value, list):
                candidates.extend(value)
    elif isinstance(payload, list):
        candidates = payload

    normalized = [normalize_item(item) for item in candidates if isinstance(item, dict)]
    return dedupe_and_sort(normalized)


def dedupe_and_sort(normalized: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in normalized:
        key = item.get("url") or f"{item.get('source')}:{item.get('title')}:{item.get('text')}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return sorted(deduped, key=lambda i: i.get("score", 0), reverse=True)


def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    title = first_text(item, "title", "source_title", "headline", "name")
    text = first_text(
        item,
        "snippet",
        "explanation",
        "why_relevant",
        "text",
        "content",
        "summary",
        "body",
        "description",
    )
    url = first_text(item, "url", "source_url", "permalink", "link")
    source = first_source(item)
    author = first_text(item, "author", "handle", "channel", "subreddit", "container")
    score = first_number(
        item,
        "final_score",
        "rerank_score",
        "rrf_score",
        "engagement_score",
        "score",
        "upvotes",
        "likes",
        "views",
        "comments",
    )
    return {
        "title": clean_text(title)[:160],
        "text": clean_text(text)[:320],
        "url": url,
        "source": source,
        "author": author,
        "score": score,
    }


def first_source(item: dict[str, Any]) -> str:
    sources = item.get("sources")
    if isinstance(sources, list):
        labels = [str(source).strip() for source in sources if str(source).strip()]
        if labels:
            return ", ".join(labels)
    return first_text(item, "source", "platform", "type") or "unknown"


def first_text(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
    return ""


def first_number(item: dict[str, Any], *keys: str) -> float:
    for key in keys:
        value = item.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            match = re.search(r"\d+(?:\.\d+)?", value.replace(",", ""))
            if match:
                return float(match.group(0))
    return 0.0


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def count_sources(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        source = str(item.get("source") or "unknown")
        counts[source] = counts.get(source, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def build_markdown(results: list[dict[str, Any]]) -> str:
    now = dt.datetime.now(dt.timezone.utc).astimezone()
    date_label = now.strftime("%Y-%m-%d")
    lines = [
        f"**AI 求职情报日报 - {date_label}**",
        "",
        f"> 主题数：{len(results)} | 由 GitHub Actions 自动生成",
        "",
    ]
    for result in results:
        name = result["name"]
        if result["status"] != "ok":
            lines.extend(
                [
                    f"**{name}**",
                    f"> 运行失败：{clean_text(result.get('error', '未知错误'))[:300]}",
                    "",
                ]
            )
            continue

        counts = ", ".join(f"{k}: {v}" for k, v in result.get("source_counts", {}).items())
        lines.append(f"**{name}**")
        lines.append(f"> 搜索词：{result.get('query', '')}")
        lines.append(f"> 找到 {result.get('raw_count', 0)} 条线索" + (f" | 来源分布：{counts}" if counts else ""))
        items = result.get("items", [])
        if not items:
            lines.append("- 暂时没有找到高信号线索。")
        for index, item in enumerate(items, start=1):
            title = item.get("title") or item.get("text") or "未命名线索"
            meta = " / ".join(
                str(part)
                for part in (item.get("source"), item.get("author"))
                if part
            )
            url = item.get("url")
            lines.append(f"{index}. **{title}**")
            lines.append(f"   这是什么：{item.get('brief_summary') or fallback_item_summary(item)}")
            if meta:
                lines.append(f"   来源：{meta}")
            if item.get("score"):
                lines.append(f"   信号分：{item['score']:g}")
            lines.append(f"   链接：{url if url else '暂无链接'}")
        lines.append("")
    return trim_wecom_markdown("\n".join(lines))


def trim_wecom_markdown(markdown: str) -> str:
    # WeCom robot markdown content has practical length limits. Keep the digest
    # readable and avoid rejected messages.
    limit = int(os.getenv("WECOM_MARKDOWN_LIMIT", "3800"))
    if len(markdown) <= limit:
        return markdown
    suffix = "\n\n> 内容过长，已截断。完整原始结果可在 GitHub Actions artifact 中查看。"
    return markdown[: limit - len(suffix)].rstrip() + suffix


def send_wecom(webhook: str, markdown: str, dry_run: bool) -> None:
    payload = {
        "msgtype": "markdown",
        "markdown": {"content": markdown},
    }
    if dry_run:
        print(markdown)
        return
    request = urllib.request.Request(
        webhook,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise SystemExit(f"WeCom delivery failed: {exc}") from exc
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise SystemExit(f"WeCom returned non-JSON response: {body}")
    if data.get("errcode") != 0:
        raise SystemExit(f"WeCom delivery failed: {body}")


def send_email(markdown: str, dry_run: bool) -> None:
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "")
    password = os.getenv("SMTP_PASSWORD", "")
    sender = os.getenv("EMAIL_FROM", username)
    recipients = split_recipients(os.getenv("EMAIL_TO", ""))
    subject = os.getenv("EMAIL_SUBJECT", "Last30Days Daily Brief")

    if dry_run:
        print(markdown)
        return
    missing = [
        name
        for name, value in {
            "SMTP_HOST": host,
            "SMTP_USERNAME": username,
            "SMTP_PASSWORD": password,
            "EMAIL_TO": ",".join(recipients),
        }.items()
        if not value
    ]
    if missing:
        raise SystemExit(f"邮件发送缺少这些 GitHub Secrets：{', '.join(missing)}")

    message = email.message.EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.set_content(markdown)
    message.add_alternative(markdown_to_html(markdown), subtype="html")

    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
            smtp.login(username, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(username, password)
            smtp.send_message(message)


def split_recipients(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,;\n]+", value) if part.strip()]


def markdown_to_html(markdown: str) -> str:
    html_lines: list[str] = []
    for line in markdown.splitlines():
        escaped = html_escape(line)
        escaped = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", escaped)
        escaped = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', escaped)
        if not line:
            html_lines.append("<br>")
        elif line.startswith("> "):
            html_lines.append(f"<blockquote>{escaped[5:]}</blockquote>")
        elif line.startswith("- "):
            html_lines.append(f"<p>{escaped}</p>")
        else:
            html_lines.append(f"<p>{escaped}</p>")
    return "\n".join(html_lines)


def html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def write_artifacts(results: list[dict[str, Any]], markdown: str, artifacts_dir: Path) -> None:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    date_label = dt.datetime.now().strftime("%Y-%m-%d")
    (artifacts_dir / f"{date_label}-brief.md").write_text(markdown, encoding="utf-8")
    (artifacts_dir / f"{date_label}-raw.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS_FILE)
    parser.add_argument(
        "--topics-text",
        default=os.getenv("TOPICS_TEXT", ""),
        help="Comma-separated or newline-separated topics. Overrides --topics.",
    )
    parser.add_argument("--skill-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--delivery",
        choices=("email", "wecom", "both"),
        default=os.getenv("DELIVERY", "email"),
    )
    parser.add_argument("--artifacts-dir", type=Path, default=ROOT / "artifacts")
    args = parser.parse_args()

    topics = load_topics_text(args.topics_text) if args.topics_text else load_topics(args.topics)
    if not topics:
        raise SystemExit(f"No topics found in {args.topics}")

    results = [run_last30days(args.skill_dir, topic, args.timeout) for topic in topics]
    markdown = build_markdown(results)
    write_artifacts(results, markdown, args.artifacts_dir)

    if args.delivery in ("email", "both"):
        send_email(markdown, args.dry_run)
    if args.delivery in ("wecom", "both"):
        webhook = os.getenv("WECOM_BOT_WEBHOOK", "")
        if not webhook and not args.dry_run:
            raise SystemExit(
                textwrap.dedent(
                    """
                    WECOM_BOT_WEBHOOK is missing.
                    Add your Enterprise WeChat group robot webhook to GitHub Secrets.
                    """
                ).strip()
            )
        send_wecom(webhook, markdown, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

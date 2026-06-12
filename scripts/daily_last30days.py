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

QUERY_FIELDS: list[tuple[str, str]] = [
    ("query_role", "岗位理解 / 工作内容"),
    ("query_learning", "如何新增能力 / 学习路径"),
    ("query_experience", "帖子经验 / 从业者观点"),
]

DISPLAY_SOURCE_CATEGORIES = {
    "如何新增能力 / 学习路径",
    "帖子经验 / 从业者观点",
}


ROLE_PROFILES: dict[str, dict[str, list[str]]] = {
    "AI + 社区产品经理": {
        "what": [
            "把社区、内容、用户关系和 AI 能力结合起来，提升用户留存、创作/交流效率、社区活跃和商业转化。",
            "常见场景包括 AI 社区运营工具、创作者社区、开发者社区、知识社区、社交产品、内容平台的 AI 功能。",
        ],
        "responsibilities": [
            "设计 AI 辅助发帖、内容分发、社群问答、用户匹配、内容审核、社区增长等功能。",
            "和运营/增长团队一起定义社区指标，例如活跃、留存、贡献率、内容质量、转化率。",
            "把用户反馈、社区讨论和数据指标转成产品需求，推动实验和迭代。",
        ],
        "skills": [
            "补社区/内容产品能力：拆 3 个社区产品的用户分层、激励机制、冷启动和治理策略。",
            "补 AI 产品判断力：选一个社区流程，设计 AI 辅助方案，并说明哪些环节不能完全自动化。",
            "补数据和增长能力：围绕活跃、留存、贡献率、内容质量设计一套实验和指标看板。",
        ],
        "signals": [
            "搜索关键词：community-led growth、creator community、AI social product、developer community、UGC moderation。",
            "作品集可以做：AI 社区助手、社区内容质检/推荐方案、创作者成长路径、用户反馈闭环分析。",
        ],
    },
    "AI + 出海电商产品经理": {
        "what": [
            "把 AI 能力用于跨境电商链路，帮助卖家、平台或品牌提升选品、上架、营销、客服、转化和履约效率。",
            "常见场景包括 Shopify/DTC、Amazon/TikTok Shop 卖家工具、跨境 SaaS、AI shopping assistant、广告/素材自动化。",
        ],
        "responsibilities": [
            "设计面向海外卖家或消费者的 AI 工具，例如商品文案、多语言本地化、广告素材、客服、选品分析。",
            "理解跨境电商业务链路：选品、供应链、刊登、营销投放、支付、物流、售后、合规。",
            "和运营、销售、算法/工程团队一起做转化率、GMV、留存、付费率等指标优化。",
        ],
        "skills": [
            "补电商链路能力：梳理选品、刊登、营销、支付、物流、售后、合规的完整卖家流程。",
            "补海外市场理解：定期研究 Shopify、Amazon、TikTok Shop、DTC 工具生态和卖家痛点。",
            "补 AI 落地能力：做一个多语言商品上架、广告素材或客服自动化的产品方案。",
        ],
        "signals": [
            "搜索关键词：global ecommerce、cross-border ecommerce、AI shopping assistant、DTC、Shopify app、TikTok Shop seller tools。",
            "作品集可以做：AI 商品上架助手、跨境卖家工作台、海外市场选品分析、AI 广告素材生成流程。",
        ],
    },
}


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
    topic_queries = get_topic_queries(topic)
    if not topic_queries:
        return {
            "name": display_name,
            "query": "",
            "queries": [],
            "status": "failed",
            "error": "没有可执行的搜索 query",
        }

    all_items: list[dict[str, Any]] = []
    shown_items: list[dict[str, Any]] = []
    failed_queries: list[str] = []
    query_labels: list[str] = []
    for category, query in topic_queries:
        query_labels.append(f"{category}：{query}")
        query_result = run_last30days_query(skill_dir, query, category, timeout)
        if query_result["status"] != "ok":
            failed_queries.append(f"{category}：{query_result.get('error', '未知错误')}")
            continue
        all_items.extend(query_result["all_items"])
        shown_items.extend(query_result["items"])

    research_items = dedupe_and_sort(shown_items)
    display_items = [
        item for item in research_items if item.get("category") in DISPLAY_SOURCE_CATEGORIES
    ][: int(os.getenv("MAX_ITEMS_PER_TOPIC", "8"))]
    display_items = enrich_items_for_brief(display_items)
    status = "ok" if research_items or all_items else "failed"
    return {
        "name": display_name,
        "query": "；".join(query_labels),
        "queries": [{"category": category, "query": query} for category, query in topic_queries],
        "status": status,
        "items": display_items,
        "role_brief": build_role_brief(display_name, "；".join(query_labels), research_items),
        "source_counts": count_sources(all_items),
        "raw_count": len(dedupe_and_sort(all_items)),
        "error": "；".join(failed_queries),
    }


def get_topic_queries(topic: dict[str, str]) -> list[tuple[str, str]]:
    queries: list[tuple[str, str]] = []
    for key, label in QUERY_FIELDS:
        query = topic.get(key, "").strip()
        if query:
            queries.append((label, maybe_translate_query(query)))
    if queries:
        return queries
    query = (topic.get("query") or topic.get("name") or "").strip()
    return [("综合搜索", maybe_translate_query(query))] if query else []


def run_last30days_query(
    skill_dir: Path, query: str, category: str, timeout: int
) -> dict[str, Any]:
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
            "query": query,
            "category": category,
            "status": "failed",
            "error": (result.stderr or result.stdout)[-1200:],
        }

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "query": query,
            "category": category,
            "status": "failed",
            "error": "last30days 返回的不是 JSON 输出",
            "raw": result.stdout[-1200:],
        }

    all_items = extract_items(payload)
    items = all_items[: int(os.getenv("MAX_ITEMS_PER_SEARCH", "4"))]
    for item in all_items:
        item["category"] = category
    return {
        "query": query,
        "category": category,
        "status": "ok",
        "items": items,
        "all_items": all_items,
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
            item["post_summary"] = fallback_post_summary(item)
        return items

    enriched: list[dict[str, Any]] = []
    for item in items:
        summary = summarize_post_for_job_search(item)
        item["post_summary"] = summary or fallback_post_summary(item)
        enriched.append(item)
    return enriched


def summarize_post_for_job_search(item: dict[str, Any]) -> str:
    title = item.get("title") or ""
    text = item.get("text") or ""
    source = item.get("source") or "unknown"
    prompt = (
        "你在帮一位中文产品经理做求职研究。请阅读下面这条帖子/经验/讨论来源，"
        "输出严格 JSON，不要 markdown。字段必须是 main、relevance、why_read。"
        "main：用中文概括帖子主要内容或核心观点；"
        "relevance：说明它和搜索主题、岗位工作内容或能力补充的具体关系；"
        "why_read：说明为什么值得读，最好指出能帮用户补哪类认知、简历素材或面试表达。"
        "每个字段 1 句话，具体一点，别编造原文没有的公司、岗位或数据。\n\n"
        f"来源：{source}\n标题：{title}\n摘要：{text}"
    )
    content = call_openai_text(prompt, max_tokens=420)
    if not content:
        return ""
    try:
        data = json.loads(strip_json_fence(content))
    except json.JSONDecodeError:
        return ""
    return json.dumps(
        {
            "main": clean_text(str(data.get("main", ""))),
            "relevance": clean_text(str(data.get("relevance", ""))),
            "why_read": clean_text(str(data.get("why_read", ""))),
        },
        ensure_ascii=False,
    )


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


def fallback_post_summary(item: dict[str, Any]) -> str:
    title = item.get("title") or "这条线索"
    text = item.get("text") or ""
    main = f"围绕“{title}”展开讨论。" if not text else f"围绕“{title}”，原文提到：{text[:120]}"
    relevance = "可用来判断该方向的真实工作内容、能力要求或从业者关注点。"
    why_read = "适合作为后续精读材料，帮助你提炼简历关键词、面试表达或作品集切入点。"
    return json.dumps(
        {"main": main, "relevance": relevance, "why_read": why_read},
        ensure_ascii=False,
    )


def parse_post_summary(item: dict[str, Any]) -> dict[str, str]:
    raw = item.get("post_summary") or fallback_post_summary(item)
    if isinstance(raw, dict):
        data = raw
    else:
        try:
            data = json.loads(str(raw))
        except json.JSONDecodeError:
            data = {"main": str(raw), "relevance": "", "why_read": ""}
    return {
        "main": clean_text(str(data.get("main", ""))),
        "relevance": clean_text(str(data.get("relevance", ""))),
        "why_read": clean_text(str(data.get("why_read", ""))),
    }


def format_post_summary_inline(item: dict[str, Any]) -> str:
    summary = parse_post_summary(item)
    parts = [
        f"主要内容：{summary['main']}" if summary["main"] else "",
        f"关联：{summary['relevance']}" if summary["relevance"] else "",
        f"推荐理由：{summary['why_read']}" if summary["why_read"] else "",
    ]
    return "；".join(part for part in parts if part)


def build_role_brief(topic_name: str, query: str, items: list[dict[str, Any]]) -> dict[str, list[str]]:
    if os.getenv("OPENAI_API_KEY"):
        model_brief = synthesize_role_brief(topic_name, query, items)
        if model_brief:
            return model_brief
    return ROLE_PROFILES.get(topic_name, fallback_role_profile(topic_name, query))


def synthesize_role_brief(
    topic_name: str, query: str, items: list[dict[str, Any]]
) -> dict[str, list[str]]:
    evidence = "\n".join(
        f"- 标题：{item.get('title', '')}\n  原始摘要：{item.get('text', '')}\n  帖子摘要：{format_post_summary_inline(item)}\n  来源：{item.get('source', '')}\n  链接：{item.get('url', '')}"
        for item in items[:8]
    )
    prompt = (
        "你在帮一位中文产品经理做求职方向研究。"
        "请基于给定岗位方向和来源，输出严格 JSON，不要 markdown。"
        "JSON 字段必须是 what、responsibilities、skills、signals，每个字段是 2-4 条中文短句。"
        "重点回答：这个岗位大概做什么，以及用户应该如何补足所需能力。"
        "skills 字段必须写成可执行的补能力动作，例如研究哪些产品、做什么练习、准备什么作品集材料。"
        "signals 字段写可转化成简历/作品集/面试表达的方向。"
        "如果来源不足，可以结合常识，但要保持谨慎，不要编造具体招聘信息。\n\n"
        f"岗位方向：{topic_name}\n搜索词：{query}\n来源：\n{evidence}"
    )
    content = call_openai_text(prompt, max_tokens=900)
    if not content:
        return {}
    try:
        parsed = json.loads(strip_json_fence(content))
    except json.JSONDecodeError:
        return {}
    brief: dict[str, list[str]] = {}
    for key in ("what", "responsibilities", "skills", "signals"):
        values = parsed.get(key)
        if isinstance(values, list):
            brief[key] = [clean_text(str(value)) for value in values if clean_text(str(value))][:4]
    return brief if brief else {}


def strip_json_fence(value: str) -> str:
    value = value.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    return value.strip()


def fallback_role_profile(topic_name: str, query: str) -> dict[str, list[str]]:
    return {
        "what": [f"这是围绕“{topic_name}”的求职研究方向，当前搜索词是：{query}。"],
        "responsibilities": ["重点关注岗位描述里的业务场景、核心指标、用户对象和 AI 功能落地点。"],
        "skills": ["重点提炼产品能力、行业理解、数据分析、AI 工作流和跨团队协作要求。"],
        "signals": ["建议补充更具体的行业、公司、平台或国家市场关键词，以提升搜索相关性。"],
    }


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
        f"**AI 产品经理求职方向研究 - {date_label}**",
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
        lines.append("> 本次搜索拆分：")
        for query_info in result.get("queries", []):
            lines.append(f"> - {query_info.get('category')}：{query_info.get('query')}")
        lines.append(f"> 找到 {result.get('raw_count', 0)} 条线索" + (f" | 来源分布：{counts}" if counts else ""))
        if result.get("error"):
            lines.append(f"> 部分搜索失败：{clean_text(result.get('error', ''))[:240]}")
        role_brief = result.get("role_brief") or {}
        append_brief_section(lines, "这个岗位大概做什么", role_brief.get("what", []))
        append_brief_section(lines, "需要补的能力，以及怎么补", role_brief.get("skills", []))
        append_brief_section(lines, "可转化成简历/作品集的方向", role_brief.get("signals", []))
        lines.append(
            "> 下面只展开学习路径和经验分享类来源；岗位/JD 类信息已用于上面的综合判断，不逐条列出。"
        )
        items = result.get("items", [])
        if not items:
            lines.append("**学习/经验类来源**")
            lines.append("- 暂时没有找到适合展开的学习路径或经验分享来源。")
        for category, category_items in group_items_by_category(items).items():
            lines.append(f"**{category}：相关来源观点**")
            for index, item in enumerate(category_items, start=1):
                title = item.get("title") or item.get("text") or "未命名线索"
                meta = " / ".join(
                    str(part)
                    for part in (item.get("source"), item.get("author"))
                    if part
                )
                url = item.get("url")
                post_summary = parse_post_summary(item)
                lines.append(f"{index}. **{title}**")
                if post_summary["main"]:
                    lines.append(f"   主要内容：{post_summary['main']}")
                if post_summary["relevance"]:
                    lines.append(f"   与搜索主题的关联：{post_summary['relevance']}")
                if post_summary["why_read"]:
                    lines.append(f"   推荐阅读理由：{post_summary['why_read']}")
                if meta:
                    lines.append(f"   来源：{meta}")
                if item.get("score"):
                    lines.append(f"   信号分：{item['score']:g}")
                lines.append(f"   链接：{url if url else '暂无链接'}")
        lines.append("")
    return trim_brief_markdown("\n".join(lines))


def append_brief_section(lines: list[str], title: str, items: list[str]) -> None:
    if not items:
        return
    lines.append(f"**{title}**")
    for item in items:
        lines.append(f"- {item}")


def group_items_by_category(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        category = str(item.get("category") or "综合来源")
        grouped.setdefault(category, []).append(item)
    return grouped


def trim_brief_markdown(markdown: str) -> str:
    limit = int(os.getenv("BRIEF_MARKDOWN_LIMIT", "12000"))
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


def send_email(markdown: str, dry_run: bool, subject_suffix: str = "") -> None:
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "")
    password = os.getenv("SMTP_PASSWORD", "")
    sender = os.getenv("EMAIL_FROM", username)
    recipients = split_recipients(os.getenv("EMAIL_TO", ""))
    subject = os.getenv("EMAIL_SUBJECT", "AI 产品经理求职方向研究")
    if subject_suffix:
        subject = f"{subject} - {subject_suffix}"

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
    for result in results:
        name = slugify(result.get("name", "topic"))
        topic_markdown = build_markdown([result])
        (artifacts_dir / f"{date_label}-{name}-brief.md").write_text(
            topic_markdown,
            encoding="utf-8",
        )


def slugify(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z\u3400-\u9fff]+", "-", value).strip("-")
    return slug[:80] or "topic"


def should_split_email_by_topic() -> bool:
    return os.getenv("SPLIT_EMAIL_BY_TOPIC", "true").lower() in {"1", "true", "yes", "on"}


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
        if should_split_email_by_topic() and len(results) > 1:
            for result in results:
                send_email(
                    build_markdown([result]),
                    args.dry_run,
                    subject_suffix=str(result.get("name", "未命名方向")),
                )
        else:
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

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
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOPICS_FILE = ROOT / "config" / "topics.yml"

QUERY_FIELDS: list[tuple[str, str]] = [
    ("query_role", "岗位理解 / 工作内容"),
    ("query_china_market", "中文关键词 / 本土讨论线索"),
    ("query_learning", "如何新增能力 / 学习路径"),
    ("query_experience", "帖子经验 / 从业者观点"),
]

DISPLAY_SOURCE_CATEGORIES = {
    "中文关键词 / 本土讨论线索",
    "如何新增能力 / 学习路径",
    "帖子经验 / 从业者观点",
}

ROLE_CONTEXTS: dict[str, str] = {
    "AI + 垂直行业产品经理（示例方向 A）": (
        "用户正在准备 AI + 垂直行业产品经理方向，重点关注 AI 如何进入某个具体行业的业务链路、"
        "工作流、效率工具、用户场景、商业指标和岗位能力要求。输出要优先服务面试表达、行业黑话理解和作品集选题。"
    ),
    "AI + 内容社区产品经理（示例方向 B）": (
        "用户正在准备 AI + 内容/社区类产品经理方向，重点关注内容生产、推荐分发、用户增长、社区治理、"
        "创作者生态和 AI 辅助工作流。输出要优先服务面试表达、行业黑话理解和作品集选题。"
    ),
}


ROLE_PROFILES: dict[str, dict[str, list[str]]] = {
    "AI + 内容社区产品经理（示例方向 B）": {
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
    "AI + 垂直行业产品经理（示例方向 A）": {
        "what": [
            "把 AI 能力用于某个垂直行业的核心业务链路，帮助用户提升信息处理、内容生成、决策辅助或运营效率。",
            "常见场景包括行业工作台、AI 助手、自动化流程、内容/素材生成、客户服务、数据分析和业务决策支持。",
        ],
        "responsibilities": [
            "理解目标行业的用户角色、业务流程、关键指标和高频痛点，并判断 AI 能落在哪些环节。",
            "设计面向业务用户的 AI 工具，例如信息整理、内容生成、流程自动化、推荐决策或客服辅助。",
            "和运营、业务、算法/工程团队一起定义需求、评估效果，并推动指标优化。",
        ],
        "skills": [
            "补行业理解：选择一个目标行业，梳理用户角色、业务链路、核心指标和典型工具。",
            "补 AI 落地能力：选择一个高频流程，设计 AI 辅助方案，并说明哪些环节需要人工确认。",
            "补作品集表达：把行业案例拆成问题、用户、方案、指标、风险和迭代路径。",
        ],
        "signals": [
            "搜索关键词：AI vertical product manager、industry workflow automation、AI assistant、B2B SaaS AI workflow。",
            "作品集可以做：行业 AI 工作台、AI 流程助手、业务知识库问答、自动化运营工具、智能分析看板。",
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
    ][: int(os.getenv("MAX_ITEMS_PER_TOPIC", "12"))]
    for item in display_items:
        item["topic_name"] = display_name
        item["topic_context"] = get_topic_context(display_name, topic)
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


def get_topic_context(topic_name: str, topic: dict[str, str] | None = None) -> str:
    if topic:
        custom_context = (topic.get("topic_context") or topic.get("context") or "").strip()
        if custom_context:
            return custom_context
    return ROLE_CONTEXTS.get(
        topic_name,
        f"用户正在围绕“{topic_name}”做求职研究，输出要优先服务岗位理解、面试表达和作品集选题。",
    )


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
    items = all_items[: int(os.getenv("MAX_ITEMS_PER_SEARCH", "8"))]
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
    topic = item.get("topic_name") or "这个求职方向"
    category = item.get("category") or "相关来源"
    topic_context = item.get("topic_context") or get_topic_context(topic)
    prompt = (
        "你在帮一位中文产品经理做求职研究。请阅读下面这条帖子/经验/讨论来源，"
        "输出严格 JSON，不要 markdown。字段必须是 main、relevance、why_read。"
        "main：用中文概括帖子主要内容或核心观点，正文不足时要明确说需要点开原文确认；"
        "relevance：必须具体说明它和目标岗位、业务场景、能力补充或面试表达的关系，不能只写“有助于了解行业”；"
        "why_read：说明为什么值得读，最好指出能补哪类认知、能提炼什么面试素材、或能启发什么作品集方向。"
        "如果这条来源和目标方向关联较弱，请直接说明“关联较弱”，不要强行拔高。"
        "每个字段 1 句话，具体一点，只基于给定材料，不要编造原文没有的公司、岗位或数据。\n\n"
        f"目标岗位：{topic}\n"
        f"用户背景：{topic_context}\n"
        f"搜索分类：{category}\n"
        f"来源：{source}\n"
        f"标题：{title}\n"
        f"摘要：{text}"
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
    topic = item.get("topic_name") or "这个方向"
    category = item.get("category") or "相关来源"
    source = item.get("source") or "unknown"
    topic_context = item.get("topic_context") or get_topic_context(topic)
    signal = infer_job_signal(title, text)
    main = build_fallback_main(title, text)
    relevance = build_fallback_relevance(topic, category, title, signal, topic_context)
    why_read = build_fallback_why_read(topic, category, title, source, signal, topic_context)
    return json.dumps(
        {"main": main, "relevance": relevance, "why_read": why_read},
        ensure_ascii=False,
    )


def build_fallback_main(title: str, text: str) -> str:
    if text and text != title:
        return f"围绕“{title}”，可见信息提到：{text[:140]}"
    return f"标题聚焦“{title}”，但当前数据源没有提供足够正文，需要点开原文确认具体观点。"


def build_fallback_relevance(
    topic: str, category: str, title: str, signal: str, topic_context: str
) -> str:
    if "中国市场" in category or "本土来源" in category:
        return f"它可能提供中文语境下的真实讨论，可用来补足“{topic}”的行业黑话、岗位表达和本土案例感；建议重点验证其中和“{signal}”相关的细节。"
    if "学习路径" in category:
        return f"它和“{topic}”的关系在于补足“{signal}”这类能力，可用来拆解学习顺序、练习任务或作品集补强点。"
    if "经验" in category or "从业者" in category:
        return f"它更接近从业者/讨论者视角，能帮助判断“{topic}”在实际工作中如何体现“{signal}”，并转成面试里的岗位理解。"
    return f"它可作为“{topic}”的辅助材料，重点观察其中是否真的出现“{signal}”；如果原文不涉及 {topic_context[:40]}，就应降低优先级。"


def build_fallback_why_read(
    topic: str, category: str, title: str, source: str, signal: str, topic_context: str
) -> str:
    source_hint = source if source and source != "unknown" else "原文"
    if "中国市场" in category or "本土来源" in category:
        return f"建议阅读是因为它可能包含中文平台上的岗位说法、业务词汇或案例线索，可提炼成面试中解释你为什么选择“{topic}”的素材。"
    if "学习路径" in category:
        return f"建议阅读是因为它可能把“{signal}”从抽象能力变成可执行练习，适合转成你的补能力计划或作品集任务。"
    if "经验" in category or "从业者" in category:
        return f"建议阅读是因为它可能提供“{source_hint}”上的真实表达和问题意识，可提炼成面试中解释你为什么选择“{topic}”的素材。"
    return f"建议阅读是因为标题“{title}”可能包含和“{topic}”相关的判断依据；需要点开原文确认它是否覆盖 {topic_context[:40]} 等关键场景。"


def infer_job_signal(title: str, text: str) -> str:
    content = f"{title} {text}".lower()
    keyword_signals = [
        (("portfolio", "作品集", "project", "项目", "case study"), "作品集项目设计"),
        (("interview", "面试", "面经"), "面试表达和岗位理解"),
        (("skill", "skills", "能力", "学习", "learning", "learn"), "能力补充路径"),
        (("growth", "增长", "retention", "留存", "activation"), "增长、留存和指标拆解"),
        (("community", "社区", "creator", "创作者", "ugc"), "社区机制、内容生态和用户关系"),
        (("ecommerce", "电商", "cross-border", "跨境", "shopify", "tiktok shop", "seller"), "电商链路、卖家工具和海外市场"),
        (("ai", "llm", "agent", "automation", "自动化"), "AI 功能落地和工作流自动化"),
        (("moderation", "审核", "trust", "治理", "safety"), "社区治理、信任和内容质量"),
        (("job", "hiring", "招聘", "岗位", "jd"), "招聘要求和岗位职责"),
    ]
    for keywords, signal in keyword_signals:
        if any(keyword in content for keyword in keywords):
            return signal
    return "岗位职责、能力要求或行业趋势"


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
    "重点回答：这个岗位大概做什么、核心工作链路、用户应该如何补足能力、哪些方向可转化为简历/作品集/面试表达。"
    "不要复述搜索词，不要写“当前搜索词是”，不要把 query 当成岗位介绍。"
    "每条中文短句尽量控制在 40-60 字以内，适合邮件阅读。"
    "skills 字段必须写成可执行的补能力动作，例如研究哪些产品、做什么练习、准备什么作品集材料。"
    "signals 字段写可转化成简历/作品集/面试表达的方向。"
    "如果来源不足，可以结合常识，但要保持谨慎，不要编造具体招聘信息。\n\n"
    f"岗位方向：{topic_name}\n搜索词：{query}\n来源：\n{evidence}"
    )
    content = call_openai_text(prompt, max_tokens=900)
    if not content:
        text = f"{topic_name} {query}"
        
        if "出海电商" in text or "跨境电商" in text:
            return {
            "what": [
                "把 AI 能力接入跨境电商链路，提升选品、搜索、导购、营销、客服和履约效率。",
                "典型场景包括 AI 导购、商品搜索推荐、评论问答、商家工具、广告素材生成和客服自动化。",
                "产品经理需要理解平台、商家和消费者三方关系，并把 AI 功能落到转化、复购和效率指标上。",
            ],
            "responsibilities": [
                "拆解跨境电商用户链路，判断哪些环节适合用 AI 提升效率或体验。",
                "设计搜索推荐、AI 导购、商品问答、商家工具或客服自动化等产品方案。",
                "和算法、运营、设计、数据团队协作，验证功能是否真的提升转化和留存。",
            ],
            "skills": [
                "补电商链路：梳理浏览、搜索、比较、下单、物流、售后和复购的完整流程。",
                "补海外市场：研究 Shopify、Amazon、TikTok Shop、DTC 独立站和跨境卖家工具。",
                "补 AI 落地：做一个 AI 导购、商品问答、Listing 优化或广告素材生成的产品方案。",
            ],
            "signals": [
                "作品集可以做 AI 导购助手、商品评论问答总结、跨境卖家工作台或海外选品分析。",
                "面试中可以讲 AI 如何嵌入搜索、推荐、客服、营销和复购链路，而不是只做单点功能。",
                "简历里可以突出你对电商链路、用户决策路径、业务指标和 AI 工作流的理解。",
            ],
        }
        if "社区" in text or "UGC" in text or "内容社区" in text:
            return {
                "what": [
                    "把 AI 能力接入内容社区和创作者生态，提升内容生产、分发、互动、治理和知识沉淀效率。",
                    "典型场景包括创作者工具、内容推荐、评论区治理、UGC 审核、内容质量评估和社区记忆沉淀。",
                    "产品经理需要理解内容生态、用户关系、社区规则和治理成本，并平衡增长与社区氛围。",
                ],
                "responsibilities": [
                    "拆解内容生产、推荐分发、互动反馈、关系沉淀和治理审核的完整链路。",
                    "设计 AI 创作者助手、内容治理工具、评论总结、社区知识库或风险识别方案。",
                    "和运营、审核、算法、设计团队协作，提升内容质量、社区氛围和治理效率。",
                ],
                "skills": [
                    "补社区产品能力：研究小红书、Reddit、Discord、即刻、豆瓣等社区的内容和关系机制。",
                    "补治理能力：研究 UGC 审核、举报机制、社区规则、内容安全和人机协同审核流程。",
                    "补 AI 落地能力：做一个 AI 社区治理助手、创作者选题助手或社区知识沉淀系统。",
                ],
                "signals": [
                    "作品集可以做 AI 社区治理助手、评论区风险识别、创作者内容分析或社区记忆系统。",
                    "面试中可以讲社区产品如何平衡内容质量、用户表达、平台规则和治理成本。",
                    "简历里可以突出你对内容生态、社区治理、用户关系和 AI 辅助审核的理解。",
                ],
            }

        return {
            "what": [
                f"这是围绕“{topic_name}”的求职研究方向。",
                "重点关注岗位职责、业务场景、能力要求、案例积累和作品集机会。",
                "建议结合具体行业、平台和目标岗位继续细化搜索关键词。",
            ],
            "responsibilities": [
                "拆解目标岗位的核心工作流程和业务场景。",
                "分析岗位需要的产品能力、行业知识、数据能力和协作方式。",
            ],
            "skills": [
                "补岗位基础能力：阅读 JD、行业案例和从业者经验，整理能力清单。",
                "补作品集能力：选择一个真实业务场景，完成产品分析或方案设计。",
            ],
            "signals": [
                "可以把高频案例整理成面试观点。",
                "可以把真实业务问题转化为作品集选题。",
            ],
        }
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
    text = f"{topic_name} {query}"

    if "出海电商" in text or "跨境电商" in text:
        return {
            "what": [
                "把 AI 能力接入跨境电商链路，提升选品、搜索、导购、营销、客服和履约效率。",
                "典型场景包括 AI 导购、商品搜索推荐、评论问答、商家工具、广告素材生成和客服自动化。",
                "产品经理需要理解平台、商家和消费者三方关系，并把 AI 功能落到转化、复购和效率指标上。",
            ],
            "responsibilities": [
                "拆解跨境电商用户链路，判断哪些环节适合用 AI 提升效率或体验。",
                "设计搜索推荐、AI 导购、商品问答、商家工具或客服自动化等产品方案。",
                "和算法、运营、设计、数据团队协作，验证功能是否真的提升转化和留存。",
            ],
            "skills": [
                "补电商链路：梳理浏览、搜索、比较、下单、物流、售后和复购的完整流程。",
                "补海外市场：研究 Shopify、Amazon、TikTok Shop、DTC 独立站和跨境卖家工具。",
                "补 AI 落地：做一个 AI 导购、商品问答、Listing 优化或广告素材生成的产品方案。",
            ],
            "signals": [
                "作品集可以做 AI 导购助手、商品评论问答总结、跨境卖家工作台或海外选品分析。",
                "面试中可以讲 AI 如何嵌入搜索、推荐、客服、营销和复购链路，而不是只做单点功能。",
                "简历里可以突出你对电商链路、用户决策路径、业务指标和 AI 工作流的理解。",
            ],
        }

    if "社区" in text or "UGC" in text or "内容社区" in text:
        return {
            "what": [
                "把 AI 能力接入内容社区和创作者生态，提升内容生产、分发、互动、治理和知识沉淀效率。",
                "典型场景包括创作者工具、内容推荐、评论区治理、UGC 审核、内容质量评估和社区记忆沉淀。",
                "产品经理需要理解内容生态、用户关系、社区规则和治理成本，并平衡增长与社区氛围。",
            ],
            "responsibilities": [
                "拆解内容生产、推荐分发、互动反馈、关系沉淀和治理审核的完整链路。",
                "设计 AI 创作者助手、内容治理工具、评论总结、社区知识库或风险识别方案。",
                "和运营、审核、算法、设计团队协作，提升内容质量、社区氛围和治理效率。",
            ],
            "skills": [
                "补社区产品能力：研究小红书、Reddit、Discord、即刻、豆瓣等社区的内容和关系机制。",
                "补治理能力：研究 UGC 审核、举报机制、社区规则、内容安全和人机协同审核流程。",
                "补 AI 落地能力：做一个 AI 社区治理助手、创作者选题助手或社区知识沉淀系统。",
            ],
            "signals": [
                "作品集可以做 AI 社区治理助手、评论区风险识别、创作者内容分析或社区记忆系统。",
                "面试中可以讲社区产品如何平衡内容质量、用户表达、平台规则和治理成本。",
                "简历里可以突出你对内容生态、社区治理、用户关系和 AI 辅助审核的理解。",
            ],
        }

    return {
        "what": [
            f"这是围绕“{topic_name}”的求职研究方向。",
            "重点关注岗位职责、业务场景、能力要求、案例积累和作品集机会。",
            "建议结合具体行业、平台和目标岗位继续细化搜索关键词。",
        ],
        "responsibilities": [
            "拆解目标岗位的核心工作流程和业务场景。",
            "分析岗位需要的产品能力、行业知识、数据能力和协作方式。",
        ],
        "skills": [
            "补岗位基础能力：阅读 JD、行业案例和从业者经验，整理能力清单。",
            "补作品集能力：选择一个真实业务场景，完成产品分析或方案设计。",
        ],
        "signals": [
            "可以把高频案例整理成面试观点。",
            "可以把真实业务问题转化为作品集选题。",
        ],
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
        append_result_section(lines, result)

    return trim_brief_markdown("\n".join(lines))


def append_result_section(lines: list[str], result: dict[str, Any]) -> None:
    name = result["name"]
    lines.append(f"**{name}**")

    if result["status"] != "ok":
        lines.append(f"> 运行失败：{clean_text(result.get('error', '未知错误'))[:300]}")
        lines.append("")
        return

    append_query_summary(lines, result)
    append_run_notes(lines, result)
    append_role_summary(lines, result)
    append_key_cases_section(lines, result.get("items", []), name)
    append_source_sections(lines, result.get("items", []))
    lines.append("")


def append_query_summary(lines: list[str], result: dict[str, Any]) -> None:
    counts = ", ".join(f"{k}: {v}" for k, v in result.get("source_counts", {}).items())

    lines.append("> 本次搜索拆分：")
    seen_categories: set[str] = set()
    for query_info in result.get("queries", []):
        category = query_info.get("category")
        if category and category not in seen_categories:
            lines.append(f"> - {category}")
            seen_categories.add(category)

    lines.append(
        f"> 找到 {result.get('raw_count', 0)} 条线索"
        + (f" | 来源分布：{counts}" if counts else "")
    )


def append_run_notes(lines: list[str], result: dict[str, Any]) -> None:
    if not os.getenv("OPENAI_API_KEY"):
        lines.append(
            "> 未配置 OPENAI_API_KEY：以下帖子摘要基于标题/摘要做弱分析；配置模型后会逐条理解原始内容并生成更贴合的中文总结。"
        )
    if result.get("error"):
        lines.append(f"> 部分搜索失败：{clean_text(result.get('error', ''))[:240]}")


def append_role_summary(lines: list[str], result: dict[str, Any]) -> None:
    role_brief = result.get("role_brief") or {}
    append_brief_section(lines, "这个岗位大概做什么", role_brief.get("what", []))
    append_brief_section(lines, "需要补的能力，以及怎么补", role_brief.get("skills", []))
    append_brief_section(lines, "可转化成简历/作品集的方向", role_brief.get("signals", []))


def append_source_sections(lines: list[str], items: list[dict[str, Any]]) -> None:
    lines.append(
        "> 下面展开中文关键词、学习路径和经验分享类来源；岗位/JD 类信息已用于上面的综合判断，不逐条列出。"
    )

    if not items:
        lines.append("**学习/经验类来源**")
        lines.append("- 暂时没有找到适合展开的学习路径或经验分享来源。")
        return

    for category, category_items in group_items_by_category(items).items():
        lines.append(f"**{category}：相关来源观点**")
        for index, item in enumerate(category_items[:3], start=1):
            append_source_item(lines, index, item)


def append_source_item(lines: list[str], index: int, item: dict[str, Any]) -> None:
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

def append_brief_section(lines: list[str], title: str, items: list[str]) -> None:
    if not items:
        return
    lines.append(f"**{title}**")
    for item in items:
        lines.append(f"- {item}")




def append_key_cases_section(lines: list[str], items: list[dict[str, Any]], topic_name: str) -> None:
    if not items:
        return

    lines.append("**今日可重点看的案例**")
    for index, item in enumerate(items[:3], start=1):
        title = item.get("title") or item.get("text") or "未命名线索"
        source = item.get("source") or "unknown"
        url = item.get("url") or "暂无链接"

        lines.append(f"{index}. **{title}**")
        lines.append(f"   - 来源：{source}")
        lines.append(f"   - 为什么值得看：可作为“{topic_name}”方向的案例线索，用来观察真实产品、业务问题或从业者讨论。")
        lines.append("   - 可转化方向：岗位理解、面试观点或作品集选题。")
        lines.append(f"   - 链接：{url}")
    lines.append("")

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
    parser.add_argument("--artifacts-dir", type=Path, default=ROOT / "artifacts")
    args = parser.parse_args()

    topics = load_topics_text(args.topics_text) if args.topics_text else load_topics(args.topics)
    if not topics:
        raise SystemExit(f"No topics found in {args.topics}")

    results = [run_last30days(args.skill_dir, topic, args.timeout) for topic in topics]
    markdown = build_markdown(results)
    write_artifacts(results, markdown, args.artifacts_dir)

    if should_split_email_by_topic() and len(results) > 1:
        for result in results:
            send_email(
                build_markdown([result]),
                args.dry_run,
                subject_suffix=str(result.get("name", "未命名方向")),
            )
    else:
        send_email(markdown, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""DeepResearch 最小数据流演示。

这是教学用模拟器，不会调用外部 LLM、数据库或 Milvus，也不会修改原项目。
它只展示 ResearchState、Agent 阶段、SSE 分块和前端事件解析之间的关系。
"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List


def initial_state(query: str) -> Dict[str, Any]:
    return {
        "query": query,
        "phase": "init",
        "outline": [],
        "facts": [],
        "data_points": [],
        "charts": [],
        "draft_sections": {},
        "final_report": "",
        "quality_score": 0.0,
    }


def event(event_type: str, content: Any) -> Dict[str, Any]:
    return {"type": event_type, "content": content}


def run_agents(state: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    """按项目当前 V2 简化流程的形状，逐阶段更新共享状态。"""
    state["phase"] = "planning"
    state["outline"] = [
        {"id": "sec_1", "title": "市场规模"},
        {"id": "sec_2", "title": "竞争格局"},
    ]
    yield event("research_step", {"phase": "planning", "outline_count": 2})

    state["phase"] = "researching"
    state["facts"] = [
        {"content": "示例事实：市场规模持续增长", "source_url": "demo://source/1"},
        {"content": "示例事实：头部企业集中度较高", "source_url": "demo://source/2"},
    ]
    state["data_points"] = [
        {"year": 2023, "value": 100},
        {"year": 2024, "value": 125},
    ]
    yield event("search_results", {"facts_count": len(state["facts"])})

    state["phase"] = "analyzing"
    state["charts"] = [{"id": "chart_1", "type": "line", "title": "示例趋势"}]
    yield event("charts", {"charts_count": len(state["charts"])})

    state["phase"] = "writing"
    state["draft_sections"] = {
        "sec_1": "市场规模章节草稿",
        "sec_2": "竞争格局章节草稿",
    }
    state["final_report"] = "示例研究报告：市场增长，竞争集中。"
    yield event("report_draft", {"length": len(state["final_report"])})

    state["phase"] = "reviewing"
    state["quality_score"] = 0.86
    yield event("research_complete", {
        "final_report": state["final_report"],
        "quality_score": state["quality_score"],
    })


def format_sse(events: Iterable[Dict[str, Any]]) -> Iterable[str]:
    yield "data: " + json.dumps({"type": "research_start"}, ensure_ascii=False) + "\n\n"
    for item in events:
        yield "data: " + json.dumps(item, ensure_ascii=False) + "\n\n"
    yield "data: [DONE]\n\n"


def parse_sse_chunks(chunks: Iterable[str]) -> List[Dict[str, Any]]:
    """模拟浏览器 ReadableStream：先缓冲，再按空行取完整 SSE 事件。"""
    buffer = ""
    parsed: List[Dict[str, Any]] = []
    for chunk in chunks:
        buffer += chunk
        while "\n\n" in buffer:
            block, buffer = buffer.split("\n\n", 1)
            if not block.startswith("data: "):
                continue
            payload = block[len("data: "):]
            if payload == "[DONE]":
                continue
            parsed.append(json.loads(payload))
    return parsed


def main() -> None:
    state = initial_state("分析新能源汽车行业未来三年的竞争格局")
    raw_sse = list(format_sse(run_agents(state)))

    # 故意把每条 SSE 切成不规则片段，模拟网络分块。
    wire_text = "".join(raw_sse)
    chunks = [wire_text[i:i + 13] for i in range(0, len(wire_text), 13)]
    received = parse_sse_chunks(chunks)

    print("事件顺序:", " -> ".join(item["type"] for item in received))
    print("最终阶段:", state["phase"])
    print("事实数量:", len(state["facts"]))
    print("图表数量:", len(state["charts"]))
    print("报告:", state["final_report"])


if __name__ == "__main__":
    main()

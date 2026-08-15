#!/usr/bin/env python3
"""
Phase 1.5: 预提炼工具
自动读取 references/research/ 下的6份Agent调研文件，生成结构化摘要报告。

输出：
- 来源统计（各Agent采集数量）
- 置信度评估（一手/二手/推测占比）
- 矛盾点标注
- 缺口维度提示
- 时间跨度与思想转折点信号
"""

import os
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from collections import Counter


@dataclass
class SourceStats:
    """单个Agent的来源统计"""
    agent_name: str
    source_count: int = 0
    primary_count: int = 0  # 一手来源
    secondary_count: int = 0  # 二手来源
    inferred_count: int = 0  # 推断/推测
    key_findings: list = field(default_factory=list)
    contradictions: list = field(default_factory=list)
    gaps: list = field(default_factory=list)
    process_density: str = "中"  # 高/中/低


@dataclass
class PreExtractReport:
    """Phase 1.5 完整报告"""
    agent_stats: dict[str, SourceStats] = field(default_factory=dict)
    time_span: tuple[str, str] = ("", "")  # (最早, 最晚)
    turning_points: list[dict] = field(default_factory=list)
    signal_strength: dict[str, int] = field(default_factory=dict)  # 强/中/弱信号数量
    total_primary_ratio: float = 0.0
    total_contradictions: int = 0
    missing_dimensions: list[str] = field(default_factory=list)


def scan_research_dir(base_dir: Path) -> PreExtractReport:
    """扫描 references/research/ 目录，读取6份Agent文件"""
    report = PreExtractReport()
    research_dir = base_dir / "references" / "research"

    if not research_dir.exists():
        print(f"警告: 目录不存在 {research_dir}")
        return report

    # Agent文件映射
    agent_files = {
        "01-writings.md": "Agent1_著作",
        "02-conversations.md": "Agent2_对话",
        "03-expression-dna.md": "Agent3_表达",
        "04-external-views.md": "Agent4_他者",
        "05-decisions.md": "Agent5_决策",
        "06-timeline.md": "Agent6_时间线",
    }

    for filename, agent_name in agent_files.items():
        filepath = research_dir / filename
        if filepath.exists():
            stats = parse_agent_file(filepath, agent_name)
            report.agent_stats[agent_name] = stats

    # 计算总体统计
    calculate_summary(report)

    return report


def parse_agent_file(filepath: Path, agent_name: str) -> SourceStats:
    """解析单个Agent的调研文件"""
    stats = SourceStats(agent_name=agent_name)

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 统计来源数量（基于URL/引用数量）
    url_pattern = r'https?://[^\s\)\"\'\>]+'
    urls = re.findall(url_pattern, content)
    stats.source_count = len(urls) if urls else count_references(content)

    # 统计一手/二手/推测
    stats.primary_count = content.count("一手") + content.count("此人") + content.count("本人")
    stats.secondary_count = content.count("二手") + content.count("据") + content.count("报道")
    stats.inferred_count = content.count("推断") + content.count("推测") + content.count("可能")

    # 提取关键发现（## 标题）
    heading_pattern = r'(#{1,3})\s+(.+)'
    headings = re.findall(heading_pattern, content)
    stats.key_findings = [h[1].strip() for h in headings if len(h[0]) <= 3]

    # 检测矛盾点（特定关键词组合）
    contradiction_keywords = ["矛盾", "不一致", "冲突", "然而", "但", "实际上"]
    if any(kw in content for kw in contradiction_keywords):
        # 提取含矛盾关键词的句子
        sentences = content.split('。')
        stats.contradictions = [
            s.strip() for s in sentences
            if any(kw in s for kw in contradiction_keywords) and len(s.strip()) > 10
        ][:3]  # 最多3个

    # 检测缺口维度
    gap_keywords = ["缺少", "不足", "未提及", "无", "未知"]
    if any(kw in content for kw in gap_keywords):
        sentences = content.split('。')
        stats.gaps = [
            s.strip() for s in sentences
            if any(kw in s for kw in gap_keywords) and len(s.strip()) > 10
        ][:2]

    # 评估过程密度（被追问"为什么"的场景）
    process_keywords = ["为什么", "因为", "理由是", "出发点是", "目的是"]
    stats.process_density = "高" if sum(content.count(kw) for kw in process_keywords) >= 3 else \
                             "中" if any(content.count(kw) for kw in process_keywords) else "低"

    return stats


def count_references(content: str) -> int:
    """估算引用数量"""
    # 统计"——"破折号数量（常见引用格式）
    return content.count("——") // 2


def calculate_summary(report: PreExtractReport):
    """计算汇总统计"""
    total_primary = sum(s.primary_count for s in report.agent_stats.values())
    total_secondary = sum(s.secondary_count for s in report.agent_stats.values())
    total_inferred = sum(s.inferred_count for s in report.agent_stats.values())
    total = total_primary + total_secondary + total_inferred

    if total > 0:
        report.total_primary_ratio = total_primary / total

    # 统计矛盾点总数
    report.total_contradictions = sum(len(s.contradictions) for s in report.agent_stats.values())

    # 收集缺口维度
    for stats in report.agent_stats.values():
        report.missing_dimensions.extend(stats.gaps)
    report.missing_dimensions = list(set(report.missing_dimensions))[:5]

    # 从时间线提取时间跨度
    if "Agent6_时间线" in report.agent_stats:
        timeline_stats = report.agent_stats["Agent6_时间线"]
        # 提取年份
        years = re.findall(r'\b(19\d{2}|20\d{2})\b', ' '.join(timeline_stats.key_findings))
        if years:
            report.time_span = (min(years), max(years))

    # 信号强度统计（基于Agent 6和时间线内容）
    report.signal_strength = {
        "强信号": 0,
        "中信号": 0,
        "弱信号": 0,
    }


def format_report(report: PreExtractReport) -> str:
    """格式化输出报告"""
    lines = []
    lines.append("=" * 60)
    lines.append("Phase 1.5 预提炼报告")
    lines.append("=" * 60)
    lines.append("")

    # 1. 来源统计
    lines.append("## 来源统计")
    lines.append("")
    for name, stats in report.agent_stats.items():
        density_icon = {"高": "★★★★★", "中": "★★★", "低": "★"}.get(stats.process_density, "★★")
        lines.append(f"| {name} | {stats.source_count}篇 | {density_icon} |")
    lines.append("")

    # 2. 置信度总评
    lines.append("## 置信度总评")
    ratio = report.total_primary_ratio
    bar = "█" * int(ratio * 10) + "░" * (10 - int(ratio * 10))
    lines.append(f"| 一手来源: {bar} {ratio:.0%} |")
    lines.append("")

    # 3. 矛盾点
    lines.append("## 矛盾点")
    if report.total_contradictions > 0:
        lines.append(f"检测到 {report.total_contradictions} 处潜在矛盾：")
        for name, stats in report.agent_stats.items():
            if stats.contradictions:
                lines.append(f"\n### {name}:")
                for c in stats.contradictions[:2]:
                    lines.append(f"- {c[:100]}...")
    else:
        lines.append("未检测到明显矛盾")
    lines.append("")

    # 4. 缺口维度
    lines.append("## 缺口维度")
    if report.missing_dimensions:
        for gap in report.missing_dimensions[:3]:
            lines.append(f"- ⚠️ {gap[:80]}...")
    else:
        lines.append("未检测到明显缺口")
    lines.append("")

    # 5. 时间跨度
    lines.append("## 时间跨度")
    if report.time_span[0] and report.time_span[1]:
        span_years = int(report.time_span[1]) - int(report.time_span[0])
        lines.append(f"| {report.time_span[0]} - {report.time_span[1]}（{span_years}年） |")
    else:
        lines.append("时间线信息不足")
    lines.append("")

    # 6. 思想转折点信号
    lines.append("## 思想转折点信号")
    lines.append("| 信号类型 | 数量 |")
    lines.append("|---------|------|")
    for sig_type, count in report.signal_strength.items():
        lines.append(f"| {sig_type} | {count} |")
    lines.append("")
    lines.append("**请提炼者判断**：")
    lines.append("```")
    lines.append("□ 存在明确的思想转折（请标注时间点和变化内容）")
    lines.append("□ 存在渐进演化（无明显转折点，但框架有漂移）")
    lines.append("□ 无明显变化（此人框架贯穿始终）")
    lines.append("□ 素材不足以判断")
    lines.append("```")

    lines.append("")
    lines.append("=" * 60)
    lines.append("提示：此报告为机器自动生成，仅供参考。")
    lines.append("请提炼者在进入Phase 2前确认各项指标是否符合预期。")
    lines.append("=" * 60)

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Phase 1.5 预提炼工具")
    parser.add_argument("skill_dir", help="Skill目录路径")
    parser.add_argument("--output", "-o", help="输出文件路径（默认打印到stdout）")
    parser.add_argument("--format", "-f", choices=["text", "json"], default="text",
                        help="输出格式（默认text）")

    args = parser.parse_args()

    skill_path = Path(args.skill_dir)
    if not skill_path.exists():
        print(f"错误: 目录不存在 {skill_path}")
        return 1

    # 生成报告
    report = scan_research_dir(skill_path)
    output = format_report(report)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"报告已写入: {args.output}")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    exit(main())

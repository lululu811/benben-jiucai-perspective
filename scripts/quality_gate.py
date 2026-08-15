#!/usr/bin/env python3
"""
质量门禁脚本 v3.0

自动检查Phase 1的6个Agent输出文件质量，不达标自动拦截。

用法：
    python3 quality_gate.py [skill目录]

输出：
    - 各项检查的PASS/FAIL
    - 总体质量评级（A/B/C/D/F）
    - 具体改进建议

退出码：
    0: 质量可接受，进入Phase 2
    1: 质量不足，需要补充采集
    2: 严重不足，建议降低期望或更换蒸馏对象
"""

import sys
import re
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass

@dataclass
class QualityCheck:
    """质量检查结果"""
    name: str
    passed: bool
    actual: str
    expected: str
    suggestion: str = ""

@dataclass
class AgentStats:
    """单个Agent的统计信息"""
    name: str
    file: Path
    exists: bool = False
    source_count: int = 0
    primary_source_ratio: float = 0.0
    has_confidence_labels: bool = False
    has_contradictions: bool = False
    has_gaps: bool = False
    process_density_high: int = 0
    process_density_medium: int = 0
    process_density_low: int = 0

def parse_stats_file(file_path: Path) -> AgentStats:
    """解析单个Agent的输出文件"""
    stats = AgentStats(name=file_path.stem, file=file_path)

    if not file_path.exists():
        return stats

    stats.exists = True
    content = file_path.read_text(encoding='utf-8')

    # 提取来源统计
    # 匹配模式："书籍：X本"、"播客：X段"、"来源统计"后的数字
    source_patterns = [
        r'书籍[：:]\s*(\d+)',
        r'长文[：:]\s*(\d+)',
        r'论文[：:]\s*(\d+)',
        r'Newsletter[：:]\s*(\d+)',
        r'播客[：:]\s*(\d+)',
        r'长视频[：:]\s*(\d+)',
        r'AMA[：:]\s*(\d+)',
        r'深度采访[：:]\s*(\d+)',
        r'Twitter/X[：:]\s*(\d+)',
        r'微博[：:]\s*(\d+)',
        r'即刻[：:]\s*(\d+)',
        r'短文[：:]\s*(\d+)',
        r'书评[：:]\s*(\d+)',
        r'同行评价[：:]\s*(\d+)',
        r'批评文章[：:]\s*(\d+)',
        r'重大决策[：:]\s*(\d+)',
        r'事后反思[：:]\s*(\d+)',
        r'传记[：:]\s*(\d+)',
    ]

    for pattern in source_patterns:
        matches = re.findall(pattern, content)
        stats.source_count += sum(int(m) for m in matches)

    # 提取一手来源占比
    ratio_match = re.search(r'一手来源占比[：:]\s*(\d+)%', content)
    if ratio_match:
        stats.primary_source_ratio = int(ratio_match.group(1)) / 100

    # 检查置信度标注
    stats.has_confidence_labels = bool(re.search(r'置信度[：:].*[🟢🟡🔴]', content))

    # 检查矛盾标注
    stats.has_contradictions = bool(re.search(r'矛盾与张力', content))

    # 检查缺口标注
    stats.has_gaps = bool(re.search(r'缺口与不足', content))

    # 统计过程密度
    stats.process_density_high = len(re.findall(r'过程密度[：:]高', content))
    stats.process_density_medium = len(re.findall(r'过程密度[：:]中', content))
    stats.process_density_low = len(re.findall(r'过程密度[：:]低', content))

    return stats

def check_file_exists(stats: AgentStats) -> QualityCheck:
    """检查文件是否存在"""
    return QualityCheck(
        name=f"{stats.name} 文件存在",
        passed=stats.exists,
        actual="存在" if stats.exists else "不存在",
        expected="存在",
        suggestion="运行对应Agent生成文件" if not stats.exists else ""
    )

def check_source_count(stats: AgentStats, min_count: int = 5) -> QualityCheck:
    """检查来源数量"""
    return QualityCheck(
        name=f"{stats.name} 来源数量",
        passed=stats.source_count >= min_count,
        actual=f"{stats.source_count}条",
        expected=f"≥{min_count}条",
        suggestion=f"补充采集更多来源" if stats.source_count < min_count else ""
    )

def check_primary_ratio(stats: AgentStats, min_ratio: float = 0.4) -> QualityCheck:
    """检查一手来源占比"""
    return QualityCheck(
        name=f"{stats.name} 一手来源占比",
        passed=stats.primary_source_ratio >= min_ratio,
        actual=f"{stats.primary_source_ratio*100:.0f}%",
        expected=f"≥{min_ratio*100:.0f}%",
        suggestion="增加一手来源（著作、访谈原文、决策记录）" if stats.primary_source_ratio < min_ratio else ""
    )

def check_confidence_labels(stats: AgentStats) -> QualityCheck:
    """检查置信度标注"""
    return QualityCheck(
        name=f"{stats.name} 置信度标注",
        passed=stats.has_confidence_labels,
        actual="有" if stats.has_confidence_labels else "无",
        expected="有",
        suggestion="为每条信息标注置信度（🟢高/🟡中/🔴低）" if not stats.has_confidence_labels else ""
    )

def check_contradictions(stats: AgentStats) -> QualityCheck:
    """检查矛盾标注"""
    return QualityCheck(
        name=f"{stats.name} 矛盾标注",
        passed=stats.has_contradictions,
        actual="有" if stats.has_contradictions else "无",
        expected="有（即使无矛盾也要标注'无'）",
        suggestion="添加'矛盾与张力'section" if not stats.has_contradictions else ""
    )

def check_gaps(stats: AgentStats) -> QualityCheck:
    """检查缺口标注"""
    return QualityCheck(
        name=f"{stats.name} 缺口标注",
        passed=stats.has_gaps,
        actual="有" if stats.has_gaps else "无",
        expected="有",
        suggestion="添加'缺口与不足'section" if not stats.has_gaps else ""
    )

def check_process_density(stats: AgentStats) -> QualityCheck:
    """检查过程密度（针对Agent 2和Agent 5）"""
    total = stats.process_density_high + stats.process_density_medium + stats.process_density_low
    high_ratio = stats.process_density_high / total if total > 0 else 0

    return QualityCheck(
        name=f"{stats.name} 过程密度",
        passed=high_ratio >= 0.3 or total == 0,
        actual=f"高:{stats.process_density_high} 中:{stats.process_density_medium} 低:{stats.process_density_low}",
        expected="高密度占比≥30%",
        suggestion="补充更多被追问'为什么'的完整推理链" if high_ratio < 0.3 and total > 0 else ""
    )

def run_quality_gate(skill_dir: Path) -> Tuple[List[QualityCheck], str]:
    """运行完整质量门禁"""
    checks: List[QualityCheck] = []
    agent_files = [
        "01-writings.md",
        "02-conversations.md",
        "03-expression-dna.md",
        "04-external-views.md",
        "05-decisions.md",
        "06-timeline.md"
    ]

    agent_stats = []
    for file_name in agent_files:
        file_path = skill_dir / "references" / "research" / file_name
        stats = parse_stats_file(file_path)
        agent_stats.append(stats)

    # 检查每个Agent
    for stats in agent_stats:
        checks.append(check_file_exists(stats))
        if stats.exists:
            # 根据Agent类型调整最低来源数
            min_sources = {
                "01-writings": 5,
                "02-conversations": 3,
                "03-expression-dna": 10,
                "04-external-views": 3,
                "05-decisions": 2,
                "06-timeline": 5
            }.get(stats.name, 5)

            checks.append(check_source_count(stats, min_sources))
            checks.append(check_primary_ratio(stats, 0.4))
            checks.append(check_confidence_labels(stats))
            checks.append(check_contradictions(stats))
            checks.append(check_gaps(stats))

            # Agent 2和Agent 5额外检查过程密度
            if stats.name in ["02-conversations", "05-decisions"]:
                checks.append(check_process_density(stats))

    # 计算总体评级
    total_checks = len(checks)
    passed_checks = sum(1 for c in checks if c.passed)
    pass_rate = passed_checks / total_checks if total_checks > 0 else 0

    # 检查关键Agent
    critical_agents = ["02-conversations", "05-decisions"]
    critical_failed = any(
        not c.passed for c in checks
        if any(agent in c.name for agent in critical_agents) and "文件存在" in c.name
    )

    # 确定总体评级
    if pass_rate >= 0.9 and not critical_failed:
        grade = "A"
    elif pass_rate >= 0.75 and not critical_failed:
        grade = "B"
    elif pass_rate >= 0.6:
        grade = "C"
    elif pass_rate >= 0.4:
        grade = "D"
    else:
        grade = "F"

    return checks, grade

def print_report(checks: List[QualityCheck], grade: str):
    """打印质量报告"""
    print("\n" + "="*70)
    print("  质量门禁报告")
    print("="*70)

    # 按Agent分组显示
    current_agent = ""
    for check in checks:
        agent_name = check.name.split()[0]
        if agent_name != current_agent:
            current_agent = agent_name
            print(f"\n### {agent_name}")

        status = "✅ PASS" if check.passed else "❌ FAIL"
        print(f"{status} | {check.name}")
        if not check.passed:
            print(f"      实际: {check.actual}")
            print(f"      期望: {check.expected}")
            if check.suggestion:
                print(f"      💡 建议: {check.suggestion}")

    # 总体评级
    print("\n" + "="*70)
    print(f"  总体评级: {grade}")
    print("="*70)

    passed = sum(1 for c in checks if c.passed)
    total = len(checks)
    print(f"\n通过: {passed}/{total} ({passed/total*100:.0f}%)")

    # 建议
    if grade in ["A", "B"]:
        print("\n✅ 质量可接受，可以进入Phase 2")
        if grade == "B":
            print("💡 建议: 可以考虑补充薄弱维度，但非必须")
    elif grade == "C":
        print("\n⚠️  质量勉强可接受，建议补充薄弱维度后再进入Phase 2")
        print("💡 重点改进:")
        failed = [c for c in checks if not c.passed]
        for check in failed[:3]:  # 最多显示3个
            print(f"   - {check.name}: {check.suggestion}")
    elif grade == "D":
        print("\n❌ 质量不足，需要补充采集后再进入Phase 2")
        print("💡 必须改进:")
        failed = [c for c in checks if not c.passed]
        for check in failed[:5]:
            print(f"   - {check.name}: {check.suggestion}")
    else:  # F
        print("\n❌ 严重不足，建议:")
        print("   1. 降低期望，改用'核心模式'（只蒸馏3个核心维度）")
        print("   2. 或者更换蒸馏对象（选择信息更充足的公众人物）")
        print("   3. 或者提供更多一手素材（书籍、访谈、决策记录）")

    print("\n" + "="*70)

def main():
    if len(sys.argv) < 2:
        print("用法: python3 quality_gate.py [skill目录]")
        print("示例: python3 quality_gate.py fupeng-perspective")
        sys.exit(2)

    skill_dir = Path(sys.argv[1])
    if not skill_dir.exists():
        print(f"错误: 目录不存在: {skill_dir}")
        sys.exit(2)

    checks, grade = run_quality_gate(skill_dir)
    print_report(checks, grade)

    # 根据评级决定退出码
    if grade in ["A", "B"]:
        sys.exit(0)
    elif grade == "C":
        sys.exit(0)  # 勉强通过
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()

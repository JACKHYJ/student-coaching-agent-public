import csv, os, re
from datetime import datetime

csv_path = "automation-input/student-risk-watchlist.example.csv"
report_path = "daily-student-risk-summary.md"
inspection_date = datetime.today()

field_names = ["student_code", "project", "course", "attendance_pct", "attendance_red_line", "latest_score", "pass_mark", "overdue_count", "last_follow_up", "notes"]

CODE_RE = re.compile(r'\b(?:[A-Z]{2,4}\d{3,4}[A-Z]?)\b')

def clean(val):
    return val.strip() if val is not None else ""

def to_float_safe(val):
    v = clean(val)
    if v == "":
        return None
    try:
        return float(v)
    except Exception:
        return None

def parse_date_safe(val):
    v = clean(val)
    if v == "":
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except Exception:
            pass
    return None

def parse_course_segments(course_val):
    """Split course field into display segments with optional extracted code."""
    v = clean(course_val)
    if v == "":
        return []
    raw_segments = [s.strip() for s in v.split(';') if s.strip() != ""]
    segments = []
    for seg in raw_segments:
        m = CODE_RE.search(seg)
        if m:
            code = m.group(0)
            display = seg
            segments.append((display, code))
        else:
            # stray title fragment -> merge into previous display
            if segments:
                prev_display, prev_code = segments[-1]
                segments[-1] = (prev_display + " " + seg, prev_code)
            else:
                segments.append((seg, None))
    return segments

def align_lists(segments, *vals):
    max_len = max(len(segments), max((len(v) for v in vals), default=0))
    segs = list(segments) + [("", None)] * (max_len - len(segments))
    aligned = []
    for i in range(max_len):
        entry = {"display": segs[i][0], "code": segs[i][1]}
        for key, lst in zip(["attendance_pct", "attendance_red_line", "latest_score", "pass_mark", "overdue_count"], vals):
            entry[key] = lst[i] if i < len(lst) else None
        aligned.append(entry)
    return aligned

records = []
with open(csv_path, newline='', encoding='utf-8') as f:
    reader = csv.reader(f)
    header = next(reader, None)
    for row in reader:
        if not any(field.strip() for field in row):
            continue
        if len(row) < 10:
            row = row + [""] * (10 - len(row))
        elif len(row) > 10:
            row = row[:9] + ["; ".join(row[9:])]
        d = dict(zip(field_names, row))
        sc = clean(d["student_code"])
        if sc == "":
            continue
        proj = clean(d["project"]) or "Monash"
        segments = parse_course_segments(d["course"])
        att_list = [to_float_safe(x) for x in clean(d["attendance_pct"]).replace(',', ';').split(';') if clean(x) != ""]
        red_list = [to_float_safe(x) for x in clean(d["attendance_red_line"]).replace(',', ';').split(';') if clean(x) != ""]
        latest_list = [to_float_safe(x) for x in clean(d["latest_score"]).replace(',', ';').split(';') if clean(x) != ""]
        pass_list = [to_float_safe(x) for x in clean(d["pass_mark"]).replace(',', ';').split(';') if clean(x) != ""]
        overdue_list = []
        for x in clean(d["overdue_count"]).replace(',', ';').split(';'):
            v = clean(x)
            if v == "":
                continue
            try:
                overdue_list.append(int(v))
            except Exception:
                overdue_list.append(None)
        aligned = align_lists(segments, att_list, red_list, latest_list, pass_list, overdue_list)
        last_follow_up = parse_date_safe(d["last_follow_up"])
        notes = clean(d["notes"])
        records.append({
            "student_code": sc,
            "project": proj,
            "aligned": aligned,
            "last_follow_up": last_follow_up,
            "notes": notes,
        })

LEVEL_HIGH = "高风险"
LEVEL_MEDIUM = "中风险"
LEVEL_LOW = "低风险"
LEVEL_UNKNOWN = "信息不足"

results = []
for rec in records:
    sc = rec["student_code"]
    proj = rec["project"]
    lfu = rec["last_follow_up"]
    notes = rec["notes"]
    course_risks = []
    overall_high = False
    overall_medium = False
    overall_unknown = False

    for item in rec["aligned"]:
        display = item["display"]
        if display == "":
            continue
        attendance = item["attendance_pct"]
        red_line = item["attendance_red_line"]
        latest = item["latest_score"]
        pass_mark = item["pass_mark"]
        overdue = item["overdue_count"]

        if attendance is None and red_line is None and latest is None and pass_mark is None and overdue is None:
            triggers = ["关键字段缺失"]
            risk = LEVEL_UNKNOWN
            course_risks.append({"course": display, "risk": risk, "triggers": triggers})
            overall_unknown = True
            continue

        triggers = []
        high = False
        medium = False

        if attendance is not None and red_line is not None and attendance < red_line:
            triggers.append(f"attendance_pct ({attendance*100:.2f}%) 低于 attendance_red_line ({red_line*100:.2f}%)")
            high = True
        if latest is not None and pass_mark is not None and latest < pass_mark:
            triggers.append(f"latest_score ({latest}) 低于 pass_mark ({pass_mark})")
            high = True
        if overdue is not None and int(overdue) >= 2:
            triggers.append(f"overdue_count ({int(overdue)}) ≥ 2")
            high = True

        if high:
            risk = LEVEL_HIGH
        else:
            if attendance is not None and red_line is not None:
                diff = (red_line - attendance) * 100
                if 0 <= diff <= 5:
                    triggers.append(f"attendance_pct ({attendance*100:.2f}%) 距 attendance_red_line ({red_line*100:.2f}%) 不超过 5 个百分点")
                    medium = True
            if latest is not None and pass_mark is not None:
                diff = pass_mark - latest
                if 0 <= diff <= 10:
                    triggers.append(f"latest_score ({latest}) 距 pass_mark ({pass_mark}) 不超过 10 分")
                    medium = True
            if overdue is not None and int(overdue) == 1:
                triggers.append(f"overdue_count ({int(overdue)}) = 1")
                medium = True
            if lfu is not None:
                delta = (inspection_date.date() - lfu).days
                if delta > 14:
                    triggers.append(f"last_follow_up ({lfu}) 距巡检日期 {inspection_date.date()} 超过 14 天（{delta} 天）")
                    medium = True
            risk = LEVEL_MEDIUM if medium else LEVEL_LOW

        if not triggers:
            triggers = ["已知指标均未触发"]
        course_risks.append({"course": display, "risk": risk, "triggers": triggers})
        if risk == LEVEL_HIGH:
            overall_high = True
        elif risk == LEVEL_MEDIUM:
            overall_medium = True
        elif risk == LEVEL_UNKNOWN:
            overall_unknown = True

    if overall_unknown and not overall_high and not overall_medium:
        overall = LEVEL_UNKNOWN
    elif overall_high:
        overall = LEVEL_HIGH
    elif overall_medium:
        overall = LEVEL_MEDIUM
    else:
        overall = LEVEL_LOW

    suggestions = []
    if overall == LEVEL_HIGH:
        suggestions.append("优先联系学生，核实科目学习支持需求并安排跟进。")
    elif overall == LEVEL_MEDIUM:
        suggestions.append("关注学习进展，必要时安排学业辅导或学习计划检查。")
    elif overall == LEVEL_UNKNOWN:
        suggestions.append("补充关键数据后重新评估。")
    else:
        suggestions.append("维持常规观察，无需额外操作。")
    if any("overdue_count" in t for item in course_risks for t in item["triggers"]):
        suggestions.append("核查 overdue_count 来源，确认是否存在未提交作业或记录错误。")

    results.append({
        "student_code": sc,
        "project": proj,
        "overall": overall,
        "course_risks": course_risks,
        "suggestions": suggestions,
        "last_follow_up": lfu,
        "notes": notes,
    })

order = {LEVEL_HIGH: 0, LEVEL_MEDIUM: 1, LEVEL_LOW: 2, LEVEL_UNKNOWN: 3}
results.sort(key=lambda x: (order.get(x["overall"], 9), x["student_code"]))

md_lines = []
md_lines.append("# 每日学生学业风险报告")
md_lines.append("")
md_lines.append(f"**巡检日期：** {inspection_date.date()}  ")
md_lines.append("**数据来源：** student-risk-watchlist.example.csv  ")
md_lines.append("**使用规则：** risk-rules.md  ")
md_lines.append("")
md_lines.append("---")
md_lines.append("")
md_lines.append("## 总体摘要")
md_lines.append("")
counts = {k: 0 for k in [LEVEL_HIGH, LEVEL_MEDIUM, LEVEL_LOW, LEVEL_UNKNOWN]}
for r in results:
    counts[r["overall"]] += 1
md_lines.append(f"- {LEVEL_HIGH}：{counts[LEVEL_HIGH]} 人")
md_lines.append(f"- {LEVEL_MEDIUM}：{counts[LEVEL_MEDIUM]} 人")
md_lines.append(f"- {LEVEL_LOW}：{counts[LEVEL_LOW]} 人")
md_lines.append(f"- {LEVEL_UNKNOWN}：{counts[LEVEL_UNKNOWN]} 人")
md_lines.append("")
md_lines.append("---")
md_lines.append("")

for r in results:
    md_lines.append(f"## {r['student_code']}")
    md_lines.append("")
    md_lines.append(f"- project：{r['project']}")
    md_lines.append(f"- 风险等级：**{r['overall']}**")
    if r["last_follow_up"]:
        md_lines.append(f"- last_follow_up：{r['last_follow_up']}")
    else:
        md_lines.append("- last_follow_up：未知")
    if r["notes"]:
        md_lines.append(f"- notes：{r['notes']}")
    md_lines.append("")
    md_lines.append("### 科目明细")
    md_lines.append("")
    for item in r["course_risks"]:
        md_lines.append(f"- **{item['course']}** —— {item['risk']}")
        for t in item["triggers"]:
            md_lines.append(f"  - {t}")
    md_lines.append("")
    md_lines.append("### 下一步跟进建议")
    md_lines.append("")
    for s in r["suggestions"]:
        md_lines.append(f"- {s}")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")

md_lines.append("## 说明")
md_lines.append("")
md_lines.append("- 本报告仅反映学业指标风险，不包含心理、人格或动机推断。")
md_lines.append("- 缺失字段以“未知”处理，未做补充推测。")
md_lines.append("- 本报告为内部学业风险提示，不构成最终管理决定。")
md_lines.append("")

os.makedirs(os.path.dirname(report_path), exist_ok=True)
with open(report_path, "w", encoding="utf-8") as f:
    f.write("\n".join(md_lines))

print(f"Wrote report to {report_path}")
print(f"Total students: {len(results)}")
print("Counts:", counts)
for r in results:
    if r["overall"] in (LEVEL_HIGH, LEVEL_MEDIUM, LEVEL_UNKNOWN):
        print(r["student_code"], r["overall"], r["course_risks"])

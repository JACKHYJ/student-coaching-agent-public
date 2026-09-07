# 学生学业风险巡检规则

## 使用限制

- 本规则仅生成内部学业风险提示，不作为最终管理决定。
- 只读取 `student-risk-watchlist.example.csv`（实际使用时请替换为本地脱敏文件）。
- 只能使用脱敏 student_code，不得包含真实姓名和真实学号。
- 缺失数据标记为“未知”，禁止推测。
- 禁止作出人格、动机或心理诊断。

## 高风险

满足任意一项：

- attendance_pct 低于 attendance_red_line；
- latest_score 低于 pass_mark；
- overdue_count 大于或等于 2。

## 中风险

未达到高风险，但满足任意一项：

- attendance_pct 距 attendance_red_line 不超过 5 个百分点；
- latest_score 距 pass_mark 不超过 10 分；
- overdue_count 等于 1；
- last_follow_up 距巡检日期超过 14 天。

## 低风险

所有已知指标均未触发高风险或中风险。

## 信息不足

关键字段缺失，无法可靠判断。

## 输出字段

- student_code
- project
- course
- 风险等级
- 触发风险的原始事实
- 下一步跟进建议

---
name: jd-scoring
description: 当 jd-analyzer agent 需要计算职缺匹配分数时自动加载。定义标准评分权重和分级规则。
---

# JD 匹配评分标准

## 权重定义
| 类型 | 权重 | 说明 |
|------|------|------|
| 必需技能命中 | 3 | JD 中写「required」「must have」「essential」的技能 |
| 加分技能命中 | 1 | JD 中写「nice to have」「preferred」「plus」的技能 |
| 职责关键词命中 | 0.5 | 经历描述中出现 JD core_responsibilities 的关键词 |

## 评分公式
raw = (必需命中 × 3) + (加分命中 × 1) + (职责命中 × 0.5)
max = (必需总数 × 3) + (加分总数 × 1)
match_score = round(raw / max * 100, 1)

## 分级与建议
| 分数 | 等级 | 建议 |
|------|------|------|
| ≥ 75 | 强匹配 | 优先处理，正常生成材料 |
| 50-74 | 中等匹配 | 生成材料，在 summary 中补充说明跨领域价值 |
| 30-49 | 弱匹配 | 生成材料，但在审核时提示用户注意 gap |
| < 30 | 不匹配 | 提示用户此职缺可能不适合，询问是否仍要生成 |

## 技能标准化规则
- `Python` = `python3` = `Python programming` → 统一为 `Python`
- `ML` = `Machine Learning` = `机器学习` → 统一为 `Machine Learning`
- 大小写不敏感匹配
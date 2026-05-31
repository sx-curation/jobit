# 专案进度摘要（人类可读）

**最后更新：2026-04-13 | Session #25**

---

## 总体状态

| Phase | 状态 | 说明 |
|-------|------|------|
| Phase 1：CV 解析 | 完成 | group-da + group-pdm 均已解析 |
| Phase 2：职缺搜索 | 完成 | 最新 batch 20260413_002（group-da 专项，past_week）|
| Phase 3A：JD 分析 | 完成（旧批次）+ 新批次完成 | 旧 30 个 + 新 9 个（group-da）|
| Phase 3B：CV 撰写 | 部分完成 | 3 个 cv_written（Bionorica/PUMA/Dahua），新职缺待启动 |
| Phase 3B：Cover Letter | 全部取消 | 用户 2026-04-12 决定取消 |
| Phase 3B.5：CV 评估 | 未开始 | |
| Phase 3C：审核 UI | 未开始 | |
| Phase 3D：主题选择 | 未开始 | |
| Phase 3E：PDF 生成 | 未开始 | |

---

## 新职缺分析结果（2026-04-13，group-da）

| # | 公司 | 职位 | 分数 | 状态 | 备注 |
|---|------|------|------|------|------|
| 32 | HelloFresh | Senior Data Analytics Project Manager | **82** | jd_done | 强匹配，推荐优先 |
| 33 | Kraken | Client Data & Analytics Associate | **78** | jd_done | client-facing analytics |
| 34 | Brandwatch (Cision) | Research Analyst - German speaking | **70** | jd_done | 德语流利度风险 |
| 35 | Agoda | Analyst/Senior Analyst, Pricing Marketing | **69** | jd_done | ⚠ Bangkok 驻扎 |
| — | GKL Marketing | Projektmitarbeiter Prozessoptimierung | 58 | 低分跳过 | 流程角色，非分析 |
| — | Evotec | Digital Marketing Specialist | 56 | 低分跳过 | 缺 HubSpot/GA4 |
| — | traide AI | Marketing Manager Performance | 37 | 低分跳过 | 缺核心工具 |
| — | Delivery Hero | Senior Pricing Analyst | 24 | 低分跳过 | 需 SQL/Python |

---

## 旧 Pending 职缺（仍待处理）

| # | 公司 | 职位 | Group | 分数 | 状态 |
|---|------|------|-------|------|------|
| 4 | Bionorica SE | Marketing Analyst / Sales Analyst | group-da | 72 | cv_written — 待 PDF/投递决策 |
| 28 | PUMA Group | Junior Manager Marketing Operations | group-pdm | 67 | cv_written — 待 PDF/投递决策 |
| 29 | Dahua Technology DACH | Marketing Specialist DACH Region | group-pdm | 72 | cv_written — 待 PDF/投递决策 |
| 31 | Intersnack Group | Senior Business Transformation Analyst | group-da | 68 | jd_done — 待 cv-writer |

---

## 技术修复记录

| 日期 | 问题 | 修复 |
|------|------|------|
| 2026-04-13 | refetch_details.py Windows GBK 编码 crash | `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` |
| 2026-04-13 | run_phase2_search.py 无 group 过滤 | 新建 `scripts/_run_group_search.py` 支持 `--group` 参数 |

---

## 下一步行动（优先顺序）

1. **用户决策**：HelloFresh(82)、Kraken(78) 是否立即生成 CV → `生成 CV 32/33`
2. **用户决策**：Agoda(69, Bangkok) 是否感兴趣
3. **旧 pending**：Bionorica(72)、PUMA(67)、Dahua(72) → 直接 PDF 还是跳过
4. **#31 Intersnack(68)** → 启动 cv-writer

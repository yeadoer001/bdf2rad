# Solution 3-1 全量审查（2026-09-21）

结论：转换尚未成功。旧程序只有 doctor/inspect 和 IR 容器，没有语义构建、RAD writer 或运行链。旧报告 PARSED 仅表示词法读取完成。

本次审查覆盖项目全部源模块、测试、入口、配置和已有阶段文档；对用户新增 124,829,087 字节 BDF 做全量流式解析及磁盘语义清点。

## 已修复和新增

- Simcenter TSTEP1* 的无标签 + / * 续行兼容。
- NASTRAN SYSTEM 和 ID 执行控制段保留，不再误判为 bulk card。
- ENDDATA 后带导出校验串的结束标记识别。
- 新增 review CLI、SQLite 网格清单、重复 ID 检测、节点/属性/材料悬空引用检查。
- 所有未转换 bulk 卡片保存至 preserved_cards.jsonl；节点存入 SQLite。
- 明确 INCOMPLETE 状态、禁用 Engine，输出不完整节点审查 RAD，避免假成功。
- 20 项 unittest 通过，包括此次真实输入触发的问题及失败保护。

## 输入清点

| 实体 | 数量 |
| --- | ---: |
| GRID | 551461 |
| CTETRA10 | 248363 |
| CHEXA20 | 7935 |
| CHEXA8 | 1204 |
| CPENTA15 | 139 |
| PSOLID / MAT1 | 各 12 |
| MATS1 | 5 |
| RBE2 / RBE3 | 51 / 14 |
| CONM2 | 14 |
| BGSET | 313 |
| BCTSET | 1 |
| BSURFS / BCRPARA | 各 420 |
| SPC | 1401 |
| TIC | 548571 |

输入为 SOL 402 非线性动力学，kg/mm/s/mN；不能按常见 tonne/mm/s/N 自动解释。初速度为 -4430 mm/s，重力为 -9810 mm/s²；同时出现不自动认定为重复施加，必须审查初始位置和物理时段。

全量引用检查：缺失节点、属性、材料引用均为 0。该检查不覆盖 RBE/接触/载荷选择引用，不等于所有引用均有效。

## 尚需逐项开发

1. 高阶实体的节点次序与 formulation：本地 hm_read_solid.F 明确存在 TETRA10/BRICK20 原生读取，不能依据旧假设一律降阶；CPENTA15 需单独制定并验证策略。
2. MAT1 + MATS1 联合弹塑性及热膨胀映射，禁止用线弹性替换塑性。
3. PSOLID、/PART 与单元 formulation 绑定及材料引用同步。
4. BSURFS 面拓扑、BCRPARA、BCTADD/BCTSET 和 BGADD/BGSET 活跃集合。胶接与滑动接触必须分别验证。
5. RBE2 DOF、RBE3 权重、CONM2 质量与惯量。
6. Case Control 继承和选择，SPC/TIC/GRAV/TEMPD 的坐标与激活规则。
7. SOL 402 时间积分向显式工况转换决策；TSTEP1 不可直接复制为显式稳定时间步。
8. 正式 Starter/Engine writer、进程运行器、输出解析、质量/质心/能量验证、回归基准。

每项仍为 UNSUPPORTED / REQUIRES_VALIDATION。此次未完成这些物理映射，也没有宣称已经逐一补齐。

## 输出及复现

运行：

```powershell
python bridge.py review "examples\Solution 3-1.bdf" --output "E:\openradioss\Solution_3_1_review_20260921"
python -m unittest discover -s tests -v
```

review 要求新的输出目录，拒绝覆盖已有数据库。
E:\openradioss\Solution_3_1_review_20260921 内含 conversion_report.json、model.sqlite、preserved_cards.jsonl 和 Solution_3_1_INCOMPLETE_nodes_0000.rad。

RAD 只含节点用于审查，不含已转换实体/材料/接触/载荷；未生成可执行 Engine 文件，未运行 Starter/Engine。不是用户要求的完整“改好的 RAD”。完整转换交付仍未完成。

## 已知软件缺口

review 目前单位与输出命名面向本案例，不是通用生产转换接口；编码需显式指定，默认 gb18030；解析异常的最终 JSON 持久化尚需完善；节点未保留原始原文（原 BDF 保留、SQLite 留有源行号）；尚未自动生成 capability matrix。早期 README/阶段报告描述的是上一阶段，当前事实以本报告与实测 JSON 为准。

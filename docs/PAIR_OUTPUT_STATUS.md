# 配对输出修改状态

## 已完成

- review 默认输入 E:\openradioss\input，默认输出 E:\openradioss\output。
- 文件名根据源 BDF 生成，不再固定绑定 Solution 3-1。
- 生成 0000 节点审查文件和 0001 Engine 控制草稿，/RUN 名称与 /BEGIN 和文件根名一致。
- 0001 包含候选终止时间、动画与历史输出间隔；不擅自加入质量缩放。
- 运行前识别缺少 /PART、/PROP、/MAT、单元和 Engine 文件；preflight 不等同 Starter 验证。
- 23 项 unittest 通过；未运行 Starter/Engine，未声称求解验证通过。

## 未完成

用户要求的完整计算模型仍未完成。Warning 1114 的根因是缺少实体、Part、属性和材料转换，新增检查只让问题提前明确失败，并没有修复物理模型。
0001 控制草稿不是完整计算模型；不得将其配合节点文件用于正式求解。
下一步仍需完整实现高阶实体、MAT1/MATS1、PSOLID、接触/胶接、RBE、集中质量、约束和载荷映射及 Starter 验证。

## 语法依据与局限

只读查看 OpenRadioss-main.zip 内 qa-tests/miniqa/ACCELEROMETRES/data/ACCELERO_0001.rad，参考 /RUN、/VERS、/ANIM/DT、/ANIM/VECT/VEL、/ANIM/ELEM/VONM、/TFILE/4 的组织。
本次没有完成官方文档/源码/Starter 三方验证，因此所有新增 Engine 控制仍为 REQUIRES_VALIDATION。
TSTEP1 单步时间只保留为候选，不表示 SOL402 与显式积分等价；多步需显式提供终止时间，不自动合并。

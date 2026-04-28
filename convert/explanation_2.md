将简化后的 `proscript_simple` 数据集（只保留 `scenario`、`events`、`gold_edges_for_prediction`）转化为一种新的 JSON 结构，其中包含了由**序列（sequence）**和**同步汇合（AND‑JOIN）**组成的事件图（`script_graph`）。核心流程如下：

1. **读取数据**
   加载 `proscript_simple/dev.json`，获取每个场景的无序步骤集合（`events`）和步骤间的有向边（`edges`）。
2. **构建有向图**
   根据 `edges` 建立邻接表，并计算每个节点的入度，用于后续的拓扑排序和 AND‑JOIN 检测。
3. **识别 AND‑JOIN 结构**
   - 寻找**分叉点**（出度 ≥ 2）和**汇合点**（入度 ≥ 2）。
   - 对每一对（分叉点 s，汇合点 t），检查从 s 的每个直接后继开始，按出度为 1 的路径走到 t 形成的分支，确保：
     - 各分支之间没有节点交叉；
     - t 的所有入边恰好来自每个分支的最后一个节点（或 s 本身，当某分支为空时）；
   - 满足条件就记录为一个 AND‑JOIN 结构（以 t 为键，保存 s 和各分支节点列表）。
4. **生成脚本图**
   - 通过拓扑排序遍历节点，遇到分叉点 s 时，将 s 加入主序列，随后插入一个 `and_join` 对象（包含各分支的有序列表），并标记分支内部节点为“已处理”。
   - 普通节点（含汇合点 t）按拓扑顺序依次加入主序列。
   - 最终将主序列包装为 `{"type": "sequence", "script": [...]}` 作为 `script_graph`。
5. **输出结果**
   生成包含 `id`, `scenario`, `unordered_nodes`, `edges`, `script_graph` 的新 JSON 文件 `converted_dev.json`。
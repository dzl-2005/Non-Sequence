在已经被初步修正的事件图数据集上，利用大语言模型进一步引入**选择和循环结构**，并对拼写错误、逻辑不合理的项进行修正或删除，最终输出一个更丰富、结构更完整的数据集（包含 `sequence`、`and_join`、`select`、`loop` 四种控制结构）以及对应的修改日志。

运行流程：

1. 分批读取输入文件 `llm_fixed_temp.json`；
2. 将每一批数据与一个非常详细的提示词模板一同发送给 LLM；
3. LLM 按要求返回两个 JSON 对象：`processed_data`（保留并修改后的所有条目）和 `change_log`（修改日志）；
4. 分批次更新断点文件 `checkpoint.json`，支持断点续传；
5. 最终保存 `processed_data.json` 和 `change_log.json`。
6. `check.py` 对 `processed_data.json` 进行结构和逻辑检查

## 统计每个数据的最大嵌套深度和各结构数

脚本文件：`count_structure.py`

运行指令：`python count_structure.py -i processed_data.json -o processed_data_with_stats.json`

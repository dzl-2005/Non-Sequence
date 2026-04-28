1. **删除无关字段**
   移除 `context`、`minutes`、`events_minutes`、`flatten_input_for_edge_prediction`、`flatten_input_for_script_generation`、`flatten_output_for_edge_prediction`、`flatten_output_for_script_generation` 等顶层字段，仅保留`scenario`,`events`,`gold_edges_for_prediction`
2. **清理 `events` 中的 “NONE” 条目**
   - 将 `events` 中值为 `"NONE"` 的步骤剔除
   - 对剩余步骤按原始序号重新编号（从 `0` 开始连续编号），生成新的 `events` 字典
   - 同时维护一个从旧序号到新序号的映射 `old_to_new`
3. **更新 `gold_edges_for_prediction` 中的边**
   - 遍历原有的边（格式为 `"source->target"`）
   - 如果源节点或目标节点是已被剔除的 “NONE” 步骤，则整条边被丢弃
   - 否则，利用 `old_to_new` 将源和目标序号映射为新的连续编号，生成新的边列

1. 加载提示词模板 (prompt_template.txt)
2. 加载“正确答案”数据集 (processed_data.json)
3. 尝试从检查点恢复 progress
4. 遍历数据集中的每一项：
   - 提取 id, scenario, unordered_nodes
   - 调用大模型生成 edges + script_graph
   - 将生成结果与参考答案对比
   - 记录评估指标
   - 保存检查点
   - 输出完整的评估报告 (evaluation_results.json)
5. 软指标说明：
   新增查准率P，查全率R，F1分数，IoU指标，图编辑距离GED（增加、删减边的代价记为1）

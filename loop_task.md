### 一、总体思路与任务

1. 针对循环结构构建判别式任务：根据描述判断事件是否会继续循环
2. 从 `proscript` 数据集中选取合适数据，加以改造



### 二、数据集

1. 示例

   ```json
   {
       "id":1,
       "sceniro": "charge the phone to full battery",
       "steps": [
           "find the charger and cable",
           "plug the charger into the power outlet",
           "connect the cable to the phone's charging port",
           "wait for the battery to reach 100%"
       ],
       "loop_idx": 3,
       "loop_step": "wait for the battery to reach 100%",
       "descriptions": [
           [
               "battery is at 85%",
               1,
               "easy"
           ],
           [
               "the phone is brand new out of the box",
               2,
               "na"
           ],
           [
               "battery shows 100% on the lock screen",
               0,
               "easy"
           ],
           [
               "the phone displays 'Charging paused: Temperature too high'",
               0,
               "medium"
           ],
           [
               "the phone displays 'optimized battery charging'" ,
               0,
               "hard"
           ]
       ]
   }
   ```

2. 具体字段说明

   - `id`：数据编号/序号
   - `sceniro`：事件链目标
   - `steps`：具体步骤
   - `loop_idx` 和 `loop_step` ：`steps` 中循环步骤的编号和具体内容
   - `descriptions`：包含三个字段：
     - 问题（状态描述）：对事物或事件的具体描述，用于判断事件 `loop_step` 是否会继续循环
     - 答案：$0$ 表示退出循环，$1$ 表示继续循环，$2$ 表示状态描述与循环判断无关
     - 难度：`easy`, `medium`, `hard`, `na`，其中 `na` 用于标注状态描述与循环判断无关的问题

3. 构建提示词

   - **困难等级**：原来使用 "推理步数" 作为难度评级的准则，但是**逻辑链越长并不代表推理越困难，过于单一**。因此我们需要**额外**考虑其他量化标准，目前除了使用**人工标准的一致性**，暂无想到其他更好方法

   - 用于提示生成 `continue/stop` 状态描述的提示词：

     ```txt
     Prompt 1:
     The scenario is "{scenario}". 
     One of the steps towards that is:{steps}.
     Step {loop_idx} "{loop_step}" involves a loop.
     Because {please insert: one}，the loop needs to **continue/stop**.
     
     Prompt 2:
     The scenario is "{scenario}".
     One of the steps towards that is:{steps}.
     Step {loop_idx} "{loop_step}" involves a loop.
     Here is one reason the loop should **continue/stop**: {please insert: one}.
     Now give a different, more underlying reason that is less immediately visible than the one above, but still directly implies the loop should **continue/stop**. This new reason is: {please insert: two}.
     
     Prompt 3:
     The scenario is "{goal}". 
     One of the steps towards that is:{steps}
     Step {loop_idx} "{loop_step}" involves a loop.
     Here is one reason the loop should **continue/stop**: {please insert: one}.
     Here is a less immediately visible reason: {please insert: two}.
     Now give a third, even more underlying reason that is even less directly observable, but still in itself a sufficient reason to conclude that the loop should **continue/stop**: {please insert: three}.
     
     Requirement: 
     - Each of {please insert: k} must standalone be a complete, sufficient reason to conclude that the loop should **continue/stop**. No single reason should require reading the others to make sense.
     - Each {please insert: k} must describe a state, not an argument for why the loop should stop.
     
     Please give {please insert: one}, {please insert: two} and {please insert: three}.
     ```

     显然，根据**跳数**，可以规定 `Prompt 1`，`Prompt 2`，`Prompt 3` 导出的问题难度分别为 `easy`，`medium`，`hard`

   - 用于提示生成**无关**状态描述的提示词：

     ```txt
     Prompt:
     The scenario is "{scenario}". 
     One of the steps towards that is:{steps}.
     Now give a piece of contextual information that is related to the general scenario but has no causal bearing on whether the loop should continue or stop. The information should sound natural in the situation but should not help anyone decide the loop's state. This piece of information is: {please insert: na}.
     
     Requirement: 
     - The information must be plausibly related to the scenario.
     - It must NOT contain any information from which the loop's state could be logically deduced, even by implication.
     - Information that is completely unrelated should be avoided as much as possible.The information should feel like a natural detail in the scene, not a random fact.
     - It must describe a state, not an explanation of why it has no effect on loop inference.
     
     Please give {please insert: na}.
     ```

   - 示例：

     ```txt
     Prompt 1:
     The scenario is "charge the phone to full battery". One of the steps towards that is :
     [
             "find the charger and cable",
             "plug the charger into the power outlet",
             "connect the cable to the phone's charging port",
             "wait for the battery to reach 100%" 
     ]
     Step 3 "wait for the battery to reach 100%" involves a loop.
     Because {please insert: one}，the loop needs to stop.
     
     Prompt 2:
     The scenario is "charge the phone to full battery". One of the steps towards that is :
     [
             "find the charger and cable",
             "plug the charger into the power outlet",
             "connect the cable to the phone's charging port",
             "wait for the battery to reach 100%" 
     ]
     Step 3 "wait for the battery to reach 100%" involves a loop.
     Here is one reason the loop should stop: {please insert: one}.
     Now give a different, more underlying reason that is less immediately visible than the one above, but still directly implies the loop should stop. This new reason is: {please insert: two}.
     
     Prompt 3:
     The scenario is "charge the phone to full battery". One of the steps towards that is :
     [
             "find the charger and cable",
             "plug the charger into the power outlet",
             "connect the cable to the phone's charging port",
             "wait for the battery to reach 100%" 
     ]
     Step 3 "wait for the battery to reach 100%" involves a loop.
     Here is one reason the loop should stop: {please insert: one}.
     Here is a less immediately visible reason: {please insert: two}.
     Now give a third, even more underlying reason that is even less directly observable, but still in itself a sufficient reason to stop the loop: {please insert: three}.
     
     Requirement: 
     - Each of {please insert: k} must standalone be a complete, sufficient reason to conclude that the loop should stop. No single reason should require reading the others to make sense.
     - Each {please insert: k} must describe a state, not an argument for why the loop should stop.
     
     Please give {please insert: one}, {please insert: two} and {please insert: three}.
     ```

4. 引入噪声

   - 在利用提示词引导出 `easy`，`medium`，`hard`，`na` 各种状态描述后，在其基础上添加噪声，难度继承，以测试模型的抗噪能力

   - 核心要求：

     - 改写后的状态描述必须与原描述得出完全相同的循环判定
     - 难度直接继承，即输出时保留原难度，不做调整
     - 噪声必须与 `sceniro`、`loop_step` 以及原状态描述相关，但添加的文本对循环判定无因果影响

   - 提示词：

     ```txt
     Your task is to augment the existing data by adding reasonable noise to each state description (the first field in `descriptions`).
     
     ## Data Template
     {
       "id": number,
       "sceniro": "scenario description",
       "steps": ["step 1", "step 2", ...],
       "loop_idx": index of the loop step (note: indexing may start from 0),
       "loop_step": "content of the loop step",
       "descriptions": [
         ["state description text", answer (0/1/2), difficulty ("easy"/"medium"/"hard"/"na")],
         ...
       ]
     }
     
     ## Field Explanation
     - Answer: 0 = exit loop, 1 = continue loop, 2 = irrelevant to loop decision
     - Difficulty: easy, medium, hard, na (na is used only when answer = 2)
     
     ## Noise Addition Requirements
     1. **Answer unchanged**: The rewritten state description must lead to exactly the same loop decision (0/1/2) as the original.
     2. **Difficulty directly inherited**: Keep the original difficulty level; do not adjust it.
     3. **Source of noise**: The added text must be related to `sceniro`, `loop_step`, and the original state description, but must have no causal impact on the loop decision. You may add background details, environmental information, user states, temporal modifiers, or other distracting but non-causal content.
     4. **Semantic proximity**: Preserve the core facts that determine whether the loop should continue/stop or are irrelevant. For answer=2 (irrelevant) descriptions, keep the original meaning as much as possible.
     
     
     ## Examples of Allowed Noise (using the "charge to 100%" scenario)
     - Original: `["battery is at 85%", 1, "easy"]`
       Allowed noise: `["according to the phone, the battery level is showing 85% and the room temperature is normal", 1, "easy"]` 
     - Original: `["battery shows 100% on the lock screen", 0, "easy"]`
       Allowed noise: `["the lock screen displays a full battery icon of 100% and it's early morning", 0, "easy"]` 
     - Original: `["the phone displays 'optimized battery charging'", 0, "hard"]`
       Allowed noise: `["the phone indicates 'optimized battery charging' is active with a small leaf icon", 0, "hard"]` 
     
     ## Output Format
     Directly output the complete JSON text with the same structure as the input. Only modify the first field of each `descriptions` entry (the state description text); keep the answer and difficulty unchanged.
     
     Input data:
     {paste the specific JSON data to be augmented here}
     ```



### 三、思路


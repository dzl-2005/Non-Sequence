"""
隐藏答案评估脚本
读取 descriptions_dev.json，使用大模型对每个描述进行 0/1/2 判断，
与标准答案对比，输出准确率统计。
"""
import json
import os
import time
from collections import defaultdict
from openai import OpenAI

# ========== 配置 ==========
INPUT_FILE = "../descriptions_dev.json"
PROMPT_FILE = "prompt_judge.txt"
MODEL_NAME = "deepseek-v4-flash"

API_KEY_ENV = "DEEPSEEK_API_KEY"
MAX_RETRIES = 3
RETRY_DELAY = 3  # 秒
SLEEP_BETWEEN_ITEMS = 1  # 每条数据间休息秒数

# ========== 初始化 ==========
api_key = os.environ.get(API_KEY_ENV)
if not api_key:
    raise RuntimeError(f"未找到环境变量 {API_KEY_ENV}")

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# 加载提示词
with open(PROMPT_FILE, "r", encoding="utf-8") as f:
    eval_prompt_template = f.read()

# 加载数据
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)


# ========== 工具函数 ==========
def call_api(messages):
    """调用 DeepSeek API，返回文本响应"""
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                stream=False,
                extra_body={"thinking": {"type": "enabled"}}
            )
            content = response.choices[0].message.content.strip()
            if content:
                return content
            else:
                print(f"  API 返回空内容，重试 {attempt + 1}/{MAX_RETRIES}")
                time.sleep(RETRY_DELAY)
        except Exception as e:
            print(f"  API 调用异常：{e}，重试 {attempt + 1}/{MAX_RETRIES}")
            time.sleep(RETRY_DELAY)
    return None


def parse_prediction(raw):
    """从模型输出中提取数字 0/1/2"""
    raw = raw.strip()
    # 尝试直接转为整数
    try:
        val = int(raw)
        if val in (0, 1, 2):
            return val
    except:
        pass
    # 尝试从内容中匹配第一个 0/1/2
    import re
    match = re.search(r'\b([012])\b', raw)
    if match:
        return int(match.group(1))
    return None


# ========== 评估主流程 ==========
all_results = []  # 存储每个预测的详细信息
stats = defaultdict(lambda: defaultdict(int))  # 统计准确率

total_items = len(data)
correct_count = 0
total_count = 0

print(f"开始评估 {total_items} 条数据...")

for idx, item in enumerate(data, 1):
    scenario = item["scenario"]
    steps = item["steps"]
    loop_idx = item["loop_idx"]
    loop_step = item["loop_step"]
    descriptions = item["descriptions"]

    # 构建步骤文本
    steps_text = json.dumps(steps, ensure_ascii=False)

    print(f"\n处理 {idx}/{total_items}: {scenario} (loop: {loop_step})")

    for desc_idx, desc_entry in enumerate(descriptions):
        desc_text = desc_entry[0]
        true_answer = desc_entry[1]
        difficulty = desc_entry[2]

        # 构建用户消息
        user_prompt = f"Scenario: \"{scenario}\"\n" \
                      f"Steps: {steps_text}\n" \
                      f"Loop step index: {loop_idx}, loop step content: \"{loop_step}\"\n" \
                      f"Description: \"{desc_text}\""

        # 构建完整消息
        messages = [
            {"role": "system", "content": eval_prompt_template},
            {"role": "user", "content": user_prompt}
        ]

        # 调用 API
        response = call_api(messages)
        if response is None:
            print(f"  描述 {desc_idx + 1}/{len(descriptions)}: API 失败，跳过")
            continue

        pred = parse_prediction(response)
        if pred is None:
            print(f"  描述 {desc_idx + 1}: 无法解析预测值，原始输出：{response[:50]}...")
            continue

        is_correct = (pred == true_answer)
        if is_correct:
            correct_count += 1
        total_count += 1

        # 记录详细信息
        all_results.append({
            "item_id": item["id"],
            "scenario": scenario,
            "desc_idx": desc_idx,
            "description": desc_text,
            "true_answer": true_answer,
            "predicted": pred,
            "difficulty": difficulty,
            "correct": is_correct
        })

        # 统计
        stats["overall"]["total"] += 1
        if is_correct:
            stats["overall"]["correct"] += 1

        # 按答案类别统计
        answer_key = f"answer_{true_answer}"
        stats[answer_key]["total"] += 1
        if is_correct:
            stats[answer_key]["correct"] += 1

        # 按难度统计
        diff_key = f"difficulty_{difficulty}" if difficulty != "na" else "difficulty_na"
        stats[diff_key]["total"] += 1
        if is_correct:
            stats[diff_key]["correct"] += 1

        # 联合统计：答案+难度
        joint_key = f"{answer_key}_{difficulty}"
        stats[joint_key]["total"] += 1
        if is_correct:
            stats[joint_key]["correct"] += 1

        print(f"  描述 {desc_idx + 1} [{difficulty}] 真实: {true_answer}, "
              f"预测: {pred} {'✓' if is_correct else '✗'}")

    # 休息一下
    if idx < total_items:
        time.sleep(SLEEP_BETWEEN_ITEMS)

# ========== 输出评估报告 ==========
print("\n" + "=" * 60)
print("评估报告")
print("=" * 60)


def print_stat(name, stat):
    correct = stat.get("correct", 0)
    total = stat.get("total", 0)
    acc = correct / total * 100 if total > 0 else 0
    print(f"{name:30s} : {correct:3d}/{total:3d} = {acc:6.2f}%")


print_stat("Overall", stats["overall"])
print("-" * 40)
for ans in [0, 1, 2]:
    key = f"answer_{ans}"
    if key in stats:
        print_stat(f"  Answer = {ans}", stats[key])
print("-" * 40)
for diff in ["easy", "medium", "hard", "na"]:
    key = f"difficulty_{diff}"
    if key in stats:
        print_stat(f"  Difficulty = {diff}", stats[key])
print("-" * 40)
# 联合统计（答案×难度）
for ans in [0, 1, 2]:
    for diff in ["easy", "medium", "hard", "na"]:
        joint_key = f"answer_{ans}_{diff}"
        if joint_key in stats and stats[joint_key]["total"] > 0:
            print_stat(f"    Ans={ans}, Diff={diff}", stats[joint_key])

# 保存详细结果
with open("evaluation_details.json", "w", encoding="utf-8") as f:
    json.dump(all_results, f, indent=2, ensure_ascii=False)

print(f"\n详细评估结果已保存至 evaluation_details.json")
print(
    f"总预测数: {total_count}, 正确数: {correct_count}, 总体准确率: {correct_count / total_count * 100:.2f}%" if total_count > 0 else "")
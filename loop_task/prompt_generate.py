import json
import os
import time
from openai import OpenAI

# ========== 配置 ==========
INPUT_FILE = "filter_loop_dev.json"
OUTPUT_FILE = "descriptions_dev.json"
MODEL = "deepseek-v4-flash"

# 提示词模板文件
PROMPT_CONTINUE_FILE = "prompt_continue.txt"
PROMPT_STOP_FILE = "prompt_stop.txt"
PROMPT_NA_FILE = "prompt_na.txt"

# API 设置
MAX_RETRIES = 3
RETRY_DELAY = 3  # 秒

# ========== 初始化 ==========
api_key = os.environ.get("DEEPSEEK_API_KEY")
if not api_key:
    raise RuntimeError("未找到环境变量 DEEPSEEK_API_KEY")

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


# 加载提示词模板
def load_prompt(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


prompt_continue_tpl = load_prompt(PROMPT_CONTINUE_FILE)
prompt_stop_tpl = load_prompt(PROMPT_STOP_FILE)
prompt_na_tpl = load_prompt(PROMPT_NA_FILE)

# 加载数据
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)


# ========== 工具函数 ==========
def call_api(prompt_text):
    """调用 DeepSeek API，返回模型文本响应"""
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt_text}
                ],
                stream=False,
                # 对于生成任务，我们使用默认推理，不强制开启思考模式
                extra_body={"thinking": {"type": "enabled"}}
            )
            content = response.choices[0].message.content.strip()
            if not content:
                print(f"  API 返回空内容，重试 {attempt + 1}/{MAX_RETRIES}")
                time.sleep(RETRY_DELAY)
                continue
            return content
        except Exception as e:
            print(f"  API 调用异常：{e}，重试 {attempt + 1}/{MAX_RETRIES}")
            time.sleep(RETRY_DELAY)
    return None


def parse_json_array(raw):
    """从模型响应中解析 JSON 数组，做基本的清洗"""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        raw = "\n".join(lines).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 尝试提取第一个 JSON 数组
        import re
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        return None


# ========== 主流程 ==========
results = []
total = len(data)

print(f"开始为 {total} 条数据生成 descriptions...")

for idx, item in enumerate(data, 1):
    print(f"处理 {idx}/{total}: {item['scenario']} (loop: {item['loop_step']})")

    # 准备变量
    scenario = item["scenario"]
    steps = json.dumps(item["steps"], ensure_ascii=False)
    loop_idx = item["loop_idx"]
    loop_step = item["loop_step"]

    descriptions = []
    success = True

    # ---------- 生成 continue (答案=1) ----------
    prompt_cont = prompt_continue_tpl.format(
        scenario=scenario,
        steps=steps,
        loop_idx=loop_idx,
        loop_step=loop_step
    )
    resp_cont = call_api(prompt_cont)
    if resp_cont:
        arr = parse_json_array(resp_cont)
        if isinstance(arr, list) and len(arr) == 3:
            difficulties = ["easy", "medium", "hard"]
            for desc, diff in zip(arr, difficulties):
                descriptions.append([desc, 1, diff])
            print(f"  continue: √")
        else:
            print(f"  continue 解析失败或数量不对，收到：{resp_cont[:100]}")
            success = False
    else:
        print(f"  continue 调用失败")
        success = False

    # ---------- 生成 stop (答案=0) ----------
    prompt_stop = prompt_stop_tpl.format(
        scenario=scenario,
        steps=steps,
        loop_idx=loop_idx,
        loop_step=loop_step
    )
    resp_stop = call_api(prompt_stop)
    if resp_stop:
        arr = parse_json_array(resp_stop)
        if isinstance(arr, list) and len(arr) == 3:
            difficulties = ["easy", "medium", "hard"]
            for desc, diff in zip(arr, difficulties):
                descriptions.append([desc, 0, diff])
            print(f"  stop: √")
        else:
            print(f"  stop 解析失败或数量不对，收到：{resp_stop[:100]}")
            success = False
    else:
        print(f"  stop 调用失败")
        success = False

    # ---------- 生成 na (答案=2) ----------
    prompt_na = prompt_na_tpl.format(
        scenario=scenario,
        steps=steps
    )
    resp_na = call_api(prompt_na)
    if resp_na:
        arr = parse_json_array(resp_na)
        if isinstance(arr, list) and len(arr) >= 2:  # 我们要求至少2条
            for desc in arr[:2]:  # 只取前两个
                descriptions.append([desc, 2, "na"])
            print(f"  na: √")
        else:
            print(f"  na 解析失败或数量不够，收到：{resp_na[:100]}")
            success = False
    else:
        print(f"  na 调用失败")
        success = False

    # 组装结果
    if success:
        final_entry = {
            "id": item["id"],  # 暂时保留原id，稍后统一重排
            "scenario": item["scenario"],
            "steps": item["steps"],
            "loop_idx": item["loop_idx"],
            "loop_step": item["loop_step"],
            "descriptions": descriptions
        }
        results.append(final_entry)
        print(f"  -> 成功生成 {len(descriptions)} 条描述")
    else:
        print(f"  -> 由于部分失败，该条数据被跳过")
    time.sleep(1)  # 礼貌间隔

# ========== 重新编号 id ==========
for new_id, entry in enumerate(results, start=1):
    entry["id"] = new_id

# ========== 保存 ==========
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\n完成！成功处理 {len(results)}/{total} 条，输出至 {OUTPUT_FILE}")
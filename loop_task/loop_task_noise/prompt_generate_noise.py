"""
噪声注入脚本
读取 descriptions_dev.json，调用大模型为每个状态描述添加噪声，
输出 descriptions_noisy.json
"""
import json
import os
import time
from openai import OpenAI

# ========== 配置 ==========
INPUT_FILE = "../descriptions_dev.json"
OUTPUT_FILE = "descriptions_dev_noise.json"
PROMPT_FILE = "prompt_noise.txt"
MODEL_NAME = "deepseek-v4-flash"

API_KEY_ENV = "DEEPSEEK_API_KEY"
MAX_RETRIES = 3
RETRY_DELAY = 5  # 秒

# ========== 初始化 ==========
api_key = os.environ.get(API_KEY_ENV)
if not api_key:
    raise RuntimeError(f"未找到环境变量 {API_KEY_ENV}")

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# 加载提示词模板
with open(PROMPT_FILE, "r", encoding="utf-8") as f:
    prompt_template = f.read()

# 加载原始数据
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    original_data = json.load(f)

# ========== 构建完整提示词 ==========
input_json_str = json.dumps(original_data, indent=2, ensure_ascii=False)
full_prompt = prompt_template + "\n" + input_json_str


# ========== 调用 API ==========
def call_api_with_retry(messages):
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                stream=False,
                extra_body={"thinking": {"type": "enabled"}}
            )
            content = response.choices[0].message.content.strip()
            if not content:
                print(f"  空响应，重试 {attempt + 1}/{MAX_RETRIES}")
                time.sleep(RETRY_DELAY)
                continue
            return content
        except Exception as e:
            print(f"  API 调用异常：{e}，重试 {attempt + 1}/{MAX_RETRIES}")
            time.sleep(RETRY_DELAY)
    return None


print("正在调用大模型为所有描述添加噪声...")
messages = [
    {"role": "system", "content": "You are a helpful data augmentation assistant."},
    {"role": "user", "content": full_prompt}
]

raw_output = call_api_with_retry(messages)

if raw_output is None:
    print("错误：多次重试后仍无法获取有效响应，脚本终止。")
    exit(1)

# ========== 解析输出 ==========
# 清洗可能的 markdown 代码块标记
cleaned = raw_output.strip()
if cleaned.startswith("```"):
    lines = cleaned.split("\n")
    # 去掉第一行和最后一行 ```
    if lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    cleaned = "\n".join(lines).strip()

try:
    noisy_data = json.loads(cleaned)
except json.JSONDecodeError as e:
    print(f"JSON 解析失败：{e}")
    print("原始返回内容前500字符：")
    print(raw_output[:500])
    exit(1)

# ========== 简单验证 ==========
if len(noisy_data) != len(original_data):
    print(f"警告：输出数据条数 ({len(noisy_data)}) 与输入 ({len(original_data)}) 不一致，可能存在丢失。")

print(f"成功生成 {len(noisy_data)} 条带噪声数据")

# 检查每条数据的 descriptions 数量是否匹配
mismatch_count = 0
for i, (orig, noisy) in enumerate(zip(original_data, noisy_data)):
    if len(orig["descriptions"]) != len(noisy["descriptions"]):
        print(
            f"  条目 {noisy.get('id', '?')} 描述数量不匹配：原 {len(orig['descriptions'])}，现 {len(noisy['descriptions'])}")
        mismatch_count += 1
if mismatch_count:
    print(f"共有 {mismatch_count} 条数据的描述数量不匹配，请检查。")

# ========== 保存结果 ==========
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(noisy_data, f, indent=2, ensure_ascii=False)

print(f"噪声注入完成，输出文件：{OUTPUT_FILE}")
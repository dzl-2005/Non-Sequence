import json

# 定义目标 ID 集合（自动去重，例如 E 组重复的 425 只保留一次）
target_ids = {
    # A 组
    6, 8, 22, 23, 26, 28, 34, 63, 73, 90, 96, 104,
    153, 163, 186, 192, 200, 213, 234, 242,
    # B 组
    121, 182, 232, 290, 355, 500, 587, 686, 709, 723,
    756, 767, 791, 835, 899, 920, 940, 990, 999, 1048,
    # C 组
    3, 4, 135, 202, 222, 400, 420, 540, 711, 903,
    916, 919, 922, 970, 985, 993, 1004, 1064, 1079, 1080,
    # D 组
    189, 255, 266, 335, 506, 698, 706, 708, 710, 733,
    751, 770, 810, 850, 941, 1034, 18, 68, 102, 437,
    # E 组
    48, 299, 636, 659, 825, 957, 80, 414, 748, 537,
    1012, 17, 336, 425, 463, 475, 482, 977, 317,476
}

# 1. 读取原始 JSON
with open('processed_data_check_with_stats.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 确保数据是列表（如果整个文件是单个对象，可能需要根据实际情况调整）
if not isinstance(data, list):
    raise ValueError("JSON 文件的顶层结构应为数组")

# 2. 筛选并只保留五个字段
extracted = []
for item in data:
    if item.get('id') in target_ids:
        extracted.append({
            "id": item["id"],
            "scenario": item.get("scenario", ""),
            "unordered_nodes": item.get("unordered_nodes", {}),
            "edges": item.get("edges", []),
            "script_graph": item.get("script_graph", {})
        })

# 3. 按 id 升序排序
extracted.sort(key=lambda x: x["id"])

# 4. 写入新文件
with open('gold.json', 'w', encoding='utf-8') as f:
    json.dump(extracted, f, indent=4, ensure_ascii=False)

print(f"提取完成，共 {len(extracted)} 个脚本，已保存至 extracted_scripts.json")
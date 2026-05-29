import json
import os
import time
from openai import OpenAI
from collections import defaultdict

MODEL = "deepseek-v4-pro"
BASE_URL = "https://api.deepseek.com"
API_KEY = os.getenv("DEEPSEEK_API_KEY")
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

CHECKPOINT_FILE = "eval_checkpoint.json"
OUTPUT_FILE = "results_v4-pro.json"

# ---------- 辅助函数 ----------
def load_prompt_template(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

def build_user_message(item):
    inp = {
        "id": item["id"],
        "scenario": item["scenario"],
        "unordered_nodes": item["unordered_nodes"]
    }
    return json.dumps(inp, ensure_ascii=False, indent=2)

def call_model(system_prompt, user_message):
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}},
        stream=False
    )
    return response.choices[0].message.content

def extract_json(text):
    if "```json" in text:
        json_str = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        json_str = text.split("```")[1].split("```")[0].strip()
    else:
        json_str = text.strip()
    return json.loads(json_str)

def normalize_graph(edges, script_graph):
    normalized_edges = sorted(set(edges))
    sg_str = json.dumps(script_graph, sort_keys=True, ensure_ascii=False)
    return normalized_edges, sg_str

def compare_graphs(gen_edges, gen_sg, ref_edges, ref_sg):
    gen_e, gen_s = normalize_graph(gen_edges, gen_sg)
    ref_e, ref_s = normalize_graph(ref_edges, ref_sg)
    edges_match = gen_e == ref_e
    sg_match = gen_s == ref_s
    return edges_match, sg_match

def evaluate_item(item, template, reference_graphs):
    rid = item["id"]
    nodes = item["unordered_nodes"]
    user_msg = build_user_message(item)
    raw = call_model(template, user_msg)
    try:
        gen = extract_json(raw)
    except Exception as e:
        return {"id": rid, "error": f"JSON parse error: {e}", "raw": raw}

    if "edges" not in gen or "script_graph" not in gen:
        return {"id": rid, "error": "Missing edges or script_graph", "raw": raw}

    ref_edges = reference_graphs[rid]["edges"]
    ref_sg = reference_graphs[rid]["script_graph"]
    edges_match, sg_match = compare_graphs(gen["edges"], gen["script_graph"], ref_edges, ref_sg)

    # 节点使用一致性检查
    node_ids = set(nodes.keys())
    used_ids = set()
    def collect_nodes(struct):
        if isinstance(struct, str):
            if struct != "continue":
                used_ids.add(struct)
        elif isinstance(struct, dict):
            if "script" in struct:
                for elem in struct["script"]:
                    collect_nodes(elem)
            elif "options" in struct:
                for opt in struct["options"]:
                    collect_nodes(opt)
            elif "entry" in struct:
                used_ids.add(struct["entry"])
                if "retry" in struct:
                    for elem in struct["retry"]:
                        collect_nodes(elem)
                used_ids.add(struct["exit"])
            elif "branches_set" in struct:
                for branch in struct["branches_set"].values():
                    for elem in branch:
                        collect_nodes(elem)
    collect_nodes(gen["script_graph"])
    nodes_valid = (used_ids == node_ids)

    return {
        "id": rid,
        "edges_match": edges_match,
        "sg_match": sg_match,
        "nodes_valid": nodes_valid,
        "generated_edges": gen["edges"],
        "generated_sg": gen["script_graph"],
        # 以下仅用于内部评估，不写入最终输出
        "reference_edges": ref_edges,
        "reference_sg": ref_sg
    }

def save_checkpoint(merged_records):
    """保存已处理的合并记录到检查点文件"""
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(merged_records, f, ensure_ascii=False, indent=2)

def load_checkpoint():
    """如果检查点文件存在则加载已合并的记录列表，否则返回空列表"""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# ---------- 指标计算 ----------
def compute_statistics(merged_records, reference_stats):
    """从合并记录中计算并打印各种正确率指标"""
    print("=" * 60)
    total = len(merged_records)
    if total == 0:
        print("没有数据可供统计。")
        return

    total_edges_ok = sum(1 for r in merged_records if r.get("edges_match"))
    total_sg_ok = sum(1 for r in merged_records if r.get("sg_match"))
    total_both_ok = sum(1 for r in merged_records if r.get("edges_match") and r.get("sg_match"))

    def safe_div(num, den):
        return f"{num}/{den}" if den > 0 else "0/0"

    def percent(num, den):
        return f"{num/den*100:.1f}%" if den > 0 else "N/A"

    print("1. 总体正确率")
    print(f"   Edges: {percent(total_edges_ok, total)} ({safe_div(total_edges_ok, total)})")
    print(f"   SG:    {percent(total_sg_ok, total)} ({safe_div(total_sg_ok, total)})")
    print(f"   Both:  {percent(total_both_ok, total)} ({safe_div(total_both_ok, total)})")

    # 2. 按深度分组
    depth_groups = defaultdict(list)
    for r in merged_records:
        rid = r["id"]
        stats = reference_stats.get(rid, {})
        depth = stats.get("max_depth", 0)
        if depth >= 3:
            depth = 3
        depth_groups[depth].append(r)
    print("\n2. 各最大嵌套深度正确率")
    for depth in sorted(depth_groups.keys()):
        recs = depth_groups[depth]
        n = len(recs)
        e_ok = sum(1 for r in recs if r["edges_match"])
        s_ok = sum(1 for r in recs if r["sg_match"])
        b_ok = sum(1 for r in recs if r["edges_match"] and r["sg_match"])
        label = f"深度 {depth}" if depth < 3 else "深度 3+"
        print(f"   {label} (n={n}):")
        print(f"      Edges: {percent(e_ok, n)} ({safe_div(e_ok, n)})")
        print(f"      SG:    {percent(s_ok, n)} ({safe_div(s_ok, n)})")
        print(f"      Both:  {percent(b_ok, n)} ({safe_div(b_ok, n)})")

    # 3. 包含特定非线性结构
    type_names = ["select", "loop", "and_join"]
    print("\n3. 包含特定非线性结构的正确率")
    for tname in type_names:
        recs = [r for r in merged_records
                if reference_stats.get(r["id"], {}).get("type_cnt", {}).get(tname, 0) > 0]
        if not recs:
            print(f"   包含 {tname}: 无样本")
            continue
        n = len(recs)
        e_ok = sum(1 for r in recs if r["edges_match"])
        s_ok = sum(1 for r in recs if r["sg_match"])
        b_ok = sum(1 for r in recs if r["edges_match"] and r["sg_match"])
        print(f"   包含 {tname} (n={n}):")
        print(f"      Edges: {percent(e_ok, n)} ({safe_div(e_ok, n)})")
        print(f"      SG:    {percent(s_ok, n)} ({safe_div(s_ok, n)})")
        print(f"      Both:  {percent(b_ok, n)} ({safe_div(b_ok, n)})")

    # 4. 纯顺序与混合结构
    print("\n4. 纯顺序与混合结构正确率")
    def get_combo(type_cnt):
        has = []
        for t in type_names:
            if type_cnt.get(t, 0) > 0:
                has.append(t)
        if not has:
            return "sequence"
        has.sort()
        return "+".join(has)

    combo_groups = defaultdict(list)
    for r in merged_records:
        stats = reference_stats.get(r["id"], {})
        combo = get_combo(stats.get("type_cnt", {}))
        combo_groups[combo].append(r)

    for combo in sorted(combo_groups.keys()):
        recs = combo_groups[combo]
        n = len(recs)
        e_ok = sum(1 for r in recs if r["edges_match"])
        s_ok = sum(1 for r in recs if r["sg_match"])
        b_ok = sum(1 for r in recs if r["edges_match"] and r["sg_match"])
        print(f"   {combo} (n={n}):")
        print(f"      Edges: {percent(e_ok, n)} ({safe_div(e_ok, n)})")
        print(f"      SG:    {percent(s_ok, n)} ({safe_div(s_ok, n)})")
        print(f"      Both:  {percent(b_ok, n)} ({safe_div(b_ok, n)})")


if __name__ == "__main__":
    template = load_prompt_template("prompt_predict.txt")

    with open("../intro_structure/stats/processed_data_with_stats.json", "r", encoding="utf-8") as f:
        dataset = json.load(f)

    reference_graphs = {}
    reference_stats = {}
    for item in dataset:
        rid = item["id"]
        reference_graphs[rid] = {
            "edges": item["edges"],
            "script_graph": item["script_graph"]
        }
        reference_stats[rid] = {
            "max_depth": item.get("max_depth", 0),
            "type_cnt": item.get("type_cnt", {})
        }

    # 从断点恢复
    merged_records = load_checkpoint()
    if merged_records:
        print(f"从检查点恢复，已处理 {len(merged_records)} 条数据。")

    # 获取已处理id集合，用于跳过
    processed_ids = {r["id"] for r in merged_records}

    for item in dataset:
        rid = item["id"]
        if rid in processed_ids:
            print(f"跳过已处理: {rid}")
            continue

        print(f"Processing {rid}...")
        res = evaluate_item(item, template, reference_graphs)

        # 构建合并记录（只保留需要的字段）
        record = {
            "id": rid,
            "scenario": item["scenario"],
            "unordered_nodes": item["unordered_nodes"],
            "edges": res.get("generated_edges", []) if "error" not in res else [],
            "script_graph": res.get("generated_sg", {"type": "sequence", "script": []}) if "error" not in res else {"type": "sequence", "script": []},
            "edges_match": res.get("edges_match", False),
            "sg_match": res.get("sg_match", False)
        }

        merged_records.append(record)
        processed_ids.add(rid)

        # 实时写入检查点
        save_checkpoint(merged_records)
        time.sleep(1)

    # 最终写入合并文件
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(merged_records, f, ensure_ascii=False, indent=2)

    print(f"\n合并文件已保存至 {OUTPUT_FILE}")
    compute_statistics(merged_records, reference_stats)
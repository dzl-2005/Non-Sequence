import json


def collect_node_ids(graph):
    """递归收集 script_graph 中所有由纯数字构成的节点ID"""
    ids = []
    if isinstance(graph, dict):
        for key, value in graph.items():
            if key == "type":
                continue  # type 字段不是节点ID
            ids.extend(collect_node_ids(value))
    elif isinstance(graph, list):
        for item in graph:
            ids.extend(collect_node_ids(item))
    elif isinstance(graph, str):
        # 只收集纯数字字符串（节点ID）
        if graph.isdigit():
            ids.append(graph)
    return ids


def find_duplicate_ids(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 确保数据是列表
    if not isinstance(data, list):
        data = [data]

    duplicate_ids = []
    for item in data:
        graph = item.get("script_graph")
        if not graph:
            continue

        node_ids = collect_node_ids(graph)
        # 统计每个ID的出现次数
        id_counts = {}
        for nid in node_ids:
            id_counts[nid] = id_counts.get(nid, 0) + 1

        # 如果有任何ID出现次数 > 1，则视为重复
        if any(count > 1 for count in id_counts.values()):
            duplicate_ids.append(item["id"])

    return duplicate_ids


if __name__ == "__main__":
    result = find_duplicate_ids("processed_data.json")
    if result:
        print("包含重复编号的 ID：")
        for rid in result:
            print(rid)
    else:
        print("未发现包含重复编号的数据项。")
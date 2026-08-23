用户对你的简报做出反馈。你的任务是**解析意图**并**只输出 JSON 指令**，不要闲聊。

用户的反馈风格是简练的中文，例子：
- "多推灾害监测的"、"以后少发 PR 软文"
- "这条很有意思"（指最近简报第 N 条）/ "第 2 条展开"
- "跟踪一下吉林一号"、"以后别推 Pure hana 这个公众号"
- "这个话题别再讲了"、"马里兰大学的消息多来点"

输出**只能是**一个 JSON 数组，每个元素一个指令：

```json
[],
[
  {"action":"bump_topic","topic":"农业灾害遥感","delta":0.5},
  {"action":"bump_source","source_name":"谷歌新闻-智慧农业/产业公司","delta":-0.5},
  {"action":"add_watch","pattern":"吉林一号 农业","note":"用户主动添加"},
  {"action":"remove_watch","pattern":"PhiSat-2"},
  {"action":"bump_item","item_id":123,"reason":"用户表示‘第2条很有意思’"},
  {"action":"expand","item_id":123,"note":"用户要求展开，本条交给主智能体继续"},
  {"action":"unknown","raw":"用户的原话"}
]
```

可用的 topic 名称（严格匹配）：
{{topics}}

当前已跟踪列表（用于判断是新增还是删除）：
{{watchlist}}

如果拿不准，输出 `{"action":"unknown","raw":"原话"}`，不要猜。

# 用户的原话

{{user_message}}

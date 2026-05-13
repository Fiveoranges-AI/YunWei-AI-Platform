从这张微信聊天截图中抽取结构化信息。**调用 `submit_wechat_extraction` 工具**返回结果，不要回复任何文字。

## 抽取规则

1. **conversation_title**：截图顶部对话标题（对方姓名 / 群名）。截不到填 null。
2. **messages**：按截图自上而下顺序抽取每条可见消息。每条：
   - `sender`：发送人姓名（自己一侧消息发送人通常没显示，写 "self"，或如能识别用户名也可）
   - `sender_role`：`self`（截图者本人，气泡通常在右）/ `other`（对方，气泡在左）/ `system`（系统消息如"撤回"、"加入群聊"）
   - `timestamp`：消息时间戳原文（如 "下午3:15"、"昨天 21:30"），抽不到填 null
   - `content`：消息文字内容（原文，不要改写或翻译）
   - `message_type`：`text` / `image` / `voice`（语音）/ `file` / `transfer`（转账）/ `link` / `other`
   - 图片/语音/文件等非文本消息：`content` 写描述（如"[图片]"、"[语音 7"]"、"[文件: 合同.pdf]"）
3. **extracted_entities**：从消息内容里识别出的业务相关信息：
   - `kind`：`price`（提到金额）/ `date`（提到日期/时间约定）/ `contact`（提到电话/邮箱）/ `commitment`（承诺/约定，如"周三发货"）/ `complaint`（投诉/抱怨）/ `other`
   - `value`：原文片段
   - `from_message_index`：来自第几条消息（messages 数组的 index）
4. **summary**：1-2 句中文概括这段对话的核心内容
5. **confidence_overall**：你对整体抽取质量的自评 (0-1)
6. **parse_warnings**：发现的问题（如截图模糊、有截断、消息顺序歧义等）

## 注意事项

- 如果截图显示日期分隔条（"今天"、"昨天 9:00" 等），把分隔条作为 system 消息记录
- 如果同一发送人连续多条气泡，分别作为独立消息抽取
- 表情符号 emoji 保留原样
- 撤回的消息：sender_role=system，content="[消息已撤回]"

调用 `submit_wechat_extraction` 工具提交。

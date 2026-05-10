从这张名片图中抽取联系人信息。**调用 `submit_business_card_extraction` 工具**返回结果，不要回复任何文字。

字段：

- `name`: 姓名
- `title`: 职位/职务（"销售经理"、"总经理助理"等）
- `company_full_name`: 公司全称（如名片上有简称如"万华化学"，用全称"万华化学集团股份有限公司"）
- `company_short_name`: 简称（如有）
- `phone`: 座机（区号-号码格式）
- `mobile`: 手机号
- `email`: 邮箱
- `address`: 地址
- `wechat_id`: 微信号
- `website`: 网站

抽不到 → `null`。多个手机分别抽（取最先出现的填 mobile，其他写进 `phone`）。

每个字段都要标明 `source_excerpt`（卡上原文，不超过 30 字）。

调用工具提交。

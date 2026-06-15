# 客情应答话术优先级投票功能设计

## 需求概述

客情应答中的每条话术，业务员可点"有用/无用"来投票，提高/降低对应话术的优先级，检索时按优先级加权时间综合排序。

## 需求细节确认

1. **投票规则**：每个用户对话术可以反复切换"有用 ↔ 无用"，以最后一次为准
2. **优先级量化**：优先级 = 有用票数 - 无用票数（差值），越高越靠前
3. **影响范围**：全员共享，所有业务员看到相同排序
4. **排序方式**：加权组合排序 = priority × 权重P + 距离今天天数 × 权重T
5. **应用页面**：主页（营销首页）
6. **管理需求**：管理员可查看投票统计并重置投票

## 数据模型

### 新增表：marketing_schedule_vote

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer (PK) | 主键 |
| schedule_id | Integer (FK) | 关联话术 ID |
| user_id | Integer (FK) | 投票用户 ID |
| vote | String(10) | 投票类型：`useful` 或 `useless` |
| created_at | DateTime | 首次投票时间 |
| updated_at | DateTime | 最后更新时间 |

**约束**：`schedule_id + user_id` 联合唯一索引，确保同一用户对话术只有一条记录

### 修改表：marketing_schedule

新增计算属性（Python property，数据库不存储）：

- `vote_useful_count`：有用票数
- `vote_useless_count`：无用票数
- `vote_priority`：优先级 = useful - useless

## 排序算法

主页话术列表综合排序：

```
排序分 = priority × P权重 + 距离今天天数 × T权重
```

- 权重常量：P = 10, T = -1（可配置）
- 距离今天天数：越近权重越高
- 排序：按排序分降序（高的在前）

## API 设计

### 1. 投票/更新投票

```
POST /marketing/api/schedule/<id>/vote
Body: { "vote": "useful" | "useless" }
Response: { "success": true, "priority": 5, "useful_count": 10, "useless_count": 5 }
```

- 用户未投票时：插入新记录
- 用户已投票：更新 vote 和 updated_at
- 返回更新后的投票统计

### 2. 获取用户投票状态（可选，前端用）

```
GET /marketing/api/schedule/<id>/vote
Response: { "vote": "useful" | "useless" | null }
```

### 3. 管理员：投票统计列表

```
GET /marketing/api/admin/schedule-votes?period_id=&date=
Response: [{ schedule_id, content_preview, useful_count, useless_count, priority }, ...]
```

### 4. 管理员：重置投票

```
POST /marketing/api/admin/schedule/<id>/vote/reset
Response: { "success": true }
```

## 前端交互

### 话术卡片新增按钮

在"复制话术并执行"按钮旁边新增两个按钮：

```
👍 有用（默认灰色 outline）
👎 无用（默认灰色 outline）
```

**状态样式**：
- 用户已投票"有用"：👍 显示绿色实心
- 用户已投票"无用"：👎 显示红色实心
- 未投票：两个都是灰色 outline

**交互流程**：
1. 点击按钮 → 立即 AJAX POST 投票接口
2. 成功 → 更新按钮状态 + 显示当前优先级
3. 失败 → 提示错误

### 排序切换

主页列表顶部添加切换按钮：

```
[综合排序] [时间排序]
```

默认"综合排序"，点击"时间排序"切回原逻辑。

### 优先级展示

话术卡片右上角显示优先级徽章：

```
+5  👍10 👎5
```

## 管理员后台

### 入口

营销管理菜单下新增：`话术投票管理`

### 功能

1. **投票统计表**：按栏目/日期筛选，显示所有话术的投票统计
2. **重置功能**：对单条话术执行"重置投票"
3. **可选**：导出投票数据

## 实现计划

1. 新增 `MarketingScheduleVote` 模型
2. 新增 `vote_useful_count`、`vote_useless_count`、`vote_priority` 属性
3. 新增投票相关 API 路由
4. 修改主页查询，添加综合排序
5. 前端添加投票按钮和交互
6. 管理员后台投票管理页面
7. 排序切换功能

## 配置项

```python
# routes_marketing.py
VOTE_PRIORITY_WEIGHT = 10      # P 权重
VOTE_TIME_WEIGHT = -1           # T 权重
```

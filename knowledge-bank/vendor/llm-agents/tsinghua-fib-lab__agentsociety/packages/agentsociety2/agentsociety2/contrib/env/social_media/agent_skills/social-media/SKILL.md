---
name: social-media
description: 社交媒体互动：发帖 / 转发 / 评论 / 点赞 / 关注、刷新 Feed 推荐流、搜索话题贴文。必须通过 ask_env 调用 SocialMediaSpace 工具。
---

# Social Media

SocialMediaSpace 是微博 / Twitter 风格的社交媒体环境。**所有操作通过 `ask_env` 调用**，环境路由器会自动将指令转换为 SocialMediaSpace 工具调用。

## 环境概念

### 用户身份

默认 agent_id === user_id：你在社交媒体中的 id 就是你的 agent id。`ctx={"id": <your_id>}` 提供你的身份；凡 `author_id` / `user_id` / `follower_id` 都填自己的 id，只有对他人发起动作（关注）时才用对方 id。

### 帖子

每条帖子有 `post_id`、`author_id`、`content`、`tags`（话题标签列表）、`post_type`（`original` / `repost` / `comment`），以及 `likes_count` / `comments_count` / `reposts_count` / `view_count`。

### Feed 推荐流

`refresh_feed` 返回按算法排序的贴文流：`chronological`（时间倒序，默认）、`reddit_hot`（热度）、`twitter_ranking`（综合社交关系）、`random`、`mf`（预训练模型）。这是贴文流推荐（Timeline），不是电商物品推荐。

## 可用工具

所有操作通过 `ask_env` 调用，用模板指令 + `variables` 让同类调用结构一致（易变值放 `variables`，指令措辞保持稳定）：

```
ask_env(instruction="<指令模板>", variables={...}, ctx={"id": <your_id>}, readonly=<bool>)
```

### observe_user（只读，observe）

观察自己的状态：资料（粉丝 / 关注 / 发帖数）、最近 Feed（5 条）、收到的互动、近期活动、社交关系变动、可用行为列表。每个 step 先观察。

```
ask_env(instruction="<observe>", ctx={"id": <your_id>})
```

### create_post（非只读）

发布原创帖子。`tags` 为话题标签列表。

```
ask_env(
    instruction="create_post author_id={user_id} content={content} tags={tags}",
    variables={"user_id": 0, "content": "支持更严格的背景审查", "tags": ["guncontrol", "policy"]},
    ctx={"id": 0},
    readonly=False
)
```

### repost（非只读）

转发帖子，可附 `comment`（留空则内容为 `repost <post_id>`）。

```
ask_env(
    instruction="repost user_id={user_id} post_id={post_id} comment={comment}",
    variables={"user_id": 0, "post_id": 3, "comment": ""},
    ctx={"id": 0},
    readonly=False
)
```

### comment_on_post（非只读）

评论帖子。

```
ask_env(
    instruction="comment_on_post user_id={user_id} post_id={post_id} content={content}",
    variables={"user_id": 0, "post_id": 3, "content": "同意这个观点"},
    ctx={"id": 0},
    readonly=False
)
```

### like_post / unlike_post（非只读）

点赞 / 取消点赞。参数：`user_id`、`post_id`。取消点赞把模板里的 `like_post` 换成 `unlike_post` 即可。

```
ask_env(
    instruction="like_post user_id={user_id} post_id={post_id}",
    variables={"user_id": 0, "post_id": 3},
    ctx={"id": 0},
    readonly=False
)
```

### follow_user / unfollow_user（非只读）

关注 / 取消关注。`follower_id` 是自己，`followee_id` 是对方。

```
ask_env(
    instruction="follow_user follower_id={user_id} followee_id={followee_id}",
    variables={"user_id": 0, "followee_id": 7},
    ctx={"id": 0},
    readonly=False
)
```

### view_post（非只读）

查看帖子详情（增加浏览数），用于了解内容与立场后再互动。

```
ask_env(
    instruction="view_post user_id={user_id} post_id={post_id}",
    variables={"user_id": 0, "post_id": 3},
    ctx={"id": 0},
    readonly=False
)
```

### refresh_feed（只读）

刷新 Feed 推荐流，浏览内容、寻找互动对象。

```
ask_env(
    instruction="refresh_feed user_id={user_id} algorithm={algorithm} limit={limit}",
    variables={"user_id": 0, "algorithm": "twitter_ranking", "limit": 10},
    ctx={"id": 0},
    readonly=True
)
```

### search_posts（只读）

搜索贴文。`keyword` 在 content 和 tags 中匹配；`sort_by` 为 `time`（默认）/ `relevance` / `popularity`。

```
ask_env(
    instruction="search_posts keyword={keyword} tags={tags} limit={limit} sort_by={sort_by}",
    variables={"keyword": "guncontrol", "tags": [], "limit": 20, "sort_by": "popularity"},
    ctx={"id": 0},
    readonly=True
)
```

## 示例

### 观察并刷新 Feed

```
ask_env(instruction="<observe>", ctx={"id": 0})
ask_env(
    instruction="refresh_feed user_id={user_id} algorithm={algorithm} limit={limit}",
    variables={"user_id": 0, "algorithm": "twitter_ranking", "limit": 10},
    ctx={"id": 0},
    readonly=True
)
```

### 发帖后点赞热门帖

```
ask_env(
    instruction="create_post author_id={user_id} content={content} tags={tags}",
    variables={"user_id": 0, "content": "支持更严格的背景审查", "tags": ["guncontrol"]},
    ctx={"id": 0},
    readonly=False
)
ask_env(
    instruction="search_posts keyword={keyword} tags={tags} limit={limit} sort_by={sort_by}",
    variables={"keyword": "guncontrol", "tags": [], "limit": 5, "sort_by": "popularity"},
    ctx={"id": 0},
    readonly=True
)
ask_env(
    instruction="like_post user_id={user_id} post_id={post_id}",
    variables={"user_id": 0, "post_id": 7},
    ctx={"id": 0},
    readonly=False
)
```

## 约束

1. **所有操作通过 `ask_env`**。不能直接调用 `create_post`、`refresh_feed` 等函数。
2. **`user_id` 填你自己的 id**（`ctx["id"]`）；只有关注 / 取消关注才需要对方 id（`followee_id`）。
3. 重复点赞、重复关注、关注自己会报错；不确定时先 `view_post` 查看状态。

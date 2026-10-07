from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SocialMediaPerson(BaseModel):
    """
    Social Media Person Model
    """

    model_config = ConfigDict(use_enum_values=True)

    id: int = Field(..., description="Person ID")
    username: str = Field(..., description="Username")
    bio: str | None = Field(None, description="User biography")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Account creation time"
    )
    followers_count: int = Field(0, ge=0, description="Number of followers")
    following_count: int = Field(0, ge=0, description="Number of users being followed")
    posts_count: int = Field(0, ge=0, description="Number of posts created")
    camp_score: float | None = Field(
        None,
        description="Camp score for polarization experiment, optional",
    )
    following: list[int] = Field(
        default_factory=list, description="IDs of users this user follows"
    )
    post_ids: list[int] = Field(
        default_factory=list, description="IDs of posts by this person"
    )
    comment_ids: list[int] = Field(
        default_factory=list, description="IDs of comments by this person"
    )
    liked_post_ids: list[int] = Field(
        default_factory=list, description="IDs of posts liked by this person"
    )

    def __str__(self) -> str:
        return f"User {self.username} (ID: {self.id}), Followers: {self.followers_count}, Following: {self.following_count}, Posts: {self.posts_count}"


class Post(BaseModel):
    """
    贴文模型(原创、转发或评论)
    """

    model_config = ConfigDict(use_enum_values=True)

    post_id: int = Field(..., description="Post ID")
    author_id: int = Field(..., description="Author user ID")
    content: str = Field(..., min_length=1, max_length=5000, description="Post content")
    post_type: Literal["original", "repost", "comment"] = Field(
        "original", description="Post type: original, repost, or comment"
    )
    parent_id: int | None = Field(
        None, description="Parent post ID (for repost and comment)"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="Post creation time"
    )
    likes_count: int = Field(0, ge=0, description="Number of likes")
    reposts_count: int = Field(0, ge=0, description="Number of reposts")
    comments_count: int = Field(0, ge=0, description="Number of comments")
    view_count: int = Field(0, ge=0, description="Number of views")
    liked_by: list[int] = Field(
        default_factory=list, description="User IDs who liked this post"
    )
    tags: list[str] = Field(default_factory=list, description="话题标签列表，最多10个")
    topic_category: str | None = Field(
        None, description="主要话题分类（politics/sports/tech等）"
    )

    def __str__(self) -> str:
        return f"{self.post_type.capitalize()} Post (ID: {self.post_id}) by User {self.author_id}: {self.content[:50]}{'...' if len(self.content) > 50 else ''}, Likes: {self.likes_count}, Reposts: {self.reposts_count}, Comments: {self.comments_count}"


class Comment(BaseModel):
    """Comment Model"""

    model_config = ConfigDict(use_enum_values=True)

    comment_id: int = Field(..., description="Comment ID")
    post_id: int = Field(..., description="Post ID that this comment belongs to")
    author_id: int = Field(..., description="Commenter user ID")
    content: str = Field(
        ..., min_length=1, max_length=2000, description="Comment content"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="Comment creation time"
    )
    likes_count: int = Field(0, ge=0, description="Number of likes")

    def __str__(self) -> str:
        return f"Comment (ID: {self.comment_id}) by User {self.author_id}: {self.content[:30]}{'...' if len(self.content) > 30 else ''}"


__all__ = [
    "Comment",
    "CommentOnPostResponse",
    # Response Models
    "CreatePostResponse",
    "FollowUserResponse",
    "LikePostResponse",
    "ObserveUserResponse",
    "Post",
    "RefreshFeedResponse",
    "RepostResponse",
    "SearchPostsResponse",
    "SocialMediaPerson",
    "UnfollowUserResponse",
    "UnlikePostResponse",
    "ViewPostResponse",
]


# ============ Response Models ============


class CreatePostResponse(BaseModel):
    """创建帖子的响应"""

    post_id: int = Field(..., description="新创建的帖子ID")
    author_id: int = Field(..., description="作者ID")
    content: str = Field(..., description="帖子内容")
    tags: list[str] = Field(default_factory=list, description="话题标签")
    created_at: str = Field(..., description="创建时间(ISO格式)")
    post_type: str = Field("original", description="帖子类型")


class LikePostResponse(BaseModel):
    """点赞帖子的响应"""

    post_id: int = Field(..., description="帖子ID")
    user_id: int = Field(..., description="点赞用户ID")
    total_likes: int = Field(..., description="帖子当前总点赞数")


class UnlikePostResponse(BaseModel):
    """取消点赞的响应"""

    post_id: int = Field(..., description="帖子ID")
    user_id: int = Field(..., description="用户ID")
    total_likes: int = Field(..., description="帖子当前总点赞数")


class FollowUserResponse(BaseModel):
    """关注用户的响应"""

    follower_id: int = Field(..., description="关注者ID")
    followee_id: int = Field(..., description="被关注者ID")
    follower_following_count: int = Field(..., description="关注者的关注数")
    followee_followers_count: int = Field(..., description="被关注者的粉丝数")


class UnfollowUserResponse(BaseModel):
    """取消关注的响应"""

    follower_id: int = Field(..., description="关注者ID")
    followee_id: int = Field(..., description="被关注者ID")
    follower_following_count: int = Field(..., description="关注者的关注数")
    followee_followers_count: int = Field(..., description="被关注者的粉丝数")


class ViewPostResponse(BaseModel):
    """查看帖子的响应"""

    post_id: int = Field(..., description="帖子ID")
    author_id: int = Field(..., description="作者ID")
    content: str = Field(..., description="帖子内容")
    post_type: str = Field(..., description="帖子类型")
    likes_count: int = Field(..., description="点赞数")
    comments_count: int = Field(..., description="评论数")
    reposts_count: int = Field(..., description="转发数")
    view_count: int = Field(..., description="浏览数")
    created_at: str = Field(..., description="创建时间")
    tags: list[str] = Field(default_factory=list, description="话题标签列表")
    topic_category: str | None = Field(None, description="主要话题分类")


class CommentOnPostResponse(BaseModel):
    """评论帖子的响应"""

    comment_id: int = Field(..., description="评论ID")
    post_id: int = Field(..., description="帖子ID")
    user_id: int = Field(..., description="评论者ID")
    content: str = Field(..., description="评论内容")
    total_comments: int = Field(..., description="帖子当前总评论数")


class RepostResponse(BaseModel):
    """转发帖子的响应"""

    new_post_id: int = Field(..., description="新帖子ID")
    original_post_id: int = Field(..., description="原帖子ID")
    user_id: int = Field(..., description="转发者ID")
    comment: str = Field("", description="转发评论")
    original_reposts_count: int = Field(..., description="原帖当前转发数")


class RefreshFeedResponse(BaseModel):
    """刷新Feed的响应"""

    user_id: int = Field(..., description="用户ID")
    algorithm: str = Field(..., description="推荐算法")
    posts: list[dict] = Field(default_factory=list, description="推荐帖子列表")
    count: int = Field(..., description="返回的帖子数量")


class SearchPostsResponse(BaseModel):
    """搜索帖子的响应"""

    keyword: str = Field(..., description="搜索关键词")
    tags: list[str] = Field(default_factory=list, description="标签过滤")
    sort_by: str = Field(..., description="排序方式")
    posts: list[dict] = Field(default_factory=list, description="匹配的帖子")
    count: int = Field(..., description="返回的帖子数量")
    total_matched: int = Field(..., description="总匹配数")


class ObserveUserResponse(BaseModel):
    """用户观察响应 - 用于 <observe> 指令"""

    user_id: int = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    followers_count: int = Field(0, description="粉丝数")
    following_count: int = Field(0, description="关注数")
    posts_count: int = Field(0, description="帖子数")
    profile: dict = Field(default_factory=dict, description="用户档案摘要")
    recent_interactions: list[dict] = Field(
        default_factory=list, description="最近收到的互动"
    )
    recent_activity: list[dict] = Field(
        default_factory=list, description="最近自己的动态"
    )
    social_updates: list[dict] = Field(
        default_factory=list, description="最近社交关系更新"
    )
    recent_feed: list[dict] = Field(
        default_factory=list, description="最近的 Feed 帖子"
    )
    available_actions: list[str] = Field(default_factory=list, description="可用的行为")

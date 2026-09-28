"""
fufu新闻 - 收藏夹文件夹数据模型
================================
定义 FavoriteFolder（收藏夹文件夹）和 FavoriteFolderItem（文件夹-文章关联）ORM 模型。
"""
from sqlalchemy import (
    String, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from app.core.database import Base


class FavoriteFolder(Base):
    """
    收藏夹文件夹 ORM 模型——对应数据库中的 favorite_folder 表。

    字段说明：
    - id: 主键，自增
    - user_id: 外键，关联 user 表的用户（级联删除）
    - name: 文件夹名称（最大 100 字符，同一用户下唯一）
    - icon: 文件夹图标 emoji（默认 📁）
    - is_public: 是否公开（0=私有, 1=公开，默认 0）
    - sort_order: 排序顺序（默认 0）
    - created_at: 创建时间（默认当前 UTC 时间）
    """
    __tablename__ = "favorite_folder"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_folder_user_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    icon: Mapped[str] = mapped_column(String(10), default="📁")
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # 关联的文件夹-文章记录
    items: Mapped[list["FavoriteFolderItem"]] = relationship(
        "FavoriteFolderItem", back_populates="folder", cascade="all, delete-orphan"
    )


class FavoriteFolderItem(Base):
    """
    收藏夹文件夹-文章关联表——对应数据库中的 favorite_folder_item 表。

    字段说明：
    - id: 主键，自增
    - folder_id: 外键，关联 favorite_folder 表（级联删除）
    - article_id: 外键，关联 article 表（级联删除）
    - added_at: 添加时间（默认当前 UTC 时间）
    """
    __tablename__ = "favorite_folder_item"
    __table_args__ = (
        UniqueConstraint("folder_id", "article_id", name="uq_folder_article"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    folder_id: Mapped[int] = mapped_column(
        ForeignKey("favorite_folder.id", ondelete="CASCADE"), index=True, nullable=False
    )
    article_id: Mapped[int] = mapped_column(
        ForeignKey("article.id", ondelete="CASCADE"), index=True, nullable=False
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # 关联的文件夹
    folder: Mapped["FavoriteFolder"] = relationship(
        "FavoriteFolder", back_populates="items"
    )

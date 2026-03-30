from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from sirius_toolbox.core.types import SourceProvider, TaskType


class TaskBase(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    task_type: TaskType
    source: SourceProvider
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    max_retries: int = 2


class SocialCollectTask(TaskBase):
    task_type: TaskType = TaskType.SOCIAL_POST
    source: SourceProvider = SourceProvider.XIAOHONGSHU
    keyword: str
    max_items: int = 50
    headless: bool = False
    debug: bool = False


class PoiCollectTask(TaskBase):
    task_type: TaskType = TaskType.MAP_POI
    source: SourceProvider
    keyword: str
    city: str
    page_size: int = 20
    max_pages: int = 3

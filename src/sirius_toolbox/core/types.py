from enum import StrEnum


class TaskType(StrEnum):
    SOCIAL_POST = "social_post"
    MAP_POI = "map_poi"


class SourceProvider(StrEnum):
    XIAOHONGSHU = "xiaohongshu"
    GAODE = "gaode"
    BAIDU = "baidu"

import typing as t

import ormar

from database import meta, field


class PageInfo(ormar.Model):
    class Meta(meta.BaseMeta):
        tablename: str = "hi3_wiki_pages"
    
    pageid: int = field.Integer()
    title: str = field.String(max_length=50, primary_key=True)
    categories: t.List[str] = field.Array(item_type=str, default=[])
    alias_of: str = field.String(max_length=50, index=True)
    
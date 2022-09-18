import pydantic

from ..backend import api_types


class ContentBase(pydantic.BaseModel):
    class Config:
        allow_mutation = False
        frozen = True

    @classmethod
    def parse_wikitext(cls, wikitext: api_types.WikiText):
        return cls.parse_obj(wikitext.to_dict())

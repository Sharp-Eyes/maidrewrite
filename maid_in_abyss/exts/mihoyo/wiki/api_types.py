import re
import typing as t

import pydantic
import wikitextparser


# API response types

_ContinueAPIResponseComponent = t.TypedDict(
    "_ContinueAPIResponseComponent",
    {"continue": t.Dict[str, str]},
    total=False,
)


class _BatchCompleteAPIResponseComponent(t.TypedDict, total=False):
    batchcomplete: str


class _WarningsAPIResponseComponent(t.TypedDict, total=False):
    warnings: t.Dict[str, t.Dict[t.Literal["*"], str]]


class AnyResponse(
    _ContinueAPIResponseComponent,
    _BatchCompleteAPIResponseComponent,
    _WarningsAPIResponseComponent,
):
    query: t.Dict[t.Literal["pages"], t.Any]


# Request validation

RARITY_SUFFIX_PATTERN = re.compile(r"/\d-star$", flags=re.I)

def _strip_rarity(title: str) -> str:
    return RARITY_SUFFIX_PATTERN.sub("", title, 1)


class TitleContainerValidator(pydantic.BaseModel, extra=pydantic.Extra.forbid):
    ns: int
    title: str


class PageInfoValidator(pydantic.BaseModel, extra=pydantic.Extra.forbid):
    pageid: int
    ns: int
    title: str
    categories: t.Sequence[TitleContainerValidator]
    redirects: t.Sequence[TitleContainerValidator] = []
    alias_of: t.Optional[str] = None

    def unpack_aliases(
        self,
        *,
        base_params: t.Dict[str, t.Any],
    ) -> t.Iterator[t.Dict[str, t.Any]]:
        title = _strip_rarity(self.title)
        base = base_params | {
            "pageid": self.pageid,
            "categories": [category.title for category in self.categories],
            "alias_of": title,
        }
        
        yield base | {"title": title}

        for redirect in self.redirects:
            if title.lower() not in redirect.title.lower():
                yield base | {"title": _strip_rarity(redirect.title)}


class WikiText(wikitextparser.WikiText):
    """Custom extension to wikitextparser's WikiText class such that it
    supports pydantic model validation.
    """

    @classmethod
    def __get_validators__(cls):

        def _validate(value: t.Any):
            if isinstance(value, wikitextparser.WikiText):
                return value
            elif isinstance(value, str):
                return cls(value)
            raise TypeError("WikiText input must be either str or WikiText.")

        yield _validate


class RevisionValidator(pydantic.BaseModel, extra=pydantic.Extra.forbid):
    contentmodel: t.Literal["wikitext"]
    contentformat: t.Literal["text/x-wiki"]
    content: WikiText = pydantic.Field(alias="*")


class PageContentValidator(pydantic.BaseModel, extra=pydantic.Extra.forbid):
    pageid: int
    ns: int
    title: str
    revision: RevisionValidator = pydantic.Field(alias="revisions")  # We only care about main.

    @pydantic.validator("revision", pre=True)
    def _unnest_revisions(
        cls,
        revisions: t.List[t.Any],
    ) -> t.Dict[str, t.Dict[str, str]]:
        return revisions[0]["slots"]["main"]


# Content models

class ContentBase(pydantic.BaseModel):
    class Config:
        allow_mutation = False
        frozen = True

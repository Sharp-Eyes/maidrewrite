import typing as t
import aiohttp
import logging

import pydantic
import wikitextparser

from . import api_types


LOGGER = logging.getLogger(__name__)

WIKI_BASE = "https://honkaiimpact3.fandom.com/"


T = t.TypeVar("T")


class WikiRequest(t.AsyncIterator[T]):

    API_BASE = "https://honkaiimpact3.fandom.com/api.php?"
    _iterator: t.Iterator[t.Dict[str, t.Any]]

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        model: t.Callable[..., T],
        params: t.Dict[str, str],
    ):
        self.session = session
        self.model = model

        self._params = params
        self._iterator = iter(())
        self._continue = {}
        self._done = False

    @property
    def params(self) -> t.Dict[str, str]:
        return self._params | self._continue

    async def get_chunk(self) -> t.Dict[str, t.Any]:
        async with self.session.get(self.API_BASE, params=self.params) as response:
            response.raise_for_status()
            data: api_types.AnyResponse = await response.json()

        if "batchcomplete" in data:
            self._done = True

        if "warnings" in data:
            logging.warn(
                "Encountered one or more warnings in API request to {url}: {warnings}".format(
                    url=response.url,
                    warnings=", ".join(
                        f"{item}={warn['*']}"
                        for item, warn in data["warnings"].items()
                    ),
                )
            )

        self._continue = data.get("continue", {}) 
        return data["query"]["pages"]

    async def __anext__(self) -> T:
        try:
            value = next(self._iterator)
    
        except StopIteration:
            if self._done:
                raise StopAsyncIteration

            chunk = await self.get_chunk()
            self._iterator = iter(chunk.values())
            value = next(self._iterator)

        try:
            return self.model(**value)
        except pydantic.ValidationError as e:
            # This is fully expected to happen for a group of poorly placed categories.
            # Logging these is not really of any benefit, and any warnings that could
            # lead to unexpected/unwanted errors are already logged.
            # Therefore, this can be safely ignored, and the next value can be returned.
            LOGGER.warning(
                "Encountered {num} validation errors while parsing model {model.name}".format(
                    num=len(e.errors()),
                    model=self.model,
                )
            )
            return await self.__anext__()


def wikitext_to_dict(wikitext: wikitextparser.WikiText) -> dict[str, str]:
    return {
        argument.name.strip(): argument.value.strip()
        for template in wikitext.templates
        for argument in template.arguments
        if not template.ancestors()  # Avoid nested arguments
    }

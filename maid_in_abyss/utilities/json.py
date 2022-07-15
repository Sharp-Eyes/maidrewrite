import typing as t

import pydantic

try:
    import orjson

    def dumps(obj: t.Any, *, default: t.Callable[[t.Any], t.Any] = None) -> str:
        return orjson.dumps(obj, default=default).decode()

    pydantic.BaseConfig.json_loads = loads = orjson.loads
    pydantic.BaseConfig.json_dumps = dumps

except ModuleNotFoundError:
    import json

    loads = json.loads
    dumps = json.dumps  # pyright: ignore[reportGeneralTypeIssues]

import typing as t

import ormar
import ormar_postgres_extensions as ormar_pg
import sqlalchemy

T = t.TypeVar("T")


def String(
    *,
    max_length: int,
    min_length: t.Optional[int] = None,
    regex: t.Optional[str] = None,
    **kwargs: t.Any
) -> str:
    return t.cast(
        str,
        ormar.String(
            max_length=max_length,
            min_length=t.cast(int, min_length),
            regex=t.cast(str, regex),
            **kwargs,
        ),
    )


def Integer(
    *,
    minimum: t.Optional[int] = None,
    maximum: t.Optional[int] = None,
    multiple_of: t.Optional[int] = None,
    **kwargs: t.Any
) -> int:
    return t.cast(
        int,
        ormar.Integer(
            maximum=t.cast(int, maximum),
            minimum=t.cast(int, minimum),
            regex=t.cast(int, multiple_of),
            **kwargs,
        ),
    )


ARRAY_TYPE_LOOKUP: t.Dict[t.Any, t.Any] = {
    str: sqlalchemy.String(),
    int: sqlalchemy.Integer(),
}


def Array(item_type: t.Type[T], dimensions: t.Optional[int] = None, **kwargs: t.Any) -> t.List[T]:
    return ormar_pg.ARRAY(
        item_type=ARRAY_TYPE_LOOKUP.get(item_type, item_type), dimensions=dimensions, **kwargs
    )  # type: ignore

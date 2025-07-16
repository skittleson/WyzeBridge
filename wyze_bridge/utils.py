from typing import Optional
from fastapi import Query

def parse_csv_query_param(alias: str):
    """
    Parses a comma-separated string from a query parameter and returns a list of strings.

    This function takes an alias and returns a parser function that can be used
    with a query parameter. The parser function splits the input string by commas,
    strips whitespace from each item, and returns a list of non-empty strings.
    If the input string is None or empty, the parser returns None.

    :param alias: The alias of the query parameter.
    :return: A parser function that takes an optional string and returns an optional list of strings.
    """
    def parser(value: Optional[str] = Query(None, alias=alias)) -> Optional[list[str]]:
        if value is None:
            return None
        return [item.strip() for item in value.split(",") if item.strip()]
    return parser
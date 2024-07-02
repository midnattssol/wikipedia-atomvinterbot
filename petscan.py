#!/usr/bin/env python3.12
"""Provide programmatic access to PetScan.

https://petscan.wmflabs.org/
"""
from __future__ import annotations
from bs4 import BeautifulSoup
import dataclasses as dc
import requests
import itertools as it
import more_itertools as mit
import datetime as dt

PETSCAN_MAIN_TABLE_CSS_SELECTOR = (
    "html body div.container.mt-2 div.row div.col-md-12"
    " div table#main_table.table.table-sm.table-striped tbody"
)


@dc.dataclass(frozen=True)
class PetScanArticleData:
    page_name: str
    page_id: int
    size_bytes: int
    last_change: timestamp

    @classmethod
    def parse(cls, page_name, page_id, namespace, size_bytes, last_change):
        last_change = dt.datetime.strptime(last_change, "%Y%m%d%H%M%S")
        size_bytes = int(size_bytes)
        page_id = int(page_id)

        page_name = (namespace + ":" if namespace not in {"Artikel", "Article"} else "") + page_name

        return cls(page_name, page_id, size_bytes, last_change)


@dc.dataclass(frozen=True)
class PetScanQuery:
    language: str = "en"
    project: str = "wikipedia"
    depth: int = 0
    categories: tuple[str] = tuple()
    is_intersection: bool = True

    # TODO: Add more PetScan query options

    def to_payload(self) -> dict[str, str]:
        return {
            "interface_language": "en",
            "language": self.language,
            "project": self.project,
            "depth": str(self.depth),
            "categories": "\n".join(self.categories),
            "combination": "subset" if self.is_intersection else "union",
            # `doit` performs the search by default without user input
            "doit": "",
        }


def fetch(query: PetScanQuery) -> [str]:
    """Fetch a PetScan query."""
    request = requests.get("https://petscan.wmflabs.org", params=query.to_payload())
    soup = BeautifulSoup(request.text, features="lxml")
    main_table = mit.one(soup.select(PETSCAN_MAIN_TABLE_CSS_SELECTOR))

    rows = main_table.select("tr")

    for row in rows:
        # First index is the index of the article in the query, so we just skip it
        index, *article_data = (i.text for i in row.select("td"))
        yield PetScanArticleData.parse(article_data)


# Example program:
# result = fetch(
#     PetScanQuery(
#         language="sv", categories=["Frankrikes historia", "Alla artiklar som behöver källor"]
#     )
# )
#
# print(mit.take(5, result))

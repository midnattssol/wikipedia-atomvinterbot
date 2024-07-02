#!/usr/bin/env python3.12
""""""
from __future__ import annotations

import dataclasses as dc
import itertools as it

import more_itertools as mit
import pywikibot
import regex as re
from agave import *


@dc.dataclass(slots=True, frozen=True)
class CategoryMembership:
    match: ...
    category_name: str
    sort_as: Maybe[str] = Nil


_RE_CATEGORIES = r"\[\[\s*((?>Kategori|Category)\s*:.*?)(\|.*)?\]\]"
_TOP_CATEGORIES_CACHE = dict()


# Values in _TOP_CATEGORIES_CACHE are Nil if they're currently being processed
# (the membership is currently unknown) or if the category was not a member of either
# of the sets (exhaustive search failed).


def get_supercategories(site_text: str) -> [CategoryMembership]:
    parent_categories = re.finditer(_RE_CATEGORIES, site_text)
    parent_categories = [
        CategoryMembership(i, i.group(1), maybeify(i.group(2)).map(lambda x: x.removeprefix("|")))
        for i in parent_categories
    ]
    parent_categories = [i for i in parent_categories if "{" not in i.category_name]
    return parent_categories


def get_category_set(category: str, category_sets: tuple[tuple[str]], sitename: str) -> bool:
    """
    Return Just(x) if there exists an index x such that `category` is a subcategory of one of `category_sets[x]`,
    or Nil otherwise.
    """
    key = (category, category_sets, sitename)
    print(f"Checking {key}")

    if key in _TOP_CATEGORIES_CACHE:
        return _TOP_CATEGORIES_CACHE[key]

    for i, categories in enumerate(category_sets):
        if category in categories:
            _TOP_CATEGORIES_CACHE[key] = Just(i)
            break

    else:
        _TOP_CATEGORIES_CACHE[key] = Nil

        site = pywikibot.Site(sitename)
        category_source = pywikibot.Page(site, category).text
        parent_categories = [i.category_name for i in get_supercategories(category_source)]

        result = (get_category_set(c, category_sets, sitename) for c in parent_categories)
        result = mit.first(filter(None, result), Nil)

        _TOP_CATEGORIES_CACHE[key] = result

    return _TOP_CATEGORIES_CACHE[key]


def is_template_category(category: str) -> bool:
    return get_category_set(
        category, (("Kategori:Mallar",), ("Kategori:Artiklar",)), "wikipedia:sv"
    ) == Just(0)

#!/usr/bin/env python3.12
""""""
from __future__ import annotations

import dataclasses as dc
import enum
import functools as ft
import itertools as it

import more_itertools as mit
import pywikibot
import regex as re
from agave import *
from project import *
from supercategory import *
import random
import os
import time


def make_proposal(pagename, source):
    if "/" in pagename:
        return ProposedEdit(source)

    supercats = get_supercategories(source)
    supercats = [i for i in supercats if i.sort_as == Just("*")]

    to_space, to_omega = partition(lambda x: is_template_category(x.category_name), supercats)

    to_space = [
        ProposedEditChange(..., *i.match.span(), f"[[{i.category_name}| ]]") for i in to_space
    ]
    to_omega = [
        ProposedEditChange(..., *i.match.span(), f"[[{i.category_name}|Ω]]") for i in to_omega
    ]

    proposal = ProposedEdit(source, to_space + to_omega)

    for change in proposal.changes:
        change.parent = proposal

    return proposal


project = ProjectWithCandidates("fix-template-incorrectly-sorted")
sitename = "wikipedia:sv"
articles_to_fix = project.load_candidates()
articles_to_fix = [
    pagename for pagename in project.load_candidates() if namespace_of(pagename) == "Mall"
]

random.shuffle(articles_to_fix)


def get_edit_summary(changes):
    num_changes = len(changes.changes)
    return f"Korrigera mall med nyckel '*' till 'Ω' i artikelkategorier och ' ' i mallkategorier"


def main():
    ProjectExecutor(
        project, sitename, make_proposal, get_edit_summary, to_edit=articles_to_fix
    ).main()


if __name__ == "__main__":
    main()

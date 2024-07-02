#!/usr/bin/env python3.11
"""Replace {{Reflist}} with <references/>."""
from __future__ import annotations

import json
import os
import random
import time

import colorama
import pywikibot
import regex as re
from agave import *
from project import *


project = ProjectWithCandidates("fix-reflist")

REFLIST_REGEX = r"\n?\{\{[Rr]eflist\}\}\n?"


def make_proposal(pagename, text):
    if "<references/>" in text:
        proposal = ProposedEdit.from_regex(text, REFLIST_REGEX, "")
        return proposal

    proposal = ProposedEdit.from_regex(text, REFLIST_REGEX, "\n<references/>\n")
    return proposal


project = ProjectWithCandidates("fix-reflist")
sitename = "wikipedia:sv"
articles_to_fix = project.load_candidates()
articles_to_fix = [
    pagename for pagename in project.load_candidates() if namespace_of(pagename) == "Main"
]

random.shuffle(articles_to_fix)


def main():
    ProjectExecutor(
        project,
        sitename,
        make_proposal,
        const("Ersätt Mall:Reflist med references-tagg"),
        to_edit=articles_to_fix,
    ).main()


if __name__ == "__main__":
    main()

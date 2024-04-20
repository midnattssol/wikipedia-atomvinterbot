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
from cli import *
from management import *
from proposal import *

project = ProjectWithCandidates("fix-reflist")

REFLIST_REGEX = r"\{\{[Rr]eflist\}\}"


def propmake(pagename, text):
    proposal = ProposedEdit.from_regex(text, REFLIST_REGEX, "<references/>")
    return proposal


project = ProjectWithCandidates("fix-reflist")
sitename = "wikipedia:sv"
articles_to_fix = project.load_candidates()
articles_to_fix = [pagename for pagename in project.load_candidates() if namespace_of(pagename) == "Main"]

random.shuffle(articles_to_fix)


def main():
    for pagename in articles_to_fix:
        os.system("clear")
        perform_semiautomated_edit_with_user_input(
            project, pagename, sitename, propmake, const("Ersätt Mall:Reflist med references-tagg")
        )


if __name__ == "__main__":
    main()

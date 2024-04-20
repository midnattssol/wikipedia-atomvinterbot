#!/usr/bin/env python3.11
""""""
from __future__ import annotations

import time
import json

import pywikibot
import regex as re
import colorama
import random

import os

from proposal import *
from management import *
from agave import *
from cli import *


with open("projects/fix-memory-alpha/data/templates", "r", encoding="utf-8") as file:
    contents = file.read()
    contents = contents.splitlines()

templates_to_replace = "(" + "|".join(map(re.escape, contents)) + ")"

# Make sure the template has ended
TEMPLATE = r"^[^\S\n]*\{\{\s*" + templates_to_replace + r"[\s|}]"


def propmake(pagename, text):
    proposal = ProposedEdit.from_regex_do(text, TEMPLATE, lambda match: "* " + match[0], re.MULTILINE | re.IGNORECASE)
    return proposal


project = ProjectWithCandidates("fix-memory-alpha")
sitename = "wikipedia:sv"
articles_to_fix = project.load_candidates()
articles_to_fix = [pagename for pagename in project.load_candidates() if namespace_of(pagename) == "Main"]

random.shuffle(articles_to_fix)


def get_edit_summary(changes):
    num_changes = len(changes.changes)
    if num_changes == 1:
        return f"Lägg till * före mall i {n} mall"
    return f"Lägg till * före mall i {n} mallar"


def main():
    for pagename in articles_to_fix:
        os.system("clear")
        perform_semiautomated_edit_with_user_input(project, pagename, sitename, propmake, get_edit_summary)
        time.sleep(1)


if __name__ == "__main__":
    main()

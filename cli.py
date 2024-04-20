#!/usr/bin/env python3.11
"""Command-line interface generator."""
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


def perform_semiautomated_edit_with_user_input(
    project,
    pagename,
    sitename,
    make_proposal,
    get_edit_message,
    needs_manual_approval=lambda _: True,
    sleep_time=35,
    debug_context=Nil,
):
    """Create a command-line interface which yields articles for manual approval."""
    assert sleep_time >= 30
    debug_context = dict(debug_context.unwrap_or({}))
    site = pywikibot.Site(sitename)

    debug_context["pagename"] = pagename
    debug_context["sitename"] = sitename

    os.system("clear")
    page = pywikibot.Page(site, pagename)

    if not page.exists():
        debug_context["action"] = f"{project.name}/skip"
        debug_context["reason"] = "non-existent"

        project.log_action(debug_context)

        print(f": skipping article {pagename!r} (article does not exist)")
        mark_candidate_resolved(pagename, f"{project.name}")
        return

    proposal = make_proposal(pagename, page.text)

    if proposal.is_noop():
        debug_context["action"] = f"{project.name}/skip"
        debug_context["reason"] = "no-diff"

        project.log_action(debug_context)

        print(f": skipping article {pagename!r} (no difference from editing)")
        project.mark_candidate_resolved(pagename)
        return

    edit_message = get_edit_message(proposal)

    if needs_manual_approval(proposal):
        n = len(proposal.changes)
        proposal_str = prettyprint_proposed_edit(proposal)

        print(proposal_str)
        print("\n\n")
        print(f": edit on page {pagename!r} with {n} diffs needs manual approval")
        print(f": would apply with edit message {edit_message!r}")
        print(f": [y]es to apply proposal, any other key to skip")

        input_confirm_edit = input(": ").casefold()

        if input_confirm_edit != "y":
            print(": skipping article ([y] not pressed)")
            debug_context["action"] = f"{project.name}/skip"
            project.log_action(debug_context)
            project.mark_candidate_resolved(pagename)
            return

    debug_context["action"] = f"{project.name}/apply-replacement"
    project.log_action(debug_context)

    project.save_page(page, proposal.join(), edit_message)
    project.mark_candidate_resolved(pagename)
    print(f": edit complete! sleeping for {sleep_time} seconds after edit...")
    time.sleep(sleep_time)

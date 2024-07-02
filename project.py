#!/usr/bin/env python3.12
"""Propose a change to an article."""
from __future__ import annotations

import abc
import collections as col
import dataclasses as dc
import datetime as dt
import itertools as it
import json
import os
import pathlib as p
import random
import time

import colorama
import more_itertools as mit
import pywikibot
import regex as re
from agave import *
from termcolor import colored

__all__ = [
    "make_edit_command_line",
    "namespace_of",
    "prettyprint_proposed_edit",
    "Project",
    "ProjectExecutor",
    "ProjectMock",
    "ProjectWithCandidates",
    "ProposedEdit",
    "ProposedEditChange",
]


@dc.dataclass
class Project(abc.ABC):
    name: str

    def save_page(self, page: pywikibot.Page, text: str, edit_message: str):
        page.text = text
        page.save(edit_message)

    def log_action(self, context: dict):
        with open("log-actions.jsonl", "a", encoding="utf-8") as file:
            file.write(json.dumps(context | {"project": self.name, "time": time.time()}) + "\n")


@dc.dataclass
class ProjectWithCandidates(Project):
    def get_path(self):
        path = p.Path("project-data") / self.name / "candidates.txt"
        return path

    def load_candidates(self) -> Thunk:
        with self.get_path().open("r", encoding="utf-8") as file:
            articles_to_fix = file.read()

        articles_to_fix = articles_to_fix.splitlines()
        articles_to_fix = map(normalize_article_name, articles_to_fix)
        return list(articles_to_fix)

    def mark_candidate_resolved(self, pagename: str):
        contents = self.load_candidates()
        contents.remove(pagename)

        with self.get_path().open("w", encoding="utf-8") as file:
            file.write("\n".join(contents))


@dc.dataclass
class ProjectMock(ProjectWithCandidates):
    def save_page(self, page, text, edit_message):
        print(f"Dummy project saved {page} with {edit_message!r} writing {len(text)} chars")


@dc.dataclass
class ProposedEdit:
    source: str
    changes: [ProposedEditChange] = dc.field(default_factory=list)

    def is_noop(self) -> bool:
        return all(i.is_noop() for i in self.changes)

    @classmethod
    def from_regex(cls, source, pattern: re, string: str):
        return cls.from_regex_do(source, pattern, const(string))

    @classmethod
    def from_regex_do(cls, source, pattern: re, replacement_fn: callable, flags=None):
        """Not a re.sub pattern - the replacement must be a normal string.

        Necessary since we don't have the replacement map."""
        parent = cls(source)

        def from_match(match):
            replacement = ProposedEditChange(
                parent, match.start(), match.end(), replacement_fn(match)
            )
            return replacement

        if flags is not None:
            matches = re.finditer(pattern, source, flags=flags)
        else:
            matches = re.finditer(pattern, source)

        changes = map(from_match, matches)
        changes = it.filterfalse(ProposedEditChange.is_noop, changes)

        parent.changes = list(changes)
        return parent

    def join(self) -> str:
        sorted_changes = sorted(self.changes, key=lambda change: change.start, reverse=True)
        new_source = self.source
        for change in sorted_changes:
            new_source = new_source[: change.start] + change.new_text + new_source[change.end :]

        return new_source

    def __or__(self, other):
        assert self.source == other.source
        items = sorted(self.changes + other.changes, key=lambda change: change.start, reverse=True)

        ranges = [range(i.start, i.end) for i in items]

        assert not any_ranges_overlap(ranges)
        return dc.replace(self, changes=items)


@dc.dataclass
class ProposedEditChange:
    parent: ProposedEdit
    start: int
    end: int
    new_text: str

    def is_delete(self) -> bool:
        return (not self.new_text) and not self.is_noop()

    def is_insert(self) -> bool:
        return self.start == self.end and not self.is_noop()

    def is_replace(self) -> bool:
        return not (self.is_delete() or self.is_replace() or self.is_noop())

    def is_noop(self) -> bool:
        is_neither_delete_nor_insert = self.start == self.end and not self.new_text
        return (
            is_neither_delete_nor_insert
            or self.parent.source[self.start : self.end] == self.new_text
        )

    def span(self):
        return self.start, self.end


SpanOrSpace, Span, Space = tagged_union(
    "SpanOrSpace", {"Span": ["start", "end"], "Space": ["start", "end"]}, frozen=True
)


def escape_ansi(text: str) -> str:
    return text.replace("\x1B", "\\x1B")


def any_ranges_overlap(ranges: List[Range]) -> Result[bool, str]:
    if not ranges:
        return False

    sorted_ranges = sorted(ranges, key=lambda r: r[0])

    for i in range(len(sorted_ranges) - 1):
        current_end = sorted_ranges[i][1]
        next_start = sorted_ranges[i + 1][0]

        if current_end >= next_start:
            return True

    return False


def spans_and_spaces(spans, start, top) -> tuple[SpanOrSpace]:
    if not spans:
        return (Space(start, top),)

    if len(spans) == 1:
        return (Space(start, spans[0][0]), Span(*spans[0]), Space(spans[0][1], top))

    return tuple(
        (Space(start, spans[0][0]), Span(*spans[0]), *spans_and_spaces(spans[1:], spans[0][1], top))
    )


def prettyprint_proposed_edit(edit: ProposedEdit) -> str:
    """Prettyprint a proposed edit using ANSI for human approval before saving."""

    def prettyprint_change(change: ProposedEditChange):
        return (
            colored("(proposed edit | current: `", "green")
            + escape_ansi(change.parent.source[change.start : change.end])
            + colored("`, replace with: `", "green")
            + escape_ansi(from_span[(change.start, change.end)].new_text)
            + colored("`)", "green")
        )

    from_span = {change.span(): change for change in edit.changes}
    assert len(from_span) == len(edit.changes)
    positions = spans_and_spaces(sorted(from_span), 0, len(edit.source))

    output = "".join(
        prettyprint_change(from_span[(x.start, x.end)])
        if x.is_span()
        else edit.source[x.start : x.end]
        for x in positions
    )

    return output


def normalize_article_name(name):
    return name.strip().removesuffix("\u200e").strip()


def namespace_of(article_name):
    data = article_name.split(":")
    return data[0] if len(data) > 1 else "Main"


def make_edit_command_line(
    project,
    pagename,
    sitename,
    make_proposal,
    get_edit_summary,
    needs_manual_approval=const(True),
    sleep_time=30,
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

    edit_message = get_edit_summary(proposal)

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


@dc.dataclass
class Event:
    pagename: str
    sitename: str
    debug_context: dict

    proposed_edit: Maybe[ProposedEdit] = Nil


@dc.dataclass
class ProjectExecutor:
    project: Project
    sitename: str

    make_proposal: callable
    get_edit_summary: callable
    needs_manual_approval: int = const(True)
    sleep_time: int = 30

    backlog: col.deque = dc.field(default_factory=col.deque)
    to_edit: list = dc.field(default_factory=list)

    time_until_edit: Maybe[dt.datetime] = Nil

    def try_handle_backlog(self) -> Maybe[dt.timedelta]:
        """Attempt to handle the backlog of actions.

        Returns the amount of time to sleep before trying again.
        """

        while self.backlog:
            # No actual edit on the project
            if not self.backlog[0].proposed_edit:
                action = self.backlog.popleft()

                self.project.log_action(action.debug_context)
                self.project.mark_candidate_resolved(action.pagename)
                continue

            # We want to make an edit on the project, so we check if we have waited for long enough.
            time_left = self.time_until_edit.map(
                lambda timestamp: timestamp - dt.datetime.now()
            ).unwrap_or(dt.timedelta())

            if time_left > dt.timedelta():
                return Just(time_left)

            action = self.backlog.popleft()
            proposed_edit, edit_message = action.proposed_edit.unwrap()
            new_proposed_text = proposed_edit.join()
            page = pywikibot.Page(pywikibot.Site(self.sitename), action.pagename)

            self.project.log_action(action.debug_context)
            self.project.save_page(page, new_proposed_text, edit_message)

            self.time_until_edit = Just(dt.datetime.now() + dt.timedelta(seconds=self.sleep_time))

        return Nil

    def main(self):
        next_edit_earliest = Nil

        for item in self.to_edit:
            self.try_handle_backlog()
            new_edit = self.push_edit(item)

            self.backlog.append(new_edit)

        os.system("clear")
        print(f": info: everything handled, now clearing backlog of {len(self.backlog)} pages")
        print(f": info: expected to take {len(self.backlog) * self.sleep_time} seconds")

        # Handle everything left in the backlog.
        while self.backlog:
            result = self.try_handle_backlog()

            if not result:
                continue

            n_seconds = result.unwrap().total_seconds()
            print(f": sleeping {n_seconds} seconds...")
            time.sleep(n_seconds)

    def push_edit(self, pagename):
        """Create a command-line interface which yields articles for manual approval."""
        debug_context = {}

        debug_context["pagename"] = pagename
        debug_context["sitename"] = self.sitename

        os.system("clear")
        page = pywikibot.Page(pywikibot.Site(self.sitename), pagename)

        if not page.exists():
            debug_context["action"] = f"{self.project.name}/skip"
            debug_context["reason"] = "non-existent"

            print(f": skipping article {pagename!r} (article does not exist)")
            return Event(pagename, self.sitename, debug_context)

        proposal = self.make_proposal(pagename, page.text)

        if proposal.is_noop():
            debug_context["action"] = f"{self.project.name}/skip"
            debug_context["reason"] = "no-diff"

            print(f": skipping article {pagename!r} (no difference from editing)")
            return Event(pagename, self.sitename, debug_context)

        edit_message = self.get_edit_summary(proposal)

        if self.needs_manual_approval(proposal):
            n_changes = len(proposal.changes)
            proposal_str = prettyprint_proposed_edit(proposal)

            print(proposal_str)
            print("\n\n")
            print(f": edit on page {pagename!r} with {n_changes} diffs needs manual approval")
            print(f": would apply with edit message {edit_message!r}")
            print(f": [y]es to apply proposal, any other key to skip")

            input_confirm_edit = input(": ").casefold()

            if input_confirm_edit != "y":
                print(": skipping article ([y] not pressed)")
                debug_context["action"] = f"{self.project.name}/skip"
                return Event(pagename, self.sitename, debug_context)

        debug_context["action"] = f"{self.project.name}/apply-replacement"

        print(f": edit pushed!")
        return Event(pagename, self.sitename, debug_context, Just((proposal, edit_message)))

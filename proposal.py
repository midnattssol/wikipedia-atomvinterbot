#!/usr/bin/env python3.11
"""Propose a change to an article."""
from __future__ import annotations

import dataclasses as dc
import itertools as it

import colorama
import more_itertools as mit
import regex as re
from agave import *
from termcolor import colored

__all__ = [
    "ProposedEdit",
    "TextChange",
    "prettyprint_proposed_edit",
]


@dc.dataclass
class ProposedEdit:
    source: str
    changes: [TextChange] = dc.field(default_factory=list)

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
            replacement = TextChange(parent, match.start(), match.end(), replacement_fn(match))
            return replacement

        if flags is not None:
            matches = re.finditer(pattern, source, flags=flags)
        else:
            matches = re.finditer(pattern, source)
        changes = map(from_match, matches)
        changes = it.filterfalse(TextChange.is_noop, changes)

        parent.changes = list(changes)
        return parent

    def join(self) -> str:
        sorted_changes = sorted(self.changes, key=lambda change: change.start, reverse=True)
        new_source = self.source
        for change in sorted_changes:
            new_source = new_source[: change.start] + change.new_text + new_source[change.end :]

        return new_source


@dc.dataclass
class TextChange:
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
        return is_neither_delete_nor_insert or self.parent.source[self.start : self.end] == self.new_text

    def span(self):
        return self.start, self.end


def escape_ansi(text: str) -> str:
    return text.replace("\x1B", "\\x1B")


SpanOrSpace, Span, Space = tagged_union(
    "SpanOrSpace", {"Span": ["start", "end"], "Space": ["start", "end"]}, frozen=True
)


def spans_and_spaces(spans, start, top):
    if not spans:
        return (Space(start, top),)

    if len(spans) == 1:
        return (Space(start, spans[0][0]), Span(*spans[0]), Space(spans[0][1], top))

    return tuple((Space(start, spans[0][0]), Span(*spans[0]), *spans_and_spaces(spans[1:], spans[0][1], top)))


def prettyprint_proposed_edit(edit: ProposedEdit) -> str:
    """Prettyprint a proposed edit using ANSI for human approval before saving."""

    def prettyprint_change(change: TextChange):
        return (
            colored("(proposed edit | current: ", "green")
            + escape_ansi(change.parent.source[change.start : change.end])
            + colored(", replace with: ", "green")
            + escape_ansi(from_span[(change.start, change.end)].new_text)
            + colored(")", "green")
        )

    from_span = {i.span(): i for i in edit.changes}
    assert len(from_span) == len(edit.changes)
    positions = spans_and_spaces(sorted(from_span), 0, len(edit.source))

    output = "".join(
        prettyprint_change(from_span[(x.start, x.end)]) if x.is_span() else edit.source[x.start : x.end]
        for x in positions
    )

    return output

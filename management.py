#!/usr/bin/env python3.11
"""Manage projects."""
from __future__ import annotations

import dataclasses as dc
import json
import pathlib as p
import time


@dc.dataclass
class Project:
    name: str

    def main(self):
        # Entrypoint for the script to run a project.
        raise NotImplementedError()

    def save_page(self, page, text, edit_message):
        page.text = text
        page.save(edit_message)

    def log_action(self, context):
        with open("log-actions.jsonl", "a", encoding="utf-8") as file:
            file.write(json.dumps(context | {"project": self.name, "time": time.time()}) + "\n")


def normalize_article_name(name):
    return name.strip().removesuffix("\u200e").strip()


@dc.dataclass
class ProjectWithCandidates(Project):
    def load_candidates(self):
        path = p.Path("projects") / self.name / "data" / "candidates"

        # TODO: lazy loading here
        with path.open("r", encoding="utf-8") as file:
            articles_to_fix = file.read()

        articles_to_fix = articles_to_fix.splitlines()
        articles_to_fix = map(normalize_article_name, articles_to_fix)
        return list(articles_to_fix)

    def mark_candidate_resolved(self, pagename):
        contents = self.load_candidates()
        contents.remove(pagename)
        path = p.Path("projects") / self.name / "data" / "candidates"

        with path.open("w", encoding="utf-8") as file:
            file.write("\n".join(contents))


def namespace_of(x):
    data = x.split(":")
    return data[0] if len(data) > 1 else "Main"


@dc.dataclass
class DummyProject(ProjectWithCandidates, Project):
    # Dummy project for testing.

    def save_page(self, page, text, edit_message):
        print(f"Dummy project saved {page} with {edit_message!r} writing {len(text)} chars")

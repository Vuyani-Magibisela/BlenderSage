# SPDX-License-Identifier: GPL-3.0-or-later
import pytest

from core.session import LessonSession
from core.tutorial_schema import parse_lesson
from lesson_fixtures import lesson_data


def new_session():
    return LessonSession(parse_lesson(lesson_data()))


def test_starts_on_first_step():
    s = new_session()
    assert s.current.id == "exists"
    assert not s.can_go_back


def test_next_requires_completion():
    s = new_session()
    assert not s.can_go_next
    with pytest.raises(ValueError):
        s.next()
    s.mark_complete("exists")
    assert s.can_go_next
    s.next()
    assert s.current.id == "size"


def test_completion_is_remembered_after_going_back():
    s = new_session()
    s.mark_complete("exists")
    s.next()
    s.back()
    assert s.current.id == "exists"
    assert "exists" in s.completed
    assert s.can_go_next


def test_skip_leaves_step_incomplete():
    s = new_session()
    s.skip()
    assert s.current.id == "size"
    assert "exists" in s.skipped
    assert "exists" not in s.completed


def test_completing_a_skipped_step_clears_skip():
    s = new_session()
    s.skip()
    s.back()
    s.mark_complete("exists")
    assert "exists" not in s.skipped


def test_manual_confirm_only_where_allowed():
    s = new_session()
    with pytest.raises(ValueError):
        s.confirm()
    s.skip()
    s.skip()
    assert s.current.id == "edit"
    s.confirm()
    assert "edit" in s.completed


def test_finishes_after_last_step():
    s = new_session()
    for _ in range(3):
        s.skip()
    assert s.finished
    assert s.current is None
    s.back()
    assert s.current.id == "edit"

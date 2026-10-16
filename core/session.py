# SPDX-License-Identifier: GPL-3.0-or-later
"""Learner navigation through a lesson.

Navigation only changes which step is shown. It never touches the scene, so
going back or skipping never undoes modelling work.
"""


class LessonSession:
    def __init__(self, lesson):
        self.lesson = lesson
        self.index = 0
        self.completed = set()
        self.skipped = set()

    @property
    def finished(self):
        return self.index >= len(self.lesson.steps)

    @property
    def current(self):
        return None if self.finished else self.lesson.steps[self.index]

    @property
    def can_go_back(self):
        return self.index > 0

    @property
    def can_go_next(self):
        return not self.finished and self.current.id in self.completed

    def mark_complete(self, step_id):
        self.completed.add(step_id)
        self.skipped.discard(step_id)

    def next(self):
        if not self.can_go_next:
            raise ValueError("current step is not complete")
        self.index += 1

    def back(self):
        if self.can_go_back:
            self.index -= 1

    def skip(self):
        if self.finished:
            return
        if self.current.id not in self.completed:
            self.skipped.add(self.current.id)
        self.index += 1

    def confirm(self):
        """Learner confirms a step the teacher allows to be confirmed manually."""
        if self.finished or not self.current.manual_confirm:
            raise ValueError("this step cannot be confirmed manually")
        self.mark_complete(self.current.id)

import contextlib
import io
import sys

import pytest


class _CaptureStdout(contextlib.ContextDecorator):
    def __enter__(self):
        self._stdout = sys.stdout
        self._stringio = io.StringIO()
        sys.stdout = self._stringio
        return self

    def __exit__(self, exc_type, exc, tb):
        sys.stdout = self._stdout

    def getvalue(self):
        return self._stringio.getvalue()


@pytest.fixture
def django_capture_stdout():
    def factory():
        return _CaptureStdout()

    return factory

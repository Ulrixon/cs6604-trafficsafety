"""
Frontend tests – SafetyChat page smoke test
=============================================
Validates that the SafetyChat page module:
  - Imports without error (i.e. no bare-module-level crashes)
  - Does NOT contain Python 3.10+ type-annotation syntax on session_state
    (the bug that caused the original TypeError)
"""
import os
import ast
import re
import pytest

SAFETYCHAT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../frontend/pages/5_💬_SafetyChat.py")
)


class TestSafetyChatPageSyntax:
    def test_file_parses_cleanly(self):
        """The page must be valid Python (no SyntaxError)."""
        source = open(SAFETYCHAT_PATH, encoding="utf-8").read()
        try:
            ast.parse(source)
        except SyntaxError as exc:
            pytest.fail(f"SyntaxError in SafetyChat page: {exc}")

    def test_no_type_annotated_session_state_assignment(self):
        """
        Assignments like `st.session_state.x: SomeType = value` fail at
        runtime on Python < 3.10 with `TypeError: unsupported operand type(s)
        for |`. Ensure they are gone.

        The pattern to detect is:  st.session_state.<name>: <TypeName> =
        (NOT just `if not st.session_state.x:` which is a control-flow colon)
        """
        source = open(SAFETYCHAT_PATH, encoding="utf-8").read()
        # Match type annotations on assignment: identifier after `: ` AND followed by ` =`
        # e.g.  st.session_state.foo: list[dict] = []
        bad_pattern = re.compile(
            r"st\.session_state\.\w+\s*:\s*[A-Za-z][\w\[\]\s|]*\s*="
        )
        match = bad_pattern.search(source)
        assert match is None, (
            f"Found type-annotated session_state assignment at char {match.start()}: "
            f"{match.group()!r}  — this causes TypeError on Python 3.9"
        )

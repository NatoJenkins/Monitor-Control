"""Tests for HOST-05: __main__ guard in host/main.py."""
import ast
import os


class TestMainGuard:
    """HOST-05: host/main.py must have if __name__ == '__main__' guard at module level."""

    def test_main_guard_exists(self):
        """Use ast.parse to verify host/main.py contains an
        `if __name__ == '__main__':` guard at module level.

        This is a BLOCKER — without the guard, Windows multiprocessing spawn
        mode will recursively spawn child processes on import.
        """
        main_path = os.path.join(
            os.path.dirname(__file__), "..", "host", "main.py"
        )
        main_path = os.path.normpath(main_path)

        assert os.path.exists(main_path), f"host/main.py does not exist at {main_path}"

        with open(main_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, filename="host/main.py")

        # Look for `if __name__ == "__main__":` or `if "__main__" == __name__:`
        # at the top level of the module
        guard_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                test = node.test
                # Pattern: __name__ == "__main__"
                if (
                    isinstance(test, ast.Compare)
                    and len(test.ops) == 1
                    and isinstance(test.ops[0], ast.Eq)
                    and len(test.comparators) == 1
                ):
                    left = test.left
                    right = test.comparators[0]
                    # __name__ == "__main__"
                    if (
                        isinstance(left, ast.Name)
                        and left.id == "__name__"
                        and isinstance(right, ast.Constant)
                        and right.value == "__main__"
                    ):
                        guard_found = True
                        break
                    # "__main__" == __name__
                    if (
                        isinstance(left, ast.Constant)
                        and left.value == "__main__"
                        and isinstance(right, ast.Name)
                        and right.id == "__name__"
                    ):
                        guard_found = True
                        break

        assert guard_found, (
            "host/main.py must contain `if __name__ == '__main__':` guard at module level "
            "to prevent recursive subprocess spawning on Windows"
        )

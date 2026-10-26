---
name: deprecate-function
description: Deprecate a Python function so callers get a warning before it is removed. Use when asked to deprecate, phase out, or sunset a function, or to warn callers to move to a replacement. Not for deleting or renaming functions.
metadata:
  version: "1.0.0"
---

# Deprecate a function

Follow every step.

1. In the function body, before any other statement except the docstring, add:
   `warnings.warn("<name> is deprecated; use <replacement> instead.", DeprecationWarning, stacklevel=2)`
   Add `import warnings` at the top of the module if it is missing.
2. Give the function a docstring, or extend the existing one, with a line starting `Deprecated:` that names the replacement.
3. Add a test in `tests/` that calls the function inside `with pytest.warns(DeprecationWarning):` and still checks its result.
4. Add a bullet under `## Unreleased` in `CHANGELOG.md` saying the function is deprecated and naming the replacement.
5. Do not delete or rename the function, and do not change its behaviour.

End your final message with this exact line on its own:
`skill: deprecate-function@1.0.0`

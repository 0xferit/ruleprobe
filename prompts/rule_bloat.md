Follow the team engineering handbook at all times:

1. Use four spaces for indentation, never tabs.
2. Keep lines under 100 characters.
3. Order imports: standard library, then third party, then local, separated by blank lines.
4. Prefer double quotes for strings, except when the string itself contains a double quote.
5. Use `snake_case` for functions and variables, `PascalCase` for classes.
6. Do not use single-letter variable names except as loop indices.
7. Every module begins with a module-level docstring.
8. Avoid wildcard imports.
9. Prefer f-strings over `%` formatting and `str.format`.
10. Do not leave commented-out code in the file.
11. Use `pathlib` rather than `os.path` for filesystem paths.
12. Prefer list comprehensions over `map` and `filter` where readable.
13. Do not shadow built-in names.
14. Constants are module-level and `UPPER_SNAKE_CASE`.
15. Avoid mutable default arguments.
16. Use explicit `return None` when a function can also return a value.
17. Prefer `is` for comparisons against `None`, `True` and `False`.
18. Keep functions under 40 lines.
19. Use type hints on all public function signatures.
20. Do not use `lambda` where a named function would be clearer.
21. Group related definitions together rather than interleaving them.
22. Avoid nested ternary expressions.
23. Prefer `enumerate` over manual index counters.
24. Do not catch bare `Exception` without re-raising or logging.
25. Sort dictionary literals by key where the order is not semantically meaningful.

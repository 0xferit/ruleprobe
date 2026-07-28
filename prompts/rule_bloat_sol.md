Follow the team engineering handbook at all times:

1. Use four spaces for indentation, never tabs.
2. Keep lines under 120 characters.
3. Order imports: forge-std, then third party, then local, separated by blank lines.
4. Use named imports (`import { X } from "..."`), never bare file imports.
5. Use `PascalCase` for contracts, `camelCase` for functions and variables.
6. Prefix internal and private functions with an underscore.
7. Constants are `UPPER_SNAKE_CASE` and declared `constant` or `immutable` where possible.
8. Every file begins with an SPDX licence identifier.
9. Pin the pragma to a caret range, never a bare version.
10. Prefer custom errors over revert strings.
11. Use `uint256` rather than `uint`.
12. Do not use `var` or untyped declarations.
13. Emit an event for every state-changing external function.
14. Order contract members: types, constants, storage, events, errors, modifiers, functions.
15. Order functions: constructor, receive, fallback, external, public, internal, private.
16. Mark functions `view` or `pure` wherever possible.
17. Avoid inline assembly unless there is a measured gas reason.
18. Do not shadow inherited names.
19. Use NatSpec on every public and external function.
20. Prefer `++i` over `i++` in loops.
21. Cache array length outside loops.
22. Avoid nested ternary expressions.
23. Do not leave commented-out code in the file.
24. Use `address(0)` rather than `0x0` for the zero address.
25. Group related declarations together rather than interleaving them.

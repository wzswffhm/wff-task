Fixed wexec to correctly resolve and execute non-.exe commands on Windows:

1. **executable_extensions()** now reads PATHEXT environment variable instead of returning hardcoded (.exe,). Falls back to EXECUTABLE_EXTENSIONS only when PATHEXT is missing.

2. **resolve()** now respects PATHEXT order when searching for commands. Checks if the command name already has an extension from PATHEXT and avoids double-appending (e.g., tool.exe won't become tool.exe.exe).

3. **run()** now detects batch scripts (.cmd/.bat) and launches them through cmd.exe /c instead of direct CreateProcess, ensuring correct exit codes are returned.

All existing tests pass. Verified that:
- Commands without extensions are found via PATHEXT (.cmd, .bat, etc.)
- PATHEXT order determines which file is found when multiple extensions exist
- Commands with extensions don't get double-appended
- Batch scripts execute correctly with proper exit code propagation
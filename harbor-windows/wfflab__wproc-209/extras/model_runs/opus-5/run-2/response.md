Fixed all three Windows-specific process control issues in wproc:

1. **Process tree termination**: Modified `terminate_process()` in `wproc/processes.py` to create a Windows Job Object and assign the child process to it with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`. When timeout occurs, all descendants are automatically terminated when the job is closed.

2. **Output capture on timeout**: Replaced blocking `communicate()` with a background reader thread in `wproc/runner.py` that continuously reads output into a buffer. On timeout, the process is terminated and we wait up to 2 seconds for the reader thread to finish capturing any remaining buffered output, ensuring no data is lost.

3. **Fast exit when child finishes**: Changed `process.wait(timeout)` to poll-based waiting with 0.1s intervals. This allows immediate return when the direct child exits, even if grandchildren still hold the output pipes. The background reader thread continues collecting output independently, preventing hangs on orphaned descendants.

All existing tests pass, and manual validation confirms:
- Timeout correctly terminates entire process trees (python → cmd → deep children)
- Large output (1000+ lines) is fully captured even on timeout
- Commands that exit quickly return immediately with correct returncode and timed_out=False
- Non-zero exit codes are preserved correctly
- check=True raises appropriate exceptions with complete output
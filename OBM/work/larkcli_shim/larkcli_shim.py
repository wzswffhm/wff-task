import os
import subprocess
import sys

# Real node.exe: launching it directly avoids cmd.exe entirely, so '&' inside a
# Feishu URL or JSON payload is never treated as a command separator.
_NODE_CANDIDATES = [
    r"C:\Users\Administrator\.workbuddy\binaries\node\versions\22.22.2-3\node.exe",
    r"C:\nvm4w\nodejs\node.exe",
]

_RUN_JS = (
    r"C:\Users\Administrator\.workbuddy\binaries\node\cli-connector-packages"
    r"\node_modules\@larksuite\cli\scripts\run.js"
)


def _node():
    for candidate in _NODE_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
    return "node"


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    return subprocess.call([_node(), _RUN_JS, *args])


if __name__ == "__main__":
    raise SystemExit(main())

"""Local use:  python -m cards42 <login> [theme]   |   python -m cards42 --raw <login>"""
import json
import sys

from . import api, service

if len(sys.argv) >= 3 and sys.argv[1] == "--raw":
    print(json.dumps(api.fetch_user(sys.argv[2]), indent=2))
else:
    status, _, body, _ = service.respond(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(body)
    sys.exit(0 if status == 200 else 1)

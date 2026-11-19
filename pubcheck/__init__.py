"""pubcheck: one publication check for every writer.

Is this text fit for the repository it is about to be published to? A private target
passes; a public (or unknown) one is scanned for names from the owner's acquaint records,
the owner's own matters ("the operator stated"), private references, session links,
credentials, and, for an unattended writer, @mentions. An unattended writer fails closed.

>>> from pubcheck import check
>>> check("Fixed the parser.", repo="octo/app", public=True, log=False).decision
'pass'

Three ways in, one check: :func:`check` in Python, ``public-text-guard check`` on the
command line (exit 0 pass, 1 flag, 2 unavailable), and
``pubcheck.correspond:before_send`` as correspond's ``before_send``.
"""

from pubcheck.core import Verdict, check
from pubcheck.detectors import DETECTORS, UNATTENDED_DETECTORS, findings
from pubcheck.hold import file_hold

__all__ = [
    "DETECTORS",
    "UNATTENDED_DETECTORS",
    "Verdict",
    "check",
    "file_hold",
    "findings",
]

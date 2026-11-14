"""A rollout farm for Lightlag Traverse: many missions in parallel, locally or on Modal.

    jobs.py       one mission per job, in this process; the unit of work
    search.py     a cross-entropy search over the reference pilot's options, backend-agnostic
    local.py      the commands on a local process pool (small runs, tests, no account needed)
    modal_app.py  the same commands on Modal, one container per mission

It reads `lightlag_traverse` and never edits it: the pilot belongs to the Traverse owner, who
decides whether to adopt any options found here. See docs/traverse-farm.md.
"""

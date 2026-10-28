# -*- coding: utf-8 -*-
"""Thread sizing for the BoTorch-backed optimizers (BO / cBO / AFM-cBO).

torch defaults to one compute thread per physical core. For this workload that
is a *pessimisation*, not a default worth keeping: the acquisition's tensors are
small -- a few hundred training points and q=1 -- so past about eight threads the
per-step OpenMP fork/join and reduction cost outweighs the extra arithmetic.

On a many-core workstation, per-evaluation acquisition cost on a cBO state of a
few hundred points dropped by about 10% going from torch's default thread count
to 8, and a full ``optimize_acqf`` call with gradients (wall time divided by the
forward-pass count) dropped by a similar margin.

CAVEAT worth knowing before mixing old and new runs: a different thread count
means a different floating-point reduction order, so acquisition values shift in
the last bits, L-BFGS follows a slightly different path, and a run can settle on
a different -- equally valid -- local optimum of the acquisition surface. The
objective, constraints and surrogate are identical, so quality is unaffected, but
two runs are NOT bitwise reproducible across a change in thread count. To
reproduce a run made before this cap, set ASPEN_MCP_BO_THREADS to whatever that
run used (torch's default is one thread per physical core).

Scope: the cap is a process-wide environment setting, so it also reaches numpy
and the population-based optimizers in the same server. That is harmless --
their wall time is dominated by Aspen calls, not by BLAS.

Override with ASPEN_MCP_BO_THREADS=<n>. An OMP_NUM_THREADS you set yourself is
always respected and never overwritten.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_MAX_THREADS = 8

_THREAD_ENV_VARS = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


def thread_target() -> int:
    """How many compute threads the BO stack should use on this machine."""
    override = os.environ.get("ASPEN_MCP_BO_THREADS", "").strip()
    if override:
        try:
            n = int(override)
            if n > 0:
                return n
        except ValueError:
            pass
        logger.warning("ignoring invalid ASPEN_MCP_BO_THREADS=%r", override)
    return max(1, min(_MAX_THREADS, os.cpu_count() or 1))


def _preset_thread_env() -> dict:
    """Set the thread environment *before* torch loads its runtime.

    This runs at module import, and this module must therefore be imported before
    torch: an OpenMP runtime reads OMP_NUM_THREADS once, when it initialises, and
    ignores later changes. :func:`cap_threads` resizes torch's own intra-op pool
    afterwards and so covers the case where torch was imported first, but it
    cannot resize a BLAS library's pool.

    An operator's existing setting always wins. ASPEN_MCP_BO_THREADS is the
    exception: it is this project's own knob, so it outranks an inherited
    OMP_NUM_THREADS.
    """
    explicit = os.environ.get("ASPEN_MCP_BO_THREADS", "").strip()
    if not explicit and any(var in os.environ for var in _THREAD_ENV_VARS):
        return {}
    n = thread_target()
    for var in _THREAD_ENV_VARS:
        os.environ[var] = str(n)
    return {"thread_env": n}


try:
    _PRESET = _preset_thread_env()
except Exception:                                           # pragma: no cover
    # Import-time code in a module the server imports at startup: a raise here
    # would take the whole server down for the sake of a thread count.
    _PRESET = {}


def cap_threads() -> dict:
    """Apply the cap to torch's intra-op pool. Call once, after ``import torch``.

    Returns a dict describing what was done, for logging. Never raises: it is
    called from inside the optimizers' ``try: ... except ImportError`` import
    block, which would not catch anything else, so an exception here would escape
    and take the MCP server down at startup. Nothing about a thread count is
    worth that -- the failure mode of doing nothing is simply "runs at the old
    speed".
    """
    done = dict(_PRESET)
    if _PRESET:                          # empty => operator chose; leave it alone
        try:
            import torch

            want = _PRESET["thread_env"]
            if torch.get_num_threads() != want:
                torch.set_num_threads(want)
            done["torch_threads"] = torch.get_num_threads()
        except Exception as exc:                            # pragma: no cover
            logger.debug("thread sizing skipped: %s", exc)
    if done:
        logger.info("BO thread sizing: %s", done)
    return done

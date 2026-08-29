from __future__ import annotations

"""Byte-LUT accelerator for the v9.3P MODEL/RAW beam screen.

v9.3P made beam survivors exact again, but production telemetry still showed the
first BO3 reaching depth 4 only at ~472 s.  The remaining hot path is the
*screening-only* mass calculation: every unique large Python truth-mask is
expanded to 306k individual bits before a NumPy dot product.

v9.3Q keeps the v9.3P exact boundary contract unchanged and only replaces that
screening reduction with a byte lookup table.  For each group of 8 outcome
probabilities we precompute all 256 possible byte sums once.  A mask mass then
becomes one lookup per byte instead of one operation per outcome bit.

The lookup is never trusted for final beam membership.  v9.3P still exact-rechecks
the complete cutoff/headroom set with the legacy ascending-outcome accumulator
before any row survives.  Candidate pool, POOL_LIMIT, BEAM_WIDTH, compatibility,
affinity, score formula, state lattice and final probability maths are unchanged.
"""

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

try:
    from . import symphony_beam_screen_v93p as screen
except ImportError:
    import symphony_beam_screen_v93p as screen

VERSION = "v9.3Q-byte-lut-screen-exact-boundary"


class _ByteLookupScreenMass(screen._VectorScreenMass):
    """Same screening cache API as v9.3P with 8x denser native reductions."""

    def __init__(self, probabilities: tuple[float, ...], seeded: dict[int, float]):
        super().__init__(probabilities, seeded)
        self.byte_lookup = None
        self.byte_positions = None
        if not self.available or np is None:
            return

        padded = np.zeros(self.byte_count * 8, dtype=np.float64)
        if self.count:
            padded[: self.count] = self.array
        blocks = padded.reshape(self.byte_count, 8)
        values = np.arange(256, dtype=np.uint16)[:, None]
        shifts = np.arange(8, dtype=np.uint16)[None, :]
        bits = ((values >> shifts) & 1).astype(np.float64)
        self.byte_lookup = blocks @ bits.T
        self.byte_positions = np.arange(self.byte_count, dtype=np.intp)

    def mass(self, mask: int) -> float:
        mask = int(mask)
        if mask in self.cache:
            self.hits += 1
            return self.cache[mask]
        if not mask:
            self.cache[0] = 0.0
            self.sums += 1
            return 0.0
        if not self.available or self.byte_lookup is None or self.byte_positions is None:
            return super().mass(mask)

        raw = mask.to_bytes(self.byte_count, "little", signed=False)
        packed = np.frombuffer(raw, dtype=np.uint8, count=self.byte_count)
        value = float(
            self.byte_lookup[self.byte_positions, packed].sum(dtype=np.float64)
        )
        self.cache[mask] = value
        self.sums += 1
        return value


def _run_with_patch(callable_):
    original_class = screen._VectorScreenMass
    original_version = screen.VERSION
    screen._VectorScreenMass = _ByteLookupScreenMass
    screen.VERSION = VERSION
    try:
        return callable_()
    finally:
        screen._VectorScreenMass = original_class
        screen.VERSION = original_version


def _cached_compositions(fast, shared_masks, match: dict, candidates: list, outcomes: list[dict], stats_out=None):
    return _run_with_patch(
        lambda: screen._cached_compositions(
            fast,
            shared_masks,
            match,
            candidates,
            outcomes,
            stats_out=stats_out,
        )
    )


class InstalledAdapter:
    def __init__(self, fast_module, shared_masks) -> None:
        self.fast = fast_module
        self.shared_masks = shared_masks
        self.original_screen_class = None
        self.original_screen_version = None
        self.inner = None

    def install(self):
        if self.inner is not None:
            return self
        self.original_screen_class = screen._VectorScreenMass
        self.original_screen_version = screen.VERSION
        screen._VectorScreenMass = _ByteLookupScreenMass
        screen.VERSION = VERSION
        self.inner = screen.install(self.fast, self.shared_masks)
        return self

    def uninstall(self) -> None:
        if self.inner is None:
            return
        self.inner.uninstall()
        screen._VectorScreenMass = self.original_screen_class
        screen.VERSION = self.original_screen_version
        self.inner = None
        self.original_screen_class = None
        self.original_screen_version = None


def install(fast_module, shared_masks) -> InstalledAdapter:
    return InstalledAdapter(fast_module, shared_masks).install()

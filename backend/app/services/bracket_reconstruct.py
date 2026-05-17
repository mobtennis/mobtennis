"""Reconstruct bracket_position for Sackmann-ingested tournaments.

Sackmann's CSV doesn't encode draw position — match_num is roughly the
chronological order of play, not a bracket index. For past tournaments
where we only have Sackmann data, the bracket UI's positional fallback
clumps seeded players at the top of every round.

Algorithm (two passes):

  1. **Walk the winner tree backwards from the Final.** Each round-R+1
     match at position Q is fed by two round-R matches whose winners
     are Q's p1 and p2. The R-match feeding p1 gets slot 2Q; p2 gets
     2Q+1. This recovers the binary tree structure deterministically
     from the (p1, p2, winner) tuples we already have. After this
     step the 4 quarters (QF subtrees) are internally consistent but
     their positions among each other depend on Sackmann's
     winner-as-p1 convention — half of the time the bracket is
     upside-down or rotated.

  2. **Anchor the bracket to standard draw convention.** Apply the
     classic seeding layout:
       - Quarter holding seed 1 → top half, top quarter (Q1), with
         seed 1 at the very top (R128 pos 0).
       - Quarter holding seed 2 → bottom half, bottom quarter (Q4),
         with seed 2 at the very bottom (R128 pos N-1).
       - Quarter linked to Q1 in the SF (= Q2): its highest seed
         goes to the BOTTOM of Q2 (= adjacent to Q1, near the
         top-half SF line).
       - Quarter linked to Q4 in the SF (= Q3): its highest seed
         goes to the TOP of Q3 (= adjacent to Q4, near the bottom-
         half SF line).
     Mirroring is done by swapping subtree children at the right
     levels — F→halves, SF→quarters, and within each quarter, walking
     the anchor's path R128→R64→R32→R16 and flipping at each step
     where the anchor is on the wrong side.

This matches the standard tennis bracket layout: seeds 1 and 2 at the
two corners, seeds 3 and 4 in opposite halves at the inner ends of
their quarters (so they meet at most in the Final, like 1 vs 2).
"""

from __future__ import annotations

import logging

from sqlmodel import Session, select

from app.models.match import Match

log = logging.getLogger(__name__)


# Top-down round walk: F (depth 0) → SF (1) → QF (2) → ... → R128 (6).
ROUNDS = ["F", "SF", "QF", "R16", "R32", "R64", "R128", "R256"]
ROUND_DEPTH = {r: i for i, r in enumerate(ROUNDS)}


def reconstruct_from_winner_tree(session: Session, tournament_id: int) -> dict:
    """Recompute bracket_position for every singles match in the tournament.

    Idempotent — wipes existing positions first. Returns a dict with
    counts. Skips team competitions with multiple Finals (ATP Cup,
    BJK Cup) since they don't fit a single-elimination tree.
    """
    matches = list(session.exec(
        select(Match).where(
            Match.tournament_id == tournament_id,
            Match.is_doubles == False,  # noqa: E712
        )
    ).all())
    if not matches:
        return {"placed": 0, "total": 0, "reason": "no singles matches"}

    for m in matches:
        m.bracket_position = None

    by_round: dict[str, list[Match]] = {}
    for m in matches:
        by_round.setdefault((m.round or "").upper(), []).append(m)

    finals = by_round.get("F") or []
    if len(finals) != 1:
        return {"placed": 0, "total": len(matches), "reason": f"finals={len(finals)}"}

    # ---- pass 1: walk winner tree backwards from F --------------------
    finals[0].bracket_position = 0
    current = [finals[0]]
    deepest = "F"
    for next_label in ROUNDS[1:]:
        next_matches = by_round.get(next_label) or []
        if not next_matches:
            break
        by_winner = {m.winner_id: m for m in next_matches if m.winner_id is not None}
        new_current: list[Match] = []
        for cur in current:
            P = cur.bracket_position
            if P is None:
                continue
            for slot, pid in ((0, cur.player1_id), (1, cur.player2_id)):
                if pid is None:
                    continue
                m = by_winner.get(pid)
                if m is None:
                    continue
                m.bracket_position = 2 * P + slot
                new_current.append(m)
        current = new_current
        if not current:
            break
        deepest = next_label

    deepest_depth = ROUND_DEPTH[deepest]

    # If the tournament is too small to have a QF (e.g., 8-player
    # round-robin or 4-player exhibition), leave the bare reconstruction.
    if "QF" not in by_round or deepest_depth < ROUND_DEPTH["QF"]:
        placed = sum(1 for m in matches if m.bracket_position is not None)
        return {"placed": placed, "total": len(matches)}

    # Position indexes per round for fast lookup; rebuilt by swap_children
    # as it moves matches around.
    indexes: dict[str, dict[int, Match]] = {
        r: {m.bracket_position: m for m in by_round.get(r, []) if m.bracket_position is not None}
        for r in ROUNDS
    }

    def swap_children(parent_round: str, parent_pos: int) -> None:
        """Swap the two child subtrees rooted under (parent_round,
        parent_pos). At every deeper round, the left child's
        positions shift right by `size`; the right child's shift
        left. Positions outside the swapped subtrees are untouched.
        """
        parent_depth = ROUND_DEPTH[parent_round]
        if parent_depth >= deepest_depth:
            return
        for r in ROUNDS:
            d = ROUND_DEPTH[r] - parent_depth
            if d <= 0 or d > deepest_depth - parent_depth:
                continue
            size = 1 << (d - 1)
            a_lo = 2 * parent_pos * size
            b_lo = (2 * parent_pos + 1) * size
            new_index: dict[int, Match] = {}
            for pos, m in indexes[r].items():
                if a_lo <= pos < a_lo + size:
                    new_pos = pos + size
                elif b_lo <= pos < b_lo + size:
                    new_pos = pos - size
                else:
                    new_pos = pos
                m.bracket_position = new_pos
                new_index[new_pos] = m
            indexes[r] = new_index

    leaves_per_quarter = 1 << (deepest_depth - ROUND_DEPTH["QF"])

    def qf_idx_of_seed(seed: int) -> int | None:
        """Which QF subtree (0-3) currently contains the given seed
        number? Determined by the seed's leaf-round match position."""
        for pos, m in indexes[deepest].items():
            if m.player1_seed == seed or m.player2_seed == seed:
                return pos // leaves_per_quarter
        return None

    def lowest_seed_in_quarter(qf_idx: int) -> int | None:
        """Lowest seed number present in the quarter's leaf round."""
        lo = qf_idx * leaves_per_quarter
        best: int | None = None
        for k in range(leaves_per_quarter):
            m = indexes[deepest].get(lo + k)
            if m is None:
                continue
            for s in (m.player1_seed, m.player2_seed):
                if s is None:
                    continue
                if best is None or s < best:
                    best = s
        return best

    def leaf_pos_of_seed(seed: int) -> int | None:
        for pos, m in indexes[deepest].items():
            if m.player1_seed == seed or m.player2_seed == seed:
                return pos
        return None

    def orient_quarter(qf_idx: int, anchor_seed: int | None, want_top: bool) -> None:
        """Mirror within the QF subtree at `qf_idx` so the anchor seed's
        leaf match ends up at the TOP (R128 pos `qf_idx * leaves_per_quarter`)
        when `want_top`, or BOTTOM (`(qf_idx+1) * leaves_per_quarter - 1`)
        otherwise.

        Walks the anchor's path from leaf up to QF. At each level,
        if the anchor sits on the wrong side of its parent (top when we
        want bottom, or vice versa), swap that parent's children.
        """
        if anchor_seed is None:
            return
        pos = leaf_pos_of_seed(anchor_seed)
        if pos is None:
            return
        if pos // leaves_per_quarter != qf_idx:
            return  # not in this quarter — earlier swaps should have ensured it is

        local = pos - qf_idx * leaves_per_quarter
        # rounds_up[0] = leaf round, rounds_up[-1] = QF
        rounds_up = list(reversed(ROUNDS[ROUND_DEPTH["QF"]: deepest_depth + 1]))
        depth_below_qf = deepest_depth - ROUND_DEPTH["QF"]

        for level in range(depth_below_qf):
            parent_round = rounds_up[level + 1]
            local_at_level = local >> level
            slot = local_at_level & 1  # 0 = top child of parent, 1 = bottom
            wrong = (want_top and slot == 1) or (not want_top and slot == 0)
            if wrong:
                # subtree size at parent_round within the QF subtree
                subtree_size_at_parent = 1 << (depth_below_qf - level - 1)
                parent_local = local_at_level >> 1
                parent_pos = qf_idx * subtree_size_at_parent + parent_local
                swap_children(parent_round, parent_pos)
                local ^= 1 << level  # the bit at this level flipped

    # ---- pass 2: anchor to standard draw convention -------------------
    # 1. Bring seed 1 to QF 0 (top half, top quarter).
    s1_qf = qf_idx_of_seed(1)
    if s1_qf is not None and s1_qf >= 2:
        swap_children("F", 0)  # swap top and bottom halves
        s1_qf = qf_idx_of_seed(1)
    if s1_qf == 1:
        swap_children("SF", 0)  # swap QF 0 and QF 1 within top half

    # 2. Bring seed 2 to QF 3 (bottom half, bottom quarter). If seed 2
    #    accidentally ended up in the top half (shouldn't happen in a
    #    real draw — they're always opposite seed 1), leave it.
    s2_qf = qf_idx_of_seed(2)
    if s2_qf == 2:
        swap_children("SF", 1)  # swap QF 2 and QF 3 within bottom half

    # 3. Orient each quarter internally.
    orient_quarter(0, 1, want_top=True)   # Q1: seed 1 at top of Q1
    orient_quarter(3, 2, want_top=False)  # Q4: seed 2 at bottom of Q4
    # Q2 is linked to Q1 in the top-half SF — its highest seed sits
    # adjacent to Q1, i.e., at the BOTTOM of Q2.
    orient_quarter(1, lowest_seed_in_quarter(1), want_top=False)
    # Q3 is linked to Q4 in the bottom-half SF — its highest seed sits
    # adjacent to Q4, i.e., at the TOP of Q3.
    orient_quarter(2, lowest_seed_in_quarter(2), want_top=True)

    placed = sum(1 for m in matches if m.bracket_position is not None)
    return {"placed": placed, "total": len(matches)}

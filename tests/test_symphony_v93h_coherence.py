from backend import symphony_engine_v90 as core
from backend import symphony_coherence_guard_v93h as guard


def _candidate(key: str, pick: str, line: float):
    return core.Candidate(
        key=key,
        label=f"1. set handicap · {pick} {line:+g}",
        market="set1_game_handicap",
        pick=pick,
        line=line,
        checkpoint=None,
        prod_score=60.0,
        shadow_scores={},
        path_probability=None,
        evidence_score=60.0,
        agreement=0.5,
        conflict=0.0,
    )


def test_last_first_player_name_resolves_to_exact_match_side():
    match = {"p1": "Sho Shimabukuro", "p2": "Arthur Rinderknech"}
    installed = guard.install(core)
    try:
        assert core._side_for_pick(match, "Shimabukuro, Sho") == 1
        assert core._side_for_pick(match, "Rinderknech, Arthur") == 2
    finally:
        installed.uninstall()


def test_set1_handicap_uses_exact_set_score_and_rejects_screenshot_conflict():
    match = {"p1": "Sho Shimabukuro", "p2": "Arthur Rinderknech"}
    sho_minus_15 = _candidate("sho|-1.5", "Shimabukuro, Sho", -1.5)
    arthur_minus_45 = _candidate("arthur|-4.5", "Rinderknech, Arthur", -4.5)
    outcomes = [
        {"set1": (6, 4), "prob": 0.6},
        {"set1": (1, 6), "prob": 0.4},
    ]

    installed = guard.install(core)
    try:
        sho_pred = core._predicate(match, sho_minus_15)
        arthur_pred = core._predicate(match, arthur_minus_45)
        assert sho_pred is not None
        assert arthur_pred is not None

        # 6:4 supports Shimabukuro -1.5, never Rinderknech -4.5.
        assert sho_pred(outcomes[0]) is True
        assert arthur_pred(outcomes[0]) is False
        # 1:6 can support Rinderknech -4.5.
        assert arthur_pred(outcomes[1]) is True

        joint, supported = core._joint(outcomes, [sho_pred, arthur_pred])
        assert supported == 2
        assert joint == 0.0

        # One Symphony may contain only one handicap from the same period.
        assert core._compatible(sho_minus_15, arthur_minus_45) is False
    finally:
        installed.uninstall()


def test_name_bridge_does_not_guess_ambiguous_or_different_players():
    installed = guard.install(core)
    try:
        match = {"p1": "Anna Maria", "p2": "Maria Anna"}
        assert core._side_for_pick(match, "Maria, Anna") is None

        match = {"p1": "Carlos Alcaraz", "p2": "Jannik Sinner"}
        assert core._side_for_pick(match, "Novak Djokovic") is None
    finally:
        installed.uninstall()

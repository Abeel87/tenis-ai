from __future__ import annotations

"""Stable safe local fixture matching for Superbet context.

No HTTP requests, no bookmaker prices and no MODEL/RAW probability changes.
Exact normalized player pairs win; relaxed aliases require both-player and time
confirmation; ambiguous candidates are rejected rather than guessed.
"""

from datetime import datetime, timezone

try:
    from . import superbet_market_core as base
except ImportError:
    import superbet_market_core as base

VERSION = "v9.2.7"
MIN_PERSON_SCORE = 0.88
AMBIGUOUS_SCORE_GAP = 0.02
AMBIGUOUS_TIME_GAP_HOURS = 1.0 / 6.0
MAX_SAMPLE_ROWS = 12
IGNORED_NAME_TOKENS = {"jr", "sr", "ii", "iii", "iv"}


def _empty_scope() -> dict:
    return {"checked":0,"exact":0,"relaxed":0,"unmatched":0,"time_rejected":0,"ambiguous_rejected":0,"unmatched_samples":[]}


_TELEMETRY = {"live": _empty_scope(), "cached": _empty_scope()}


def reset_telemetry() -> None:
    _TELEMETRY.clear(); _TELEMETRY.update({"live": _empty_scope(), "cached": _empty_scope()})


def _tokens(value) -> list[str]:
    return [token for token in base._norm(value).split() if token and token not in IGNORED_NAME_TOKENS]


def _token_match_kind(left: str, right: str) -> str | None:
    if left == right: return "exact"
    if len(left) == 1 and len(right) >= 2 and right.startswith(left): return "initial"
    if len(right) == 1 and len(left) >= 2 and left.startswith(right): return "initial"
    shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
    if len(shorter) >= 3 and longer.startswith(shorter): return "prefix"
    return None


def person_score(left, right) -> float:
    if base._name_key(left) and base._name_key(left) == base._name_key(right): return 1.0
    a, b = _tokens(left), _tokens(right)
    if len(a) < 2 or len(b) < 2: return 0.0
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    used: set[int] = set(); kinds: list[str] = []; exact_anchor = False
    for token in shorter:
        chosen = None; chosen_kind = None
        for wanted_kind in ("exact", "prefix", "initial"):
            for idx, candidate in enumerate(longer):
                if idx in used: continue
                kind = _token_match_kind(token, candidate)
                if kind == wanted_kind:
                    chosen, chosen_kind = idx, kind; break
            if chosen is not None: break
        if chosen is None or chosen_kind is None: return 0.0
        used.add(chosen); kinds.append(chosen_kind)
        if chosen_kind == "exact" and len(token) >= 3: exact_anchor = True
    if not exact_anchor: return 0.0
    if all(kind == "exact" for kind in kinds): score = 0.97
    elif "prefix" in kinds and "initial" not in kinds: score = 0.94
    else: score = 0.91
    extras = max(0, len(longer) - len(shorter)); score -= 0.015 * max(0, extras - 1)
    return max(0.0, min(0.99, score))


def _pair_score(app_p1, app_p2, fixture_p1, fixture_p2) -> float:
    if base._pair_key(app_p1, app_p2) == base._pair_key(fixture_p1, fixture_p2): return 1.0
    direct=(person_score(app_p1,fixture_p1),person_score(app_p2,fixture_p2)); crossed=(person_score(app_p1,fixture_p2),person_score(app_p2,fixture_p1)); valid=[pair for pair in (direct,crossed) if min(pair)>=MIN_PERSON_SCORE]
    if not valid:return 0.0
    best=max(valid,key=lambda pair:(min(pair),sum(pair))); return min(best)


def _fixture_fields(row: dict, cached: bool):
    if cached:return row.get("p1"),row.get("p2"),row.get("start_time"),row.get("fixture_id")
    return row.get("participant1Name"),row.get("participant2Name"),row.get("startTime"),row.get("fixtureId")


def _sample(scope: dict, match: dict, reason: str) -> None:
    samples=scope.get("unmatched_samples")
    if not isinstance(samples,list) or len(samples)>=MAX_SAMPLE_ROWS:return
    samples.append({"p1":str(match.get("p1") or ""),"p2":str(match.get("p2") or ""),"scheduled_time":match.get("scheduled_time"),"reason":reason})


def _select(match: dict, fixtures: list[dict], *, cached: bool):
    scope_name="cached" if cached else "live"; scope=_TELEMETRY[scope_name]; scope["checked"]+=1
    app_p1,app_p2=match.get("p1"),match.get("p2"); scheduled=base._parse_dt(match.get("scheduled_time")); ranked=[]; had_name_candidate=False; had_time_rejection=False
    for row in fixtures:
        if not isinstance(row,dict):continue
        fixture_p1,fixture_p2,start_value,fixture_id=_fixture_fields(row,cached); score=_pair_score(app_p1,app_p2,fixture_p1,fixture_p2)
        if score<MIN_PERSON_SCORE:continue
        had_name_candidate=True; exact=score>=0.999
        if scheduled is None:
            if exact:ranked.append((0,-score,0.0,str(fixture_id or ""),row,exact))
            continue
        start=base._parse_dt(start_value)
        if start is None:had_time_rejection=True;continue
        delta=abs((start-scheduled).total_seconds())/3600.0
        if delta>base.MAX_MATCH_TIME_DELTA_HOURS:had_time_rejection=True;continue
        ranked.append((0 if exact else 1,-score,delta,str(fixture_id or ""),row,exact))
    if not ranked:
        if had_time_rejection or (had_name_candidate and scheduled is None):scope["time_rejected"]+=1;_sample(scope,match,"TIME_GUARD")
        else:scope["unmatched"]+=1;_sample(scope,match,"NO_SAFE_NAME_MATCH")
        return None
    ranked.sort(key=lambda item:item[:4]); best=ranked[0]
    if not best[5] and len(ranked)>1:
        second=ranked[1]; best_score,second_score=-best[1],-second[1]
        if not second[5] and abs(best_score-second_score)<AMBIGUOUS_SCORE_GAP and abs(best[2]-second[2])<AMBIGUOUS_TIME_GAP_HOURS and best[3]!=second[3]:
            scope["ambiguous_rejected"]+=1;_sample(scope,match,"AMBIGUOUS_ALIAS");return None
    if best[5]:scope["exact"]+=1
    else:scope["relaxed"]+=1
    return best[4]


def best_fixture_for_match(match: dict, fixtures: list[dict]):
    return _select(match, fixtures if isinstance(fixtures,list) else [], cached=False)


def best_cached_fixture(match: dict, index: dict):
    if not isinstance(index,dict):return None
    exact=index.get(base._pair_key(match.get("p1"),match.get("p2"))) or []
    if exact:return _select(match,list(exact),cached=True)
    rows=[];seen=set()
    for bucket in index.values():
        for row in bucket if isinstance(bucket,list) else []:
            if not isinstance(row,dict):continue
            key=str(row.get("fixture_id") or id(row))
            if key in seen:continue
            seen.add(key);rows.append(row)
    return _select(match,rows,cached=True)


def availability_due(original_due, previous: dict, now) -> bool:
    matching=previous.get("fixture_matching_v927") if isinstance(previous,dict) else None
    if not isinstance(matching,dict) or matching.get("version")!=VERSION:return True
    return bool(original_due(previous,now))


def report(previous: dict | None = None) -> dict:
    previous=previous if isinstance(previous,dict) else {}; live=dict(_TELEMETRY.get("live") or {}); cached=dict(_TELEMETRY.get("cached") or {}); previous_report=previous.get("fixture_matching_v927") if isinstance(previous,dict) else None; live_reused=False
    if int(live.get("checked") or 0)==0 and isinstance(previous_report,dict):
        old_live=previous_report.get("live")
        if isinstance(old_live,dict):live=dict(old_live);live_reused=True
    return {"version":VERSION,"mode":"SAFE_ALIAS_LOCAL_ONLY","live":live,"cached":cached,"live_telemetry_reused_from_previous_refresh":live_reused,"additional_external_requests":0,"prices_used":False,"contract":{"exact_pair_preferred":True,"both_players_must_match":True,"relaxed_match_requires_time_guard":True,"ambiguous_relaxed_match_is_rejected":True,"model_math_unchanged":True,"operator_prices_unused":True}}


def stamp_availability() -> dict:
    availability=base._read(base.AVAILABILITY,{})
    if not isinstance(availability,dict):return report({})
    availability=dict(availability); matching=report(availability); availability["fixture_matching_v927"]=matching; availability["fixture_matching_version"]=VERSION; base._write(base.AVAILABILITY,availability); return matching


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

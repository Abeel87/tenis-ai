from backend.insufficient_history_evidence import classify_short_sample


def test_runtime_count_mismatch_has_highest_priority():
    assert classify_short_sample(
        current_matches=3,
        raw_pre_rows=7,
        clean_total_rows=7,
        clean_dated_rows=7,
        clean_pre_rows=7,
    ) == "runtime_profile_count_mismatch"


def test_hygiene_blocked_when_raw_would_clear_gate():
    assert classify_short_sample(
        current_matches=3,
        raw_pre_rows=6,
        clean_total_rows=3,
        clean_dated_rows=3,
        clean_pre_rows=3,
    ) == "hygiene_blocks_threshold"


def test_undated_rows_are_not_counted_as_safe_history():
    assert classify_short_sample(
        current_matches=3,
        raw_pre_rows=3,
        clean_total_rows=7,
        clean_dated_rows=3,
        clean_pre_rows=3,
    ) == "undated_rows_block_threshold"


def test_post_cutoff_rows_are_not_counted():
    assert classify_short_sample(
        current_matches=3,
        raw_pre_rows=3,
        clean_total_rows=7,
        clean_dated_rows=7,
        clean_pre_rows=3,
    ) == "post_cutoff_rows_block_threshold"


def test_genuine_short_history_stays_short():
    assert classify_short_sample(
        current_matches=3,
        raw_pre_rows=3,
        clean_total_rows=3,
        clean_dated_rows=3,
        clean_pre_rows=3,
    ) == "genuine_short_clean_history"


def test_non_insufficient_case_is_ignored():
    assert classify_short_sample(
        current_matches=5,
        raw_pre_rows=5,
        clean_total_rows=5,
        clean_dated_rows=5,
        clean_pre_rows=5,
    ) == "not_insufficient_sample"

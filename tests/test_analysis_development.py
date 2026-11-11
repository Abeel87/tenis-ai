"""Product evidence contracts; examples are fixtures, never published data."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from backend import history_player_priority_backfill as priority
from backend import symphony2_tracker as tracker
from backend import ineed_builder_shadow as builder
from backend import neuron
from backend import readiness_engine_shadow as readiness
from backend import player_dna_player_state_shadow as player_state
from backend import symphony2_engine as engine
from tests.test_readiness_engine_shadow import _compose, _result, _state_report
from tests.test_ineed_builder_shadow import playable_match, _phase2_direct_feed, _phase2_catalog

NOW = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)


class AnalysisDevelopmentTests(unittest.TestCase):
    def quote_fixture(self):
        match = playable_match()
        match['scheduled_time'] = (NOW + timedelta(hours=2)).isoformat()
        legs = deepcopy(match['symphony2_playable']['signals'])
        for i, leg in enumerate(legs):
            leg['selection_id'] = str(i)
        comp = {'selection': legs, 'joint_probability': 50., 'joint_status': 'EXACT_SHARED_STATE',
                'dependency_diagnostics': {'status': 'EXACT_SHARED_STATE_DIAGNOSTIC_ONLY',
                   'per_leg': [{'selection_id': str(i), 'joint_without_leg_probability': 60.} for i in range(2)]}}
        direct = _phase2_direct_feed()
        direct.update(generated_at=NOW.isoformat(), operator='superbet.pl', status='OK', prices_used=False)
        direct['matches'][0].update(p1='A', p2='B', operator_start_time=match['scheduled_time'])
        catalog = _phase2_catalog()
        catalog['quotes'][0]['odds_timestamp'] = NOW.isoformat()
        artifact = {'mode': builder.BUILDER_QUOTE_ARTIFACT_MODE, 'operator': 'superbet.pl', 'status': 'OK',
                    'direct_generated_at': NOW.isoformat(),
                    **{k: False for k in ('prices_used', 'synthetic_prices', 'production_influence',
                                         'playable_influence', 'symphony_influence', 'ineed_runtime_influence', 'automatic_real_betting')},
                    'matches': [{'match_id': 'm-1', 'p1': 'A', 'p2': 'B', 'event_id': '15000001',
                                 'direct_match_verified': True, 'observed_at': NOW.isoformat(), 'quotes': catalog['quotes']}]}
        return match, comp, direct, artifact, {'odds_max_age_minutes': 108, 'stake_tax_rate': .12}

    def test_exact_builder_quote_and_single_leg_subset_use_existing_economics(self):
        args = self.quote_fixture()
        before = deepcopy(args)
        report = builder.compare_builder_components(*args, now=NOW)
        self.assertEqual(report['full']['combined_odds'], 2.75)
        self.assertAlmostEqual(report['full']['expected_value_net'], .5 * 2.75 * .88 - 1)
        self.assertEqual(report['without_leg'][0]['combined_odds'], 2.)
        self.assertAlmostEqual(report['without_leg'][0]['net_ev_change'], -.154)
        self.assertEqual(args, before)

    def test_builder_rejects_stale_future_duplicate_swapped_and_wrong_event_quotes(self):
        for mutation in ('stale', 'future', 'duplicate', 'swapped', 'event', 'started', 'isolation'):
            with self.subTest(mutation=mutation):
                match, comp, direct, artifact, cfg = self.quote_fixture()
                if mutation == 'stale': direct['generated_at'] = (NOW-timedelta(hours=3)).isoformat()
                if mutation == 'future': direct['generated_at'] = (NOW+timedelta(minutes=1)).isoformat()
                if mutation == 'duplicate': direct['matches'].append(deepcopy(direct['matches'][0]))
                if mutation == 'swapped': direct['matches'][0].update(p1='B', p2='A')
                if mutation == 'event': artifact['matches'][0]['event_id'] = 'other'
                if mutation == 'started': match['scheduled_time'] = (NOW-timedelta(seconds=1)).isoformat()
                if mutation == 'isolation': artifact['production_influence'] = True
                result = builder.compare_builder_components(match, comp, direct, artifact, cfg, now=NOW)
                self.assertIsNone(result['full']['combined_odds'])
                self.assertIsNone(result['full']['expected_value_net'])
                self.assertTrue(all(x['net_ev_change'] is None for x in result['without_leg']))

    def test_readiness_projection_preserves_missingness_and_rejects_foreign_snapshot(self):
        match = _result()
        match.update(p1_id=11, p2_id=22, p1_stats={'matches': 0}, p2_stats={})
        state = _state_report()
        state['current_card']['matches'][0].update(p1_id=11, p2_id=22,
            scheduled_time=match['scheduled_time'].replace('+00:00', 'Z'))
        report = _compose(result=match, player_state=state)
        original = deepcopy(match)
        result = readiness.project_match_evidence([match], report)['1']
        self.assertTrue(result['shadow_available'])
        self.assertIsNotNone(result['player_state'])
        self.assertEqual(result['players']['p1']['matches'], 0)
        self.assertIsNone(result['players']['p2']['matches'])
        self.assertEqual(match, original)
        match['p2'] = 'Different'
        result = readiness.project_match_evidence([match], report)['1']
        self.assertFalse(result['shadow_available'])
        self.assertIsNone(result['dimensions'])

    def test_player_activity_uses_strict_prior_exact_identity_and_keeps_minutes_unknown(self):
        current = [{'id': '123', 'p1_id': 11, 'p2_id': 22, 'scheduled_time': NOW.isoformat()}]
        history = [{'match_id': mid, 'scheduled': NOW+timedelta(hours=hours), 'surface': 'hard',
                    'p1': 11, 'p2': 33, 'contrib': {11: {}}}
                   for mid, hours in [('prior', -24), ('older', -49), ('simultaneous', 0), ('future', 2), ('123', -1)]]
        with patch.object(player_state, '_target_state', side_effect=lambda **kwargs: {}):
            result = player_state.build_current_card_states(history, current, [], [])
        activity = result[0]['player_state']['p1']['recent_activity']
        self.assertEqual(activity['observed_matches_started_48h'], 1)
        self.assertEqual(activity['source_matches'][0]['match_id'], 'prior')
        self.assertIsNone(activity['minutes_on_court_48h'])
        self.assertFalse(activity['fatigue_inferred'])

    def test_soonest_upcoming_player_wins_equal_history_priority(self):
        with TemporaryDirectory() as cache:
            rows = priority._priority_players(
                {'players': {k: {'player_id': i, 'matches': []} for i, k in enumerate(['later', 'soon'], 1)}},
                {'later', 'soon'}, {}, NOW, cache_dir=Path(cache),
                upcoming_times={'later': NOW + timedelta(hours=8), 'soon': NOW + timedelta(hours=1)},
            )
        self.assertEqual([r['key'] for r in rows], ['soon', 'later'])
        self.assertEqual(rows[0]['next_match_at'], (NOW + timedelta(hours=1)).isoformat())

    def test_analysis_journal_is_idempotent_and_records_source_changes(self):
        match = {'id': '123', 'p1': 'Player One', 'p2': 'Player Two',
                 'scheduled_time': (NOW + timedelta(hours=3)).isoformat(),
                 'scored_selections': [{'selection_id': 'a', 'market': 'set1_total', 'pick': 'over', 'line': 8.5,
                                        'operator_model_probability': 70}], 'compositions': {}}
        current = {'generated_at': NOW.isoformat(), 'version': 'test', 'matches': [match]}
        original = deepcopy(current)
        first = tracker.observe_analysis(current, {}, now=NOW)
        self.assertEqual(current, original)
        again = tracker.observe_analysis(current, first, now=NOW)
        self.assertEqual(first, again)
        current['generated_at'] = (NOW + timedelta(minutes=10)).isoformat()
        match['scored_selections'][0]['operator_model_probability'] = 65
        updated = tracker.observe_analysis(current, first, now=NOW + timedelta(minutes=10))
        journal = updated['analysis_observations']['123']
        self.assertEqual(len(journal['observations']), 2)
        self.assertIn('MODEL_PROBABILITY_CHANGED', journal['observations'][-1]['changes'])
        self.assertEqual(first['analysis_observations']['123']['observations'][0]['selections'][0]['probability'], 70)
        late = tracker.observe_analysis(current, updated, now=NOW + timedelta(hours=4))
        self.assertEqual(updated, late)

    def test_journal_rejects_identity_change_and_future_source(self):
        match = {'id': '123', 'p1': 'One', 'p2': 'Two', 'scheduled_time': (NOW + timedelta(hours=3)).isoformat()}
        current = {'generated_at': NOW.isoformat(), 'matches': [match]}
        first = tracker.observe_analysis(current, {}, now=NOW)
        match['p2'] = 'Other'
        self.assertEqual(tracker.observe_analysis(current, first, now=NOW), first)
        current['generated_at'] = (NOW + timedelta(hours=1)).isoformat()
        self.assertEqual(tracker.observe_analysis(current, {}, now=NOW), {})

    def test_neuron_segments_stay_with_their_model_and_known_context(self):
        def row(pid, model, surface):
            return {'prediction_id': pid, 'model_id': model, 'match_key': 'id:'+pid,
                    'captured_at': NOW.isoformat(), 'scheduled_time': (NOW+timedelta(hours=1)).isoformat(),
                    'p1': 'One', 'p2': 'Two', 'surface': surface, 'tour': 'atp',
                    'p1_win_probability': .7, 'elo_p1_win_probability': .6,
                    'settlement': {'status': 'SETTLED', 'result': 'hit'}}
        rows = [row('1', 'old', 'clay'), row('2', 'current', 'hard'), row('3', 'current', None)]
        summary = neuron.summarize_predictions(rows)
        current = summary['by_model']['current']['segments']
        self.assertNotIn('clay', current['surface'])
        self.assertEqual(current['surface']['hard']['settled_matches'], 1)
        self.assertEqual(current['surface']['UNKNOWN']['settled_matches'], 1)
        self.assertIsNone(current['surface']['hard']['production_comparison']['production'])

    def test_builder_comparison_never_multiplies_leg_odds(self):
        legs = [{'selection_id': str(i), 'market': 'set1_total', 'pick': 'over', 'line': float(i)+8.5,
                 'fixture_line_verified': True, 'operator_market_id': str(i),
                 'operator_outcome_id': str(i), 'odds': 2.0} for i in range(3)]
        comp = {'selection': legs, 'joint_probability': 50., 'joint_status': 'EXACT_SHARED_STATE',
                'dependency_diagnostics': {'status': 'EXACT_SHARED_STATE_DIAGNOSTIC_ONLY',
                  'per_leg': [{'selection_id': str(i), 'joint_without_leg_probability': 60.} for i in range(3)]}}
        match = {'id': '123', 'p1': 'One', 'p2': 'Two', 'scheduled_time': (NOW+timedelta(hours=1)).isoformat()}
        cfg = {'odds_max_age_minutes': 108, 'stake_tax_rate': .12}
        original = deepcopy(comp)
        result = builder.compare_builder_components(match, comp, {}, {}, cfg, now=NOW)
        self.assertIsNone(result['full']['combined_odds'])
        self.assertIsNone(result['full']['expected_value_net'])
        self.assertEqual(result['without_leg'][0]['joint_probability'], 60.)
        self.assertEqual(comp, original)
        self.assertFalse(result['ranking_influence'])
        self.assertFalse(result['reservation_enabled'])

    def test_engine_attaches_comparison_only_after_unchanged_final_projection(self):
        match, comp, direct, artifact, cfg = self.quote_fixture()
        match.update(id=match.pop('match_id'), compositions={'2': comp}, recommended_leg_count=2)
        current = {'matches': [match], 'generated_at': NOW.isoformat(), 'model_status': 'TEST', 'matches_count': 1}
        stats = {'current_offer': {'probability_diagnostics': {}}}
        source = deepcopy(match)
        expected = engine._project_final_playable([source], current)
        reads = {engine.RESULTS: [source], engine.HISTORY: [], engine.DATA/'superbet_direct_current.json': direct,
                 engine.DATA/'superbet_builder_quotes_current.json': artifact, engine.ROOT/'config'/'ineed_superbet_pl.json': cfg}
        with patch.object(engine, '_read', side_effect=lambda path, default: reads.get(path, default)), \
             patch.object(engine, 'build', return_value=(deepcopy(current), stats)), patch.object(engine, '_write') as write:
            engine.run()
        published = {call.args[0]: call.args[1] for call in write.call_args_list}
        self.assertEqual(published[engine.RESULTS], expected)
        enriched = published[engine.CURRENT]
        enriched['matches'][0]['compositions']['2'].pop('component_comparison')
        self.assertEqual(enriched, current, 'Ranking, selections and every probability must be preserved')


if __name__ == '__main__':
    unittest.main()

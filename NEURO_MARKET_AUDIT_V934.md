# NEURO Market Audit v9.3.4

This audit is historical input for the isolated NEURO SHADOW implementation now carried directly by PR #108. PR #108 is self-contained and does not require PR #107 to merge first.

The original audit snapshot documented the Superbet market coverage gap before the isolated NEURO SHADOW state, adapter, settlement, tracker, neural training and UI were implemented. Keep this file as an audit record; current runtime capability is defined by the dedicated NEURO SHADOW capability/state modules and their regression tests.

## Original snapshot

- exact current operator selections: 16,363
- selections with model support: 4,768 (29.14%)
- zero-support / UNSCORED selections: 11,595 (70.86%)

## Architecture contract

NEURO SHADOW remains isolated from production:

- production_influence=false
- playable_influence=false
- operator_playable=false
- no Symphony PROD probability changes
- no automatic SHADOW -> PROD promotion
- unsupported or collecting markets do not receive fabricated neural probabilities

## Current implementation notes

PR #108 contains the registry/audit material as well as the current isolated SHADOW implementation, including:

- bounded state expansion for additional market families;
- strict canonical Superbet adapter using only current operator selections and exact verified lines where required;
- settlement coverage and capture-to-settlement contract tests;
- immutable prediction history and reconciliation of previously unverifiable rows;
- leakage-safe feature snapshots;
- match-grouped chronological validation split;
- match-balanced training, validation metrics and standardization;
- distinct-match readiness gate;
- neural artifact version compatibility guards;
- read-only current feed and UI;
- hourly evidence capture plus separate heavier scheduled neural training.

Serve/aces markets remain intentionally blocked from training until a trustworthy final serve-stat source exists.

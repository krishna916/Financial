# M1 Regime-Gated Momentum Resumption

This module validates one frozen hypothesis: partition the closed Strategy V3
qualified/entry/outcome evidence by an independently recomputed signal-date
market regime.

The module reads the V3 output package, PIT Nifty 500 membership, the existing
PIT breadth series, and the existing Nifty 500 index series. V3 output files
are read-only inputs. M1 does not download data, regenerate V3, use the old
Regime/Momentum_Regime labels, or add a stock filter.

Run the complete evidence pipeline from the repository root:

~~~text
python "Swing Trading/research/swing/m1_regime_gated_momentum/run_m1_validation.py"
~~~

Run the focused deterministic tests:

~~~text
python -m pytest -q "Swing Trading/research/swing/m1_regime_gated_momentum/tests"
~~~

The output package contains the source, regime, cohort, friction, robustness,
diagnostic, integrity, gate, and report artifacts required by the frozen M1
specification. PASS advances to portfolio/execution validation; FAIL or
INSUFFICIENT_EVIDENCE closes M1 and proceeds to Candidate 2;
INVALID_RESEARCH_RUN permits only an integrity correction and unchanged rerun.

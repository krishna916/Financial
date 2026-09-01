# RR1 Objective Range Sweep Reversion Validation

## Frozen hypothesis/rules
RR1 tests a liquid point-in-time Nifty 500 stock after an exact 60-session objectively non-directional range, a strict downside sweep and close back inside, next-session Open entry, midpoint target, ATR14 structural stop, 15-session lifecycle, paired raw/practical lenses, and an upper failed-break mirror.

## Universe/window/data coverage
Signal window: 2023-08-01..2026-08-25. Benchmark: ^CRSLDX. PIT membership and adjusted Yahoo OHLCV are the only primary data inputs.

## Funnel and accounting
Range-qualified sessions: 286036; lower signals: 6210; upper signals: 9152.
Lower accepted/cancelled/completed/incomplete: 2495 accepted / 3715 cancelled / 2437 paired complete; upper accepted/cancelled/completed/incomplete: 4115 accepted / 5037 cancelled / 4027 complete.

## Lens A / Lens B / mirror results
Lens A: {'Count': 2437.0, 'Gross_Mean_Return': 0.007904052458557697, 'Gross_Return_PF': 1.275724125575083, 'Base_Net_Mean_Return': 0.0039040524585576956, 'Base_Net_Return_PF': 1.1274883903769162, 'Stress_Net_Mean_Return': 0.0019040524585576934, 'Stress_Net_Return_PF': 1.0602031095419793, 'Severe_Net_Mean_Return': -9.594754144230799e-05, 'Severe_Net_Return_PF': 0.9970618744217152, 'Mean_Base_Excess_Return': -0.0018172226248109559}
Lens B: {'Count': 2437.0, 'Gross_Mean_Return': 0.0015218196111861215, 'Base_Net_Mean_Return': -0.002478180388813882, 'Stress_Net_Mean_Return': -0.0044781803888138795, 'Severe_Net_Mean_Return': -0.006478180388813881, 'Gross_Mean_R': 0.1539587508566432, 'Base_Practical_Mean_R': -0.09946854063835468, 'Stress_Practical_Mean_R': -0.2261821863858536, 'Severe_Practical_Mean_R': -0.3528958321333525, 'Base_Practical_R_PF': 0.8972158531268218, 'Stress_Practical_R_PF': 0.7890851989091345, 'Severe_Practical_R_PF': 0.7002441984746037, 'Mean_Base_Practical_Excess_Return': -0.006811659513962744, 'Practical_Median_R': -1.1427575689157297}
Upper mirror: {'Count': 4027, 'Mean_Gross_Return': 0.010788936849381904}

## Robustness and diagnostics
Temporal halves, calendar-year diagnostics, top-five winner removal, leave-one-year-out, leave-one-symbol-out, bootstrap intervals, exits, benchmark excess, and overlap/capacity are reported in the accompanying CSV artifacts.

## Integrity audit and mandatory gates
Integrity result: PASS.

                Gate Passed                                                      Observed                                     Requirement   Category
   RESEARCH_VALIDITY   True                                                          True          integrity/accounting/evidence all pass   VALIDITY
  SAMPLE_SUFFICIENCY   True {'lower': 2437, 'first': 1075, 'second': 1362, 'upper': 4027} lower>=300, first>=100, second>=100, upper>=100     SAMPLE
       LENS_A_RETURN   True                                                      0.003904                                 mean>0 and PF>1   STRATEGY
       LENS_A_EXCESS  False                                                     -0.001817                                   mean excess>0   STRATEGY
PRACTICAL_EXPECTANCY  False                                                     -0.099469                      mean R>=0.15 and RPF>=1.20   STRATEGY
    PRACTICAL_EXCESS  False                                                     -0.006812                                   mean excess>0   STRATEGY
   STRESS_ROBUSTNESS  False                                                     -0.226182                       stress mean R>0 and RPF>1   STRATEGY
    MIRROR_DIRECTION  False                                                      0.010789          lower mean>upper mean and upper mean<0   STRATEGY
 TEMPORAL_ROBUSTNESS  False                                                         False                       both temporal halves pass ROBUSTNESS
 TOP_FIVE_ROBUSTNESS  False                                                         False                mean R>0 and RPF>1 after removal ROBUSTNESS
  LEAVE_ONE_YEAR_OUT  False                                                         False                      every year omission passes ROBUSTNESS
LEAVE_ONE_SYMBOL_OUT  False                                                         False                    every symbol omission passes ROBUSTNESS

FINAL_STATUS: FAIL

RR1 is the final planned strategy-family test. Diagnostics cannot tune or rescue the frozen methodology; after this verdict the swing strategy-family program must be reassessed rather than expanded.

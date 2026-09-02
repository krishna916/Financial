# RR1 Objective Range Sweep Reversion Validation

## Frozen hypothesis/rules
RR1 tests a liquid point-in-time Nifty 500 stock after an exact 60-session objectively non-directional range, a strict downside sweep and close back inside, next-session Open entry, midpoint target, ATR14 structural stop, 15-session lifecycle, paired raw/practical lenses, and an upper failed-break mirror.

## Universe/window/data coverage
Signal window: 2023-08-01..2026-08-25. Benchmark: ^CRSLDX. PIT membership and adjusted Yahoo OHLCV are the only primary data inputs.

## Funnel and accounting
Range-qualified sessions: 285367; lower signals: 6204; upper signals: 9119.
Lower accepted/cancelled/completed/incomplete: 2495 accepted / 3709 cancelled / 2437 paired complete; upper accepted/cancelled/completed/incomplete: 4105 accepted / 5014 cancelled / 4017 complete.

## Lens A / Lens B / mirror results
Lens A: {'Count': 2437.0, 'Gross_Mean_Return': 0.007880325841939324, 'Gross_Return_PF': 1.2745827549172029, 'Base_Net_Mean_Return': 0.003880325841939321, 'Base_Net_Return_PF': 1.1265714431557687, 'Stress_Net_Mean_Return': 0.0018803258419393203, 'Stress_Net_Return_PF': 1.0593879056022688, 'Severe_Net_Mean_Return': -0.00011967415806068168, 'Severe_Net_Return_PF': 0.9963391644516403, 'Mean_Base_Excess_Return': -0.0018771748816529719}
Lens B: {'Count': 2437.0, 'Gross_Mean_Return': 0.0014839880261016095, 'Base_Net_Mean_Return': -0.002516011973898394, 'Stress_Net_Mean_Return': -0.004516011973898393, 'Severe_Net_Mean_Return': -0.006516011973898395, 'Gross_Mean_R': 0.15137163361000106, 'Base_Practical_Mean_R': -0.10223967285610684, 'Stress_Practical_Mean_R': -0.22904532608916078, 'Severe_Practical_Mean_R': -0.35585097932221477, 'Base_Practical_R_PF': 0.8944804747180976, 'Stress_Practical_R_PF': 0.7866843036128137, 'Severe_Practical_R_PF': 0.69812621039812, 'Mean_Base_Practical_Excess_Return': -0.006844437097103523, 'Practical_Median_R': -1.1434173533217205}
Upper mirror: {'Count': 4017, 'Mean_Gross_Return': 0.010369029606316138}

## Robustness and diagnostics
Temporal halves, calendar-year diagnostics, top-five winner removal, leave-one-year-out, leave-one-symbol-out, bootstrap intervals, exits, benchmark excess, and overlap/capacity are reported in the accompanying CSV artifacts.

## Integrity audit and mandatory gates
Integrity result: PASS.

                Gate Passed                                                      Observed                                     Requirement   Category
   RESEARCH_VALIDITY   True                                                          True          integrity/accounting/evidence all pass   VALIDITY
  SAMPLE_SUFFICIENCY   True {'lower': 2437, 'first': 1074, 'second': 1363, 'upper': 4017} lower>=300, first>=100, second>=100, upper>=100     SAMPLE
       LENS_A_RETURN   True                                                       0.00388                                 mean>0 and PF>1   STRATEGY
       LENS_A_EXCESS  False                                                     -0.001877                                   mean excess>0   STRATEGY
PRACTICAL_EXPECTANCY  False                                                      -0.10224                      mean R>=0.15 and RPF>=1.20   STRATEGY
    PRACTICAL_EXCESS  False                                                     -0.006844                                   mean excess>0   STRATEGY
   STRESS_ROBUSTNESS  False                                                     -0.229045                       stress mean R>0 and RPF>1   STRATEGY
    MIRROR_DIRECTION  False                                                      0.010369          lower mean>upper mean and upper mean<0   STRATEGY
 TEMPORAL_ROBUSTNESS  False                                                         False                       both temporal halves pass ROBUSTNESS
 TOP_FIVE_ROBUSTNESS  False                                                         False                mean R>0 and RPF>1 after removal ROBUSTNESS
  LEAVE_ONE_YEAR_OUT  False                                                         False                      every year omission passes ROBUSTNESS
LEAVE_ONE_SYMBOL_OUT  False                                                         False                    every symbol omission passes ROBUSTNESS

FINAL_STATUS: FAIL

RR1 is the final planned strategy-family test. Diagnostics cannot tune or rescue the frozen methodology; after this verdict the swing strategy-family program must be reassessed rather than expanded.

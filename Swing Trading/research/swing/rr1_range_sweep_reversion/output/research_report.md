# RR1 Objective Range Sweep Reversion Validation

## Frozen hypothesis/rules
RR1 tests a liquid point-in-time Nifty 500 stock after an exact 60-session objectively non-directional range, a strict downside sweep and close back inside, next-session Open entry, midpoint target, ATR14 structural stop, 15-session lifecycle, paired raw/practical lenses, and an upper failed-break mirror.

## Universe/window/data coverage
Signal window: 2023-08-01..2026-08-25. Benchmark: ^CRSLDX. PIT membership and adjusted Yahoo OHLCV are the only primary data inputs.

## Funnel and accounting
Range-qualified sessions: 371971; lower signals: 6213; upper signals: 9156.
Lower accepted/cancelled/completed/incomplete: 2497 accepted / 3716 cancelled / 2439 paired complete; upper accepted/cancelled/completed/incomplete: 4117 accepted / 5039 cancelled / 4029 complete.

## Lens A / Lens B / mirror results
Lens A: {'Count': 2439.0, 'Gross_Mean_Return': 0.00785199002404673, 'Gross_Return_PF': 1.2735589177131799, 'Base_Net_Mean_Return': 0.0038519900240467273, 'Base_Net_Return_PF': 1.1256313293139415, 'Stress_Net_Mean_Return': 0.0018519900240467266, 'Stress_Net_Return_PF': 1.0584858209305699, 'Severe_Net_Mean_Return': -0.0001480099759532741, 'Severe_Net_Return_PF': 0.9954729387705233, 'Mean_Base_Excess_Return': -0.0018720867517614224}
Lens B: {'Count': 2439.0, 'Gross_Mean_Return': 0.0014364454957774525, 'Base_Net_Mean_Return': -0.0025635545042225513, 'Stress_Net_Mean_Return': -0.00456355450422255, 'Severe_Net_Mean_Return': -0.00656355450422255, 'Gross_Mean_R': 0.14995903048797748, 'Base_Practical_Mean_R': -0.1034823463156019, 'Stress_Practical_Mean_R': -0.23020303471739162, 'Severe_Practical_Mean_R': -0.3569237231191814, 'Base_Practical_R_PF': 0.8932114124992016, 'Stress_Practical_R_PF': 0.785616877277383, 'Severe_Practical_R_PF': 0.6972124546938974, 'Mean_Base_Practical_Excess_Return': -0.006870086204737931, 'Practical_Median_R': -1.1434734544418195}
Upper mirror: {'Count': 4029, 'Mean_Gross_Return': 0.010433783270932445}

## Robustness and diagnostics
Temporal halves, calendar-year diagnostics, top-five winner removal, leave-one-year-out, leave-one-symbol-out, bootstrap intervals, exits, benchmark excess, and overlap/capacity are reported in the accompanying CSV artifacts.

## Integrity audit and mandatory gates
Integrity result: PASS.

                Gate Passed                                                      Observed                                     Requirement   Category
   RESEARCH_VALIDITY   True                                                          True          integrity/accounting/evidence all pass   VALIDITY
  SAMPLE_SUFFICIENCY   True {'lower': 2439, 'first': 1075, 'second': 1364, 'upper': 4029} lower>=300, first>=100, second>=100, upper>=100     SAMPLE
       LENS_A_RETURN   True                                                      0.003852                                 mean>0 and PF>1   STRATEGY
       LENS_A_EXCESS  False                                                     -0.001872                                   mean excess>0   STRATEGY
PRACTICAL_EXPECTANCY  False                                                     -0.103482                      mean R>=0.15 and RPF>=1.20   STRATEGY
    PRACTICAL_EXCESS  False                                                      -0.00687                                   mean excess>0   STRATEGY
   STRESS_ROBUSTNESS  False                                                     -0.230203                       stress mean R>0 and RPF>1   STRATEGY
    MIRROR_DIRECTION  False                                                      0.010434          lower mean>upper mean and upper mean<0   STRATEGY
 TEMPORAL_ROBUSTNESS  False                                                         False                       both temporal halves pass ROBUSTNESS
 TOP_FIVE_ROBUSTNESS  False                                                         False                mean R>0 and RPF>1 after removal ROBUSTNESS
  LEAVE_ONE_YEAR_OUT  False                                                         False                      every year omission passes ROBUSTNESS
LEAVE_ONE_SYMBOL_OUT  False                                                         False                    every symbol omission passes ROBUSTNESS

FINAL_STATUS: FAIL

RR1 is the final planned strategy-family test. Diagnostics cannot tune or rescue the frozen methodology; after this verdict the swing strategy-family program must be reassessed rather than expanded.

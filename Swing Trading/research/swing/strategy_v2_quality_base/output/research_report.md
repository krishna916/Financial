# Strategy V2 Quality-Base Breakout Validation

## 1. Locked hypothesis
Strategy V2 validates RS leader → pivot → quality base → volatility contraction → breakout → controlled next-session entry.
Design spec: `Swing Trading/docs/superpowers/specs/2026-08-26-strategy-v2-quality-base-breakout-design.md`.

## 2. Data and timing
Signal window: 2023-08-01 through 2026-08-25. Yahoo Finance daily OHLCV uses `auto_adjust=True`; indicators use standard Wilder ATR14.
Point-in-time membership: `market_breadth/config/nifty500_membership.csv`. Breadth is diagnostic-only and joined from a strictly prior date.

## 3. Download and audit counts
Usable symbols: 653; audited symbols: 662.
RS audit dates: 760; unsafe RS dates: 0.

## 4. RS coverage
Minimum coverage: 0.8942115768463074; median: 0.9801192842942346.

## 5. Base events and rejections
Base events: {'SEEDED': 25094, 'FAILED_PROBE': 21934, 'TOO_SHORT_BREAKOUT': 14761, 'DEPTH_INVALIDATED': 5557, 'BREAKOUT_CANDIDATE': 3267, 'EXPIRED': 1269}.
Signal rejection reasons: {'CONTRACTION_FAIL': 740, nan: 250, 'RS_FAIL;CONTRACTION_FAIL': 170, 'NOT_POINT_IN_TIME_MEMBER;RS_FAIL;CONTRACTION_FAIL': 132, 'CONTRACTION_FAIL;SIGNAL_EXTENDED': 128, 'TREND_FAIL;RS_FAIL;CONTRACTION_FAIL': 104, 'RS_FAIL': 96, 'TREND_FAIL;CONTRACTION_FAIL': 84, 'NOT_POINT_IN_TIME_MEMBER;LIQUIDITY_FAIL;RS_FAIL;CONTRACTION_FAIL': 55, 'NOT_POINT_IN_TIME_MEMBER;RS_FAIL': 49, 'SIGNAL_EXTENDED': 49, 'TREND_FAIL': 40, 'TREND_FAIL;RS_FAIL': 38, 'NOT_POINT_IN_TIME_MEMBER;RS_FAIL;CONTRACTION_FAIL;SIGNAL_EXTENDED': 36, 'NOT_POINT_IN_TIME_MEMBER;LIQUIDITY_FAIL;TREND_FAIL;RS_FAIL;CONTRACTION_FAIL': 33, 'TREND_FAIL;CONTRACTION_FAIL;SIGNAL_EXTENDED': 24, 'NOT_POINT_IN_TIME_MEMBER;TREND_FAIL;RS_FAIL;CONTRACTION_FAIL': 20, 'NOT_POINT_IN_TIME_MEMBER;LIQUIDITY_FAIL;RS_FAIL': 16, 'RS_FAIL;CONTRACTION_FAIL;SIGNAL_EXTENDED': 16, 'NOT_POINT_IN_TIME_MEMBER;LIQUIDITY_FAIL;TREND_FAIL;RS_FAIL': 15, 'LIQUIDITY_FAIL;RS_FAIL;CONTRACTION_FAIL': 13, 'NOT_POINT_IN_TIME_MEMBER;LIQUIDITY_FAIL;RS_FAIL;CONTRACTION_FAIL;SIGNAL_EXTENDED': 13, 'NOT_POINT_IN_TIME_MEMBER;TREND_FAIL;RS_FAIL': 13, 'TREND_FAIL;RS_FAIL;CONTRACTION_FAIL;SIGNAL_EXTENDED': 12, 'TREND_FAIL;SIGNAL_EXTENDED': 11, 'NOT_POINT_IN_TIME_MEMBER;RS_FAIL;SIGNAL_EXTENDED': 10, 'RS_FAIL;SIGNAL_EXTENDED': 8, 'LIQUIDITY_FAIL;CONTRACTION_FAIL': 8, 'LIQUIDITY_FAIL;RS_FAIL': 8, 'LIQUIDITY_FAIL;TREND_FAIL;RS_FAIL;CONTRACTION_FAIL': 6, 'LIQUIDITY_FAIL;CONTRACTION_FAIL;SIGNAL_EXTENDED': 6, 'NOT_POINT_IN_TIME_MEMBER;TREND_FAIL;RS_FAIL;CONTRACTION_FAIL;SIGNAL_EXTENDED': 5, 'LIQUIDITY_FAIL;TREND_FAIL;CONTRACTION_FAIL': 4, 'NOT_POINT_IN_TIME_MEMBER;LIQUIDITY_FAIL;TREND_FAIL;RS_FAIL;CONTRACTION_FAIL;SIGNAL_EXTENDED': 4, 'LIQUIDITY_FAIL': 4, 'LIQUIDITY_FAIL;TREND_FAIL': 3, 'LIQUIDITY_FAIL;TREND_FAIL;RS_FAIL;CONTRACTION_FAIL;SIGNAL_EXTENDED': 2, 'NOT_POINT_IN_TIME_MEMBER;LIQUIDITY_FAIL;TREND_FAIL;RS_FAIL;SIGNAL_EXTENDED': 2, 'NOT_POINT_IN_TIME_MEMBER;TREND_FAIL;RS_FAIL;SIGNAL_EXTENDED': 2, 'LIQUIDITY_FAIL;TREND_FAIL;RS_FAIL': 2, 'NOT_POINT_IN_TIME_MEMBER;LIQUIDITY_FAIL;RS_FAIL;SIGNAL_EXTENDED': 1, 'LIQUIDITY_FAIL;RS_FAIL;CONTRACTION_FAIL;SIGNAL_EXTENDED': 1, 'LIQUIDITY_FAIL;TREND_FAIL;CONTRACTION_FAIL;SIGNAL_EXTENDED': 1, 'LIQUIDITY_FAIL;SIGNAL_EXTENDED': 1, 'LIQUIDITY_FAIL;RS_FAIL;SIGNAL_EXTENDED': 1}.

## 6. Signals and entries
Candidates: 2236; qualified signals: 250; accepted entries: 90; cancellations: 160; incomplete outcomes: 5.

## 7. Setup-quality headline metrics
{'Completed_Trades': 85, 'Winners': 22, 'Losers': 63, 'Win_Rate': 0.25882352941176473, 'Mean_Return': -0.01472288607989003, 'Median_Return': -0.026523606964853046, 'Return_PF': 0.5560693602749592, 'Mean_R': nan, 'Median_R': nan, 'R_PF': nan, 'Median_Holding_Sessions': 10.0}

## 8. Practical headline metrics
{'Completed_Trades': 85, 'Winners': 22, 'Losers': 63, 'Win_Rate': 0.25882352941176473, 'Mean_Return': -0.005562720044752915, 'Median_Return': -0.023307998698581155, 'Return_PF': 0.7736308220130306, 'Mean_R': -0.13217730446106224, 'Median_R': -0.45966042050297157, 'R_PF': 0.728586198391234, 'Median_Holding_Sessions': 10.0}

## 9. Entry-year summary
 Entry_Year  Setup_Completed_Trades  Setup_Winners  Setup_Losers  Setup_Win_Rate  Setup_Mean_Return  Setup_Median_Return  Setup_Return_PF  Setup_Mean_R  Setup_Median_R  Setup_R_PF  Setup_Median_Holding_Sessions  Practical_Completed_Trades  Practical_Winners  Practical_Losers  Practical_Win_Rate  Practical_Mean_Return  Practical_Median_Return  Practical_Return_PF  Practical_Mean_R  Practical_Median_R  Practical_R_PF  Practical_Median_Holding_Sessions
       2023                      14              2            12        0.142857          -0.004986            -0.041386         0.877372           NaN             NaN         NaN                            6.5                          14                  2                12            0.142857               0.005850                -0.029475             1.196158          0.390656           -0.630399        1.675260                                6.5
       2024                      33             10            23        0.303030          -0.007134            -0.021447         0.756339           NaN             NaN         NaN                           12.0                          33                 10                23            0.303030               0.003501                -0.017189             1.176070         -0.115237           -0.399328        0.730654                               11.0
       2025                      23              6            17        0.260870          -0.025895            -0.026379         0.227792           NaN             NaN         NaN                           10.0                          23                  6                17            0.260870              -0.017352                -0.024390             0.314422         -0.372821           -0.473895        0.290482                               10.0
       2026                      15              4            11        0.266667          -0.023376            -0.041516         0.315583           NaN             NaN         NaN                            8.0                          15                  4                11            0.266667              -0.018079                -0.025287             0.373512         -0.288437           -0.590438        0.389849                                8.0

## 10. Top-1/3/5 winner robustness
 Removed_Top_N                                                                              Removed_Entry_IDs                         Removed_Symbols  Remaining_Entry_Count  Setup_Mean_Return  Setup_Return_PF  Practical_Mean_R  Practical_R_PF
             1                                                                          BAJAJ-AUTO-2023-11-15                              BAJAJ-AUTO                     84          -0.020150         0.399588         -0.283134        0.425451
             3                                    BAJAJ-AUTO-2023-11-15;SWSOLAR-2024-01-11;HDFCAMC-2024-01-04              BAJAJ-AUTO;SWSOLAR;HDFCAMC                     82          -0.024776         0.279298         -0.347633        0.311361
             5 BAJAJ-AUTO-2023-11-15;SWSOLAR-2024-01-11;HDFCAMC-2024-01-04;DIXON-2024-03-26;AUBANK-2025-06-02 BAJAJ-AUTO;SWSOLAR;HDFCAMC;DIXON;AUBANK                     80          -0.028222         0.199087         -0.404352        0.218541

## 11. Leave-one-symbol-out robustness
Omitted_Symbol  Remaining_Entry_Count  Setup_Mean_Return  Setup_Return_PF  Practical_Mean_R  Practical_R_PF
        360ONE                     84          -0.014058         0.570354         -0.121846        0.746623
           ACC                     84          -0.014556         0.561793         -0.129144        0.735461
    ADANIENSOL                     84          -0.014985         0.553478         -0.135164        0.725719
          AIIL                     83          -0.013671         0.580095         -0.112078        0.764268
    AJANTPHARM                     83          -0.014074         0.573006         -0.120767        0.750551
     AMBUJACEM                     84          -0.014630         0.560555         -0.128997        0.735683
    ANANDRATHI                     84          -0.014746         0.558594         -0.131591        0.731793
         ARE&M                     84          -0.013877         0.573516         -0.121846        0.746623
    ASAHIINDIA                     84          -0.014399         0.564467         -0.121846        0.746623
          ATUL                     84          -0.014496         0.562809         -0.125669        0.740734
        AUBANK                     84          -0.016212         0.516930         -0.158100        0.679176
    BAJAJ-AUTO                     84          -0.020150         0.399588         -0.283134        0.425451
    BAJFINANCE                     84          -0.014486         0.562984         -0.121846        0.746623
           BEL                     84          -0.014823         0.557325         -0.121846        0.746623
    BLUESTARCO                     84          -0.014410         0.564284         -0.125299        0.741300
      BOSCHLTD                     84          -0.014733         0.558814         -0.130401        0.733572
    CANFINHOME                     84          -0.014644         0.560315         -0.121846        0.746623
          CESC                     84          -0.014202         0.567855         -0.122793        0.745155
    CHENNPETRO                     84          -0.013008         0.589265         -0.121846        0.746623
    COCHINSHIP                     84          -0.015244         0.545778         -0.136569        0.722867
        CPPLUS                     84          -0.014081         0.569951         -0.124096        0.743146
         DIXON                     84          -0.016277         0.514997         -0.155143        0.685177
      EMAMILTD                     84          -0.014581         0.561376         -0.130793        0.732986
    ENGINERSIN                     84          -0.014303         0.566102         -0.125476        0.741029
       ETERNAL                     84          -0.014324         0.565755         -0.126269        0.739818
      EXIDEIND                     84          -0.014597         0.561103         -0.127728        0.737600
           FSL                     84          -0.014754         0.558465         -0.131765        0.731534
    GODREJPROP                     84          -0.013546         0.579407         -0.121846        0.746623
           HAL                     84          -0.014956         0.554349         -0.134874        0.726306
       HCLTECH                     84          -0.015052         0.551494         -0.136466        0.723076
       HDFCAMC                     84          -0.016435         0.510280         -0.162997        0.669239
           HEG                     84          -0.014113         0.569392         -0.121846        0.746623
     HOMEFIRST                     83          -0.014593         0.561349         -0.128657        0.737051
       HYUNDAI                     84          -0.014602         0.561017         -0.129860        0.734385
    ICICIPRULI                     84          -0.014850         0.556862         -0.132927        0.729807
      INDIACEM                     84          -0.014999         0.553055         -0.135244        0.725557
    INDUSTOWER                     84          -0.014985         0.553475         -0.135377        0.725287
     INTELLECT                     84          -0.013807         0.574756         -0.121846        0.746623
       J&KBANK                     84          -0.015402         0.541047         -0.140396        0.715102
          JBMA                     84          -0.014831         0.557189         -0.121846        0.746623
      JKCEMENT                     84          -0.014584         0.561322         -0.128955        0.735746
           JSL                     84          -0.013896         0.573183         -0.121846        0.746623
      JSWSTEEL                     84          -0.014329         0.565666         -0.121846        0.746623
        KAYNES                     84          -0.016056         0.521566         -0.146346        0.703027
          KPIL                     84          -0.014541         0.562057         -0.128496        0.736440
    LALPATHLAB                     83          -0.015394         0.543272         -0.141417        0.713262
      LLOYDSME                     84          -0.014363         0.565076         -0.126802        0.739007
            LT                     84          -0.015099         0.550077         -0.139659        0.716596
     MINDACORP                     83          -0.014849         0.553526         -0.131106        0.730612
     NAM-INDIA                     84          -0.014608         0.560923         -0.129326        0.735188
    NATCOPHARM                     84          -0.014641         0.560369         -0.130221        0.733842
           NCC                     84          -0.013817         0.574575         -0.121795        0.746703
          OFSS                     84          -0.014397         0.564494         -0.127898        0.737343
       PAGEIND                     84          -0.014870         0.556530         -0.133174        0.729440
           PNB                     83          -0.013547         0.582317         -0.114464        0.760451
       POLYCAB                     84          -0.015039         0.551886         -0.136487        0.723034
      PRESTIGE                     83          -0.013457         0.583941         -0.117847        0.755105
         PTCIL                     84          -0.014478         0.563118         -0.128109        0.737024
     RATNAMANI                     84          -0.014708         0.559233         -0.130839        0.732917
      SAREGAMA                     84          -0.013984         0.571646         -0.121846        0.746623
       SBILIFE                     84          -0.014692         0.559498         -0.128753        0.736051
    SCHAEFFLER                     84          -0.014076         0.570026         -0.123418        0.744190
    SHRIRAMFIN                     84          -0.014401         0.564425         -0.125536        0.740937
     SHYAMMETL                     84          -0.015429         0.540248         -0.140539        0.714812
     SOLARINDS                     83          -0.015718         0.529555         -0.149798        0.694829
      SUMICHEM                     84          -0.014447         0.563654         -0.128599        0.736283
    SUNDARMFIN                     84          -0.014365         0.565042         -0.126223        0.739889
         SUNTV                     84          -0.015592         0.535388         -0.145899        0.703936
       SWSOLAR                     84          -0.017398         0.481569         -0.160728        0.673844
     TATAPOWER                     84          -0.014271         0.566662         -0.123529        0.744020
      TEJASNET                     84          -0.014090         0.569787         -0.126722        0.739129
         TITAN                     84          -0.015093         0.550275         -0.139540        0.716839
    TORNTPHARM                     84          -0.014621         0.560705         -0.126772        0.739053
    TORNTPOWER                     84          -0.014518         0.562445         -0.127048        0.738632
         TRENT                     84          -0.014694         0.559481         -0.129774        0.734513
           VTL                     84          -0.014404         0.564381         -0.126396        0.739626
    WELSPUNLIV                     84          -0.014675         0.559793         -0.131328        0.732186
Full CSV: `v2_leave_one_symbol_out.csv`.

## 12. Breadth diagnostic summary
         Regime  Setup_Completed_Trades  Setup_Winners  Setup_Losers  Setup_Win_Rate  Setup_Mean_Return  Setup_Median_Return  Setup_Return_PF  Setup_Mean_R  Setup_Median_R  Setup_R_PF  Setup_Median_Holding_Sessions  Practical_Completed_Trades  Practical_Winners  Practical_Losers  Practical_Win_Rate  Practical_Mean_Return  Practical_Median_Return  Practical_Return_PF  Practical_Mean_R  Practical_Median_R  Practical_R_PF  Practical_Median_Holding_Sessions
        HOSTILE                       6              2             4        0.333333          -0.020865            -0.030500         0.301913           NaN             NaN         NaN                            8.0                           6                  2                 4            0.333333              -0.008700                -0.019225             0.509127         -0.372117           -0.510347        0.260865                                7.5
         NORMAL                      39             14            25        0.358974           0.001686            -0.018750         1.062374           NaN             NaN         NaN                           11.0                          39                 14                25            0.358974               0.005165                -0.017276             1.219250          0.205196           -0.419785        1.501156                               10.0
STRONG_MOMENTUM                      40              6            34        0.150000          -0.029801            -0.032858         0.248023           NaN             NaN         NaN                           10.0                          40                  6                34            0.150000              -0.015552                -0.025691             0.415124         -0.425125           -0.511336        0.241037                                9.5

## 13. Overlap diagnostic summary
 Total_Accepted_Entries  Entries_With_Another_Open_Same_Symbol_Trade  Max_Simultaneous_Signal_Level_Trades  Max_Same_Day_Entries
                     85                                            1                                     7                     3

## 14. Precommitted gates
                       Gate  Passed                 Value                Status
           COMPLETED_TRADES   False                    85                  FAIL
          SETUP_MEAN_RETURN   False             -0.014723                  FAIL
            SETUP_RETURN_PF   False              0.556069                  FAIL
           PRACTICAL_MEAN_R   False             -0.132177                  FAIL
             PRACTICAL_R_PF   False              0.728586                  FAIL
        TEMPORAL_ROBUSTNESS   False                     0                  FAIL
TOP_FIVE_OUTLIER_ROBUSTNESS   False                  top5                  FAIL
       LEAVE_ONE_SYMBOL_OUT   False                    77                  FAIL
    POINT_IN_TIME_INTEGRITY    True                     0                  PASS
               FINAL_STATUS   False INSUFFICIENT_EVIDENCE INSUFFICIENT_EVIDENCE

## 15. Final status: INSUFFICIENT_EVIDENCE

This report supplies locked evidence only. It does not tune Strategy V2 or prescribe a follow-up change. Portfolio Advisor retains the strategy decision.

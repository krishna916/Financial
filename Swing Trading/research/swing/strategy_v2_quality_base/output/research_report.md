# Strategy V2 Quality-Base Breakout Validation

## 1. Locked hypothesis
Strategy V2 validates RS leader → pivot → quality base → volatility contraction → breakout → controlled next-session entry.
Design spec: `Swing Trading/docs/superpowers/specs/2026-08-26-strategy-v2-quality-base-breakout-design.md`.

## 2. Data and timing
Signal window: 2023-08-01 through 2026-08-25. Yahoo Finance daily OHLCV uses `auto_adjust=True`; indicators use standard Wilder ATR14.
Point-in-time membership: `market_breadth/config/nifty500_membership.csv`. Breadth is diagnostic-only and joined from a strictly prior date.

## 3. Download and audit counts
Usable symbols: 652; audited symbols: 662.
RS audit dates: 760; unsafe RS dates: 0.

## 4. RS coverage
Minimum coverage: 0.8942115768463074; median: 0.9801192842942346.

## 5. Base events and rejections
Base events: {'SEEDED': 25509, 'FAILED_PROBE': 22120, 'TOO_SHORT_BREAKOUT': 14908, 'DEPTH_INVALIDATED': 5735, 'BREAKOUT_CANDIDATE': 3317, 'EXPIRED': 1306}.
Signal rejection reasons: {'CONTRACTION_FAIL': 751, nan: 251, 'RS_FAIL;CONTRACTION_FAIL': 174, 'NOT_POINT_IN_TIME_MEMBER;RS_FAIL;CONTRACTION_FAIL': 132, 'CONTRACTION_FAIL;SIGNAL_EXTENDED': 129, 'TREND_FAIL;RS_FAIL;CONTRACTION_FAIL': 104, 'RS_FAIL': 96, 'TREND_FAIL;CONTRACTION_FAIL': 85, 'NOT_POINT_IN_TIME_MEMBER;LIQUIDITY_FAIL;RS_FAIL;CONTRACTION_FAIL': 58, 'SIGNAL_EXTENDED': 51, 'NOT_POINT_IN_TIME_MEMBER;RS_FAIL': 50, 'TREND_FAIL': 40, 'TREND_FAIL;RS_FAIL': 39, 'NOT_POINT_IN_TIME_MEMBER;RS_FAIL;CONTRACTION_FAIL;SIGNAL_EXTENDED': 36, 'NOT_POINT_IN_TIME_MEMBER;LIQUIDITY_FAIL;TREND_FAIL;RS_FAIL;CONTRACTION_FAIL': 33, 'TREND_FAIL;CONTRACTION_FAIL;SIGNAL_EXTENDED': 24, 'NOT_POINT_IN_TIME_MEMBER;TREND_FAIL;RS_FAIL;CONTRACTION_FAIL': 20, 'NOT_POINT_IN_TIME_MEMBER;LIQUIDITY_FAIL;RS_FAIL': 16, 'RS_FAIL;CONTRACTION_FAIL;SIGNAL_EXTENDED': 16, 'LIQUIDITY_FAIL;RS_FAIL;CONTRACTION_FAIL': 15, 'NOT_POINT_IN_TIME_MEMBER;LIQUIDITY_FAIL;TREND_FAIL;RS_FAIL': 15, 'NOT_POINT_IN_TIME_MEMBER;LIQUIDITY_FAIL;RS_FAIL;CONTRACTION_FAIL;SIGNAL_EXTENDED': 13, 'NOT_POINT_IN_TIME_MEMBER;TREND_FAIL;RS_FAIL': 13, 'TREND_FAIL;RS_FAIL;CONTRACTION_FAIL;SIGNAL_EXTENDED': 12, 'TREND_FAIL;SIGNAL_EXTENDED': 11, 'NOT_POINT_IN_TIME_MEMBER;RS_FAIL;SIGNAL_EXTENDED': 10, 'RS_FAIL;SIGNAL_EXTENDED': 9, 'LIQUIDITY_FAIL;CONTRACTION_FAIL': 9, 'LIQUIDITY_FAIL;RS_FAIL': 8, 'LIQUIDITY_FAIL;TREND_FAIL;RS_FAIL;CONTRACTION_FAIL': 6, 'LIQUIDITY_FAIL;CONTRACTION_FAIL;SIGNAL_EXTENDED': 6, 'LIQUIDITY_FAIL': 5, 'NOT_POINT_IN_TIME_MEMBER;TREND_FAIL;RS_FAIL;CONTRACTION_FAIL;SIGNAL_EXTENDED': 5, 'LIQUIDITY_FAIL;TREND_FAIL;CONTRACTION_FAIL': 4, 'NOT_POINT_IN_TIME_MEMBER;LIQUIDITY_FAIL;TREND_FAIL;RS_FAIL;CONTRACTION_FAIL;SIGNAL_EXTENDED': 4, 'LIQUIDITY_FAIL;TREND_FAIL': 3, 'LIQUIDITY_FAIL;TREND_FAIL;RS_FAIL;CONTRACTION_FAIL;SIGNAL_EXTENDED': 2, 'NOT_POINT_IN_TIME_MEMBER;LIQUIDITY_FAIL;TREND_FAIL;RS_FAIL;SIGNAL_EXTENDED': 2, 'NOT_POINT_IN_TIME_MEMBER;TREND_FAIL;RS_FAIL;SIGNAL_EXTENDED': 2, 'LIQUIDITY_FAIL;TREND_FAIL;RS_FAIL': 2, 'NOT_POINT_IN_TIME_MEMBER;LIQUIDITY_FAIL;RS_FAIL;SIGNAL_EXTENDED': 1, 'LIQUIDITY_FAIL;RS_FAIL;CONTRACTION_FAIL;SIGNAL_EXTENDED': 1, 'TREND_FAIL;RS_FAIL;SIGNAL_EXTENDED': 1, 'LIQUIDITY_FAIL;TREND_FAIL;CONTRACTION_FAIL;SIGNAL_EXTENDED': 1, 'LIQUIDITY_FAIL;SIGNAL_EXTENDED': 1, 'LIQUIDITY_FAIL;RS_FAIL;SIGNAL_EXTENDED': 1}.

## 6. Signals and entries
Candidates: 2267; qualified signals: 251; accepted entries: 89; cancellations: 162; incomplete outcomes: 5.

## 7. Setup-quality headline metrics
{'Completed_Trades': 84, 'Winners': 21, 'Losers': 63, 'Win_Rate': 0.25, 'Mean_Return': -0.016382310066712875, 'Median_Return': -0.027684076246814508, 'Return_PF': 0.5165447045437258, 'Mean_R': nan, 'Median_R': nan, 'R_PF': nan, 'Median_Holding_Sessions': 10.0}

## 8. Practical headline metrics
{'Completed_Trades': 84, 'Winners': 21, 'Losers': 63, 'Win_Rate': 0.25, 'Mean_Return': -0.006983896351925521, 'Median_Return': -0.02379122831399461, 'Return_PF': 0.7213490036231452, 'Mean_R': -0.13900574286186956, 'Median_R': -0.4567159109611285, 'R_PF': 0.7136572356152061, 'Median_Holding_Sessions': 10.0}

## 9. Entry-year summary
 Entry_Year  Setup_Completed_Trades  Setup_Winners  Setup_Losers  Setup_Win_Rate  Setup_Mean_Return  Setup_Median_Return  Setup_Return_PF  Setup_Mean_R  Setup_Median_R  Setup_R_PF  Setup_Median_Holding_Sessions  Practical_Completed_Trades  Practical_Winners  Practical_Losers  Practical_Win_Rate  Practical_Mean_Return  Practical_Median_Return  Practical_Return_PF  Practical_Mean_R  Practical_Median_R  Practical_R_PF  Practical_Median_Holding_Sessions
       2023                      15              2            13        0.133333          -0.006904            -0.041040         0.828256           NaN             NaN         NaN                            7.0                          15                  2                13            0.133333               0.003210                -0.031956             1.106686          0.339054           -0.628466        1.599547                                7.0
       2024                      31              9            22        0.290323          -0.010527            -0.022556         0.660010           NaN             NaN         NaN                           12.0                          31                  9                22            0.290323               0.001145                -0.017189             1.055528         -0.124544           -0.399329        0.705699                               11.0
       2025                      23              6            17        0.260870          -0.025895            -0.026379         0.227792           NaN             NaN         NaN                           10.0                          23                  6                17            0.260870              -0.017352                -0.024390             0.314422         -0.372821           -0.473895        0.290482                               10.0
       2026                      15              4            11        0.266667          -0.023376            -0.041516         0.315583           NaN             NaN         NaN                            8.0                          15                  4                11            0.266667              -0.018079                -0.025287             0.373512         -0.288437           -0.590438        0.389849                                8.0

## 10. Top-1/3/5 winner robustness
 Removed_Top_N                                                                              Removed_Entry_IDs                         Removed_Symbols  Remaining_Entry_Count  Setup_Mean_Return  Setup_Return_PF  Practical_Mean_R  Practical_R_PF
             1                                                                          BAJAJ-AUTO-2023-11-15                              BAJAJ-AUTO                     83          -0.021894         0.361570         -0.291863        0.405938
             3                                    BAJAJ-AUTO-2023-11-15;SWSOLAR-2024-01-11;HDFCAMC-2024-01-04              BAJAJ-AUTO;SWSOLAR;HDFCAMC                     81          -0.026621         0.242438         -0.357375        0.290123
             5 BAJAJ-AUTO-2023-11-15;SWSOLAR-2024-01-11;HDFCAMC-2024-01-04;DIXON-2024-03-26;AUBANK-2025-06-02 BAJAJ-AUTO;SWSOLAR;HDFCAMC;DIXON;AUBANK                     79          -0.030158         0.163000         -0.415058        0.195900

## 11. Leave-one-symbol-out robustness
Omitted_Symbol  Remaining_Entry_Count  Setup_Mean_Return  Setup_Return_PF  Practical_Mean_R  Practical_R_PF
        360ONE                     83          -0.015729         0.529683         -0.128632        0.731598
           ACC                     83          -0.016234         0.521810         -0.136018        0.720494
    ADANIENSOL                     83          -0.016668         0.513978         -0.142110        0.710747
          AIIL                     82          -0.015358         0.538638         -0.118828        0.749162
    AJANTPHARM                     82          -0.015766         0.532121         -0.127623        0.735507
     AMBUJACEM                     83          -0.016308         0.520671         -0.135869        0.720715
    ANANDRATHI                     83          -0.016426         0.518867         -0.138495        0.716847
         ARE&M                     83          -0.015546         0.532590         -0.128632        0.731598
    ASAHIINDIA                     83          -0.016074         0.524269         -0.128632        0.731598
          ATUL                     83          -0.016173         0.522745         -0.132502        0.725739
        AUBANK                     83          -0.017909         0.477783         -0.165323        0.663500
    BAJAJ-AUTO                     83          -0.021894         0.361570         -0.291863        0.405938
    BAJFINANCE                     83          -0.016163         0.522905         -0.128632        0.731598
    BLUESTARCO                     83          -0.016085         0.524101         -0.132127        0.726303
      BOSCHLTD                     83          -0.016413         0.519069         -0.137291        0.718616
    CANFINHOME                     83          -0.016322         0.520450         -0.128632        0.731598
          CESC                     83          -0.015875         0.527385         -0.129591        0.730138
    CHENNPETRO                     83          -0.014666         0.547066         -0.128632        0.731598
    COCHINSHIP                     83          -0.016929         0.506352         -0.143533        0.707852
        CPPLUS                     83          -0.015752         0.529313         -0.130909        0.728139
         DIXON                     83          -0.017975         0.475868         -0.162330        0.669591
      EMAMILTD                     83          -0.016259         0.521426         -0.137687        0.718033
    ENGINERSIN                     83          -0.015978         0.525773         -0.132306        0.726033
       ETERNAL                     83          -0.015998         0.525454         -0.133109        0.724828
      EXIDEIND                     83          -0.016275         0.521175         -0.134585        0.722622
           FSL                     83          -0.016434         0.518748         -0.138671        0.716588
    GODREJPROP                     83          -0.015212         0.538006         -0.128632        0.731598
           HAL                     83          -0.016638         0.514841         -0.141817        0.711343
       HCLTECH                     83          -0.016735         0.512013         -0.143428        0.708064
       HDFCAMC                     83          -0.018135         0.471196         -0.170279        0.653413
           HEG                     83          -0.015785         0.528798         -0.128632        0.731598
     HOMEFIRST                     82          -0.016292         0.520954         -0.135609        0.721960
       HYUNDAI                     83          -0.016280         0.521096         -0.136742        0.719424
    ICICIPRULI                     83          -0.016531         0.517274         -0.139846        0.714871
      INDIACEM                     83          -0.016682         0.513559         -0.142191        0.710582
    INDUSTOWER                     83          -0.016668         0.513975         -0.142326        0.710308
     INTELLECT                     83          -0.015475         0.533730         -0.128632        0.731598
       J&KBANK                     83          -0.017090         0.501667         -0.147406        0.699969
          JBMA                     83          -0.016511         0.517575         -0.128632        0.731598
      JKCEMENT                     83          -0.016262         0.521376         -0.135827        0.720778
           JSL                     83          -0.015566         0.532284         -0.128632        0.731598
      JSWSTEEL                     83          -0.016003         0.525372         -0.128632        0.731598
          KPIL                     83          -0.016218         0.522053         -0.135362        0.721467
    LALPATHLAB                     82          -0.017102         0.503572         -0.148525        0.697928
      LLOYDSME                     83          -0.016038         0.524829         -0.133648        0.724021
            LT                     83          -0.016783         0.510610         -0.146660        0.701486
     MINDACORP                     82          -0.016551         0.513197         -0.138088        0.715340
     NAM-INDIA                     83          -0.016286         0.521009         -0.136202        0.720222
    NATCOPHARM                     83          -0.016319         0.520500         -0.137108        0.718884
           NCC                     83          -0.015486         0.533564         -0.128580        0.731678
          OFSS                     83          -0.016073         0.524294         -0.134757        0.722366
       PAGEIND                     83          -0.016552         0.516969         -0.140097        0.714506
           PNB                     82          -0.015232         0.540681         -0.121243        0.745362
       POLYCAB                     83          -0.016722         0.512401         -0.143449        0.708021
      PRESTIGE                     82          -0.015141         0.542174         -0.124667        0.740040
         PTCIL                     83          -0.016155         0.523029         -0.134971        0.722048
     RATNAMANI                     83          -0.016388         0.519455         -0.137733        0.717964
      SAREGAMA                     83          -0.015654         0.530871         -0.128632        0.731598
       SBILIFE                     83          -0.016372         0.519699         -0.135623        0.721080
    SCHAEFFLER                     83          -0.015748         0.529382         -0.130224        0.729177
    SHRIRAMFIN                     83          -0.016077         0.524231         -0.132367        0.725941
     SHYAMMETL                     83          -0.017117         0.500875         -0.147550        0.699675
     SOLARINDS                     82          -0.017430         0.489643         -0.157007        0.679138
      SUMICHEM                     83          -0.016123         0.523522         -0.135467        0.721312
    SUNDARMFIN                     83          -0.016040         0.524798         -0.133062        0.724898
         SUNTV                     83          -0.017282         0.496062         -0.152974        0.688634
       SWSOLAR                     83          -0.019110         0.442762         -0.167982        0.658087
     TATAPOWER                     83          -0.015945         0.526288         -0.130335        0.729008
      TEJASNET                     83          -0.015762         0.529162         -0.133567        0.724142
         TITAN                     83          -0.016776         0.510806         -0.146539        0.701733
    TORNTPHARM                     83          -0.016299         0.520809         -0.133617        0.724067
    TORNTPOWER                     83          -0.016195         0.522410         -0.133897        0.723649
         TRENT                     83          -0.016373         0.519683         -0.136656        0.719552
           VTL                     83          -0.016079         0.524190         -0.133237        0.724637
    WELSPUNLIV                     83          -0.016354         0.519970         -0.138229        0.717237
    ZENSARTECH                     83          -0.016173         0.522744         -0.136062        0.720430
Full CSV: `v2_leave_one_symbol_out.csv`.

## 12. Breadth diagnostic summary
         Regime  Setup_Completed_Trades  Setup_Winners  Setup_Losers  Setup_Win_Rate  Setup_Mean_Return  Setup_Median_Return  Setup_Return_PF  Setup_Mean_R  Setup_Median_R  Setup_R_PF  Setup_Median_Holding_Sessions  Practical_Completed_Trades  Practical_Winners  Practical_Losers  Practical_Win_Rate  Practical_Mean_Return  Practical_Median_Return  Practical_Return_PF  Practical_Mean_R  Practical_Median_R  Practical_R_PF  Practical_Median_Holding_Sessions
        HOSTILE                       6              2             4        0.333333          -0.020865            -0.030500         0.301913           NaN             NaN         NaN                            8.0                           6                  2                 4            0.333333              -0.008700                -0.019225             0.509127         -0.372117           -0.510347        0.260865                                7.5
         NORMAL                      38             13            25        0.342105          -0.000829            -0.020055         0.970134           NaN             NaN         NaN                           10.5                          38                 13                25            0.342105               0.002742                -0.018013             1.113390          0.182753           -0.446840        1.434898                                9.5
STRONG_MOMENTUM                      40              6            34        0.150000          -0.030486            -0.033758         0.243808           NaN             NaN         NaN                           10.5                          40                  6                34            0.150000              -0.015966                -0.026585             0.408763         -0.409710           -0.456716        0.247858                               10.5

## 13. Overlap diagnostic summary
 Total_Accepted_Entries  Entries_With_Another_Open_Same_Symbol_Trade  Max_Simultaneous_Signal_Level_Trades  Max_Same_Day_Entries
                     89                                            2                                     7                     3

## 14. Precommitted gates
                       Gate  Passed                 Value                Status
           COMPLETED_TRADES   False                    84                  FAIL
          SETUP_MEAN_RETURN   False             -0.016382                  FAIL
            SETUP_RETURN_PF   False              0.516545                  FAIL
           PRACTICAL_MEAN_R   False             -0.139006                  FAIL
             PRACTICAL_R_PF   False              0.713657                  FAIL
        TEMPORAL_ROBUSTNESS   False                     0                  FAIL
TOP_FIVE_OUTLIER_ROBUSTNESS   False                  top5                  FAIL
       LEAVE_ONE_SYMBOL_OUT   False                    76                  FAIL
    POINT_IN_TIME_INTEGRITY    True                     0                  PASS
               FINAL_STATUS   False INSUFFICIENT_EVIDENCE INSUFFICIENT_EVIDENCE

## 15. Final status: INSUFFICIENT_EVIDENCE

This report supplies locked evidence only. It does not tune Strategy V2 or prescribe a follow-up change. Portfolio Advisor retains the strategy decision.

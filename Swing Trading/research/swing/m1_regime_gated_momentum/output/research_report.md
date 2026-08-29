# M1 Regime-Gated Momentum Resumption Validation

## 1. Frozen M1 hypothesis and rules
M1 partitions the closed V3 opportunity set using only signal-date PIT breadth coverage >= 80%, Nifty 500 Close > SMA200, Nifty 500 SMA50 > SMA200, and Pct_Above_SMA50 >= 50%. Disabled signals remain cash; V3 setup, entry, cancellation, exits, and gross outcomes remain frozen.
Friction is frozen at 0.40% base, 0.60% stress, and 0.80% severe diagnostic. No post-result threshold or rescue changes are permitted.

## 2. Source-artifact and PIT coverage/integrity
                             Metric Value  Pass
               V3_QUALIFIED_SIGNALS  1554  True
                V3_ACCEPTED_ENTRIES  1501  True
               V3_CANCELLED_ENTRIES    53  True
                V3_COMPLETED_PAIRED  1465  True
         V3_POINT_IN_TIME_INTEGRITY  True  True
                BREADTH_SOURCE_ROWS   751  True
                  INDEX_SOURCE_ROWS   942  True
           MEMBERSHIP_INTERVAL_ROWS 20562  True
QUALIFIED_SIGNALS_WITH_EXACT_REGIME  1554  True
               INTEGRITY_VIOLATIONS     0  True
                FINAL_FORMAL_STATUS  FAIL False
    FINAL_REQUIRED_EVIDENCE_PACKAGE  True  True

## 3. M1 regime distribution
        M1_Regime  Sessions
MOMENTUM_DISABLED       418
 MOMENTUM_ENABLED       333

## 4. Signal/cohort accounting
        M1_Regime V3_Entry_Status  Signals
MOMENTUM_DISABLED        ACCEPTED      649
MOMENTUM_DISABLED       CANCELLED       21
 MOMENTUM_ENABLED        ACCEPTED      852
 MOMENTUM_ENABLED       CANCELLED       32

## 5. Base setup-quality results
{'Completed_Trades': 825.0, 'Base_Mean_Net_Return': -0.0003787284312588728, 'Base_Median_Net_Return': -0.0230716238672873, 'Base_Win_Rate': 0.2824242424242424, 'Base_Net_Return_PF': 0.9870242144986462, 'Stress_Mean_Net_Return': -0.002378728431258873, 'Stress_Net_Return_PF': 0.9223531024977433, 'Severe_Mean_Net_Return': -0.0043787284312588725, 'Severe_Net_Return_PF': 0.8636258616131753}

## 6. Base practical results
{'Completed_Trades': 825.0, 'Base_Mean_Net_R': -0.014416265079849395, 'Base_Median_Net_R': -0.5250083965439643, 'Base_Win_Rate': 0.25696969696969696, 'Base_Net_R_PF': 0.9750194191377326, 'Stress_Mean_Net_R': -0.05784558020909775, 'Stress_Net_R_PF': 0.9051441822984327, 'Severe_Mean_Net_R': -0.10127489533834612, 'Severe_Net_R_PF': 0.8425280697989049, 'Gross_Mean_R': 0.0724423651786473, 'Gross_R_PF': 1.1413075344042347, 'Median_Holding_Sessions': 6.0}

## 7. Stress/severe friction results
{'Stress_Mean_Net_R': -0.05784558020909775, 'Stress_Net_R_PF': 0.9051441822984327, 'Severe_Mean_Net_R': -0.10127489533834612, 'Severe_Net_R_PF': 0.8425280697989049}

## 8. Enabled-vs-disabled regime comparison
 Enabled_Completed  Disabled_Completed  Enabled_Base_Mean_Net_R  Disabled_Base_Mean_Net_R  Enabled_Base_R_PF  Disabled_Base_R_PF  Enabled_Beats_Disabled_Mean  Enabled_Beats_Disabled_R_PF
             825.0               640.0                -0.014416                 -0.186606           0.975019            0.683379                         True                         True

## 9. Temporal halves
     Period  Completed_Trades  Mean_Base_Net_R  Base_R_PF  Winners  Win_Rate
 FIRST_HALF               681         0.053281   1.095070      186  0.273128
SECOND_HALF               144        -0.334567   0.489918       26  0.180556

## 10. Calendar-year diagnostics
 Signal_Year  Completed_Trades  Mean_Base_Net_R  Base_R_PF  Winners  Win_Rate
        2023               214         0.527830   2.105306       75  0.350467
        2024               462        -0.155202   0.738780      111  0.240260
        2025               118        -0.272157   0.572837       25  0.211864
        2026                31        -0.678429   0.132296        1  0.032258

## 11. Top-five-winner robustness
                                                                             Removed_Entry_IDs  Remaining_Completed  Remaining_Mean_Base_Net_R  Remaining_Base_R_PF
IOC-2023-11-23;HEROMOTOCO-2023-12-12;TATAINVEST-2024-01-18;IOC-2023-12-13;SHYAMMETL-2023-12-14                  820                  -0.088127             0.848219

## 12. Leave-one-symbol-out robustness
Omitted_Symbol  Remaining_Completed  Mean_Base_Net_R  Base_R_PF
        360ONE                  821        -0.014801   0.974409
       3MINDIA                  824        -0.013948   0.975840
         AAVAS                  824        -0.013136   0.977214
           ABB                  823        -0.012723   0.977941
     ABCAPITAL                  823        -0.015479   0.973216
         ABFRL                  824        -0.014323   0.975206
         ABREL                  820        -0.013675   0.976366
           ACC                  824        -0.013878   0.975958
           ACE                  824        -0.013116   0.977248
      ADANIENT                  823        -0.013187   0.977152
    ADANIGREEN                  823        -0.013289   0.976982
    ADANIPORTS                  824        -0.014955   0.974116
    ADANIPOWER                  820        -0.014306   0.975154
      AEGISLOG                  823        -0.012759   0.977881
         AFFLE                  823        -0.012886   0.977666
          AIIL                  824        -0.013499   0.976600
    AJANTPHARM                  824        -0.012897   0.977620
         ALKEM                  824        -0.015188   0.973714
    ALKYLAMINE                  824        -0.013869   0.975974
         AMBER                  823        -0.012918   0.977611
     AMBUJACEM                  824        -0.015047   0.973958
    ANANDRATHI                  824        -0.013123   0.977236
      ANANTRAJ                  824        -0.014318   0.975215
      ANGELONE                  822        -0.015964   0.972375
      APARINDS                  823        -0.012290   0.978675
     APLAPOLLO                  823        -0.012207   0.978816
        APLLTD                  823        -0.011795   0.979517
    APOLLOTYRE                  823        -0.013046   0.977394
         ARE&M                  823        -0.015912   0.972430
    ASAHIINDIA                  823        -0.011724   0.979638
      ASHOKLEY                  822        -0.015008   0.974088
       ASTERDM                  823        -0.011799   0.979511
        AUBANK                  824        -0.013078   0.977313
    AUROPHARMA                  821        -0.011965   0.979278
    AVANTIFEED                  822        -0.011650   0.979788
    BAJAJ-AUTO                  821        -0.036280   0.937285
    BAJAJFINSV                  824        -0.014186   0.975438
    BAJAJHLDNG                  823        -0.011700   0.979679
    BAJFINANCE                  823        -0.011514   0.979995
    BALRAMCHIN                  823        -0.012776   0.977852
    BANKBARODA                  823        -0.015745   0.972717
     BANKINDIA                  824        -0.014228   0.975366
          BBTC                  823        -0.012287   0.978681
           BDL                  823        -0.013858   0.976021
           BEL                  823        -0.013350   0.976878
          BEML                  819        -0.013019   0.977458
    BHARATFORG                  824        -0.018325   0.968284
    BHARTIARTL                  824        -0.013070   0.977326
          BHEL                  822        -0.021064   0.963633
        BIKAJI                  820        -0.012415   0.978486
        BIOCON                  822        -0.011671   0.979752
           BLS                  824        -0.018323   0.968288
    BLUESTARCO                  821        -0.014478   0.975014
      BOSCHLTD                  823        -0.013390   0.976811
          BPCL                  821        -0.013120   0.977256
       BRIGADE                  823        -0.015641   0.972957
           BSE                  823        -0.014490   0.974897
         BSOFT                  822        -0.017321   0.970071
          CAMS                  823        -0.012267   0.978714
         CANBK                  819        -0.030913   0.946712
    CAPLIPOINT                  821        -0.013383   0.976833
    CARBORUNIV                  823        -0.013164   0.977195
    CASTROLIND                  821        -0.010585   0.981621
          CDSL                  824        -0.013145   0.977200
     CENTRALBK                  824        -0.014019   0.975719
    CENTURYPLY                  824        -0.013095   0.977284
          CERA                  824        -0.015797   0.972660
          CESC                  823        -0.024173   0.958130
       CGPOWER                  824        -0.013138   0.977212
        CHALET                  823        -0.011774   0.979553
    CHAMBLFERT                  823        -0.011826   0.979465
    CHENNPETRO                  824        -0.013135   0.977217
      CHOLAFIN                  824        -0.013219   0.977074
    CHOLAHLDNG                  823        -0.013710   0.976270
      CIEINDIA                  824        -0.013106   0.977265
         CLEAN                  824        -0.013448   0.976686
     COALINDIA                  824        -0.015356   0.973424
    COCHINSHIP                  819        -0.015475   0.973223
       COFORGE                  824        -0.013416   0.976740
       COHANCE                  822        -0.020179   0.965049
        COLPAL                  822        -0.012523   0.978306
        CONCOR                  823        -0.013127   0.977256
    CONCORDBIO                  824        -0.013148   0.977193
    COROMANDEL                  824        -0.013815   0.976065
     CRAFTSMAN                  819        -0.013221   0.977164
        CRISIL                  824        -0.013681   0.976291
      CROMPTON                  824        -0.013801   0.976088
           CUB                  824        -0.020779   0.964037
    CUMMINSIND                  822        -0.017969   0.968883
        CYIENT                  824        -0.016603   0.971266
    DATAPATTNS                  823        -0.013188   0.977153
    DEEPAKFERT                  824        -0.020562   0.964413
     DELHIVERY                  823        -0.012684   0.978007
      DIVISLAB                  824        -0.013095   0.977284
         DIXON                  819        -0.009506   0.983505
           DLF                  823        -0.011802   0.979505
         DMART                  823        -0.011697   0.979683
        ECLERX                  823        -0.012431   0.978437
     EICHERMOT                  824        -0.013906   0.975911
      EIDPARRY                  823        -0.014438   0.975025
       EIHOTEL                  824        -0.013849   0.976007
        ELECON                  824        -0.013125   0.977232
     ELGIEQUIP                  824        -0.013574   0.976473
      EMAMILTD                  822        -0.014719   0.974558
     ENDURANCE                  822        -0.013000   0.977499
    ENGINERSIN                  823        -0.012818   0.977780
          ERIS                  824        -0.013672   0.976307
       ESCORTS                  821        -0.016795   0.970825
       ETERNAL                  816        -0.011790   0.979611
      EXIDEIND                  820        -0.008736   0.984803
          FACT                  821        -0.010666   0.981486
     FINCABLES                  823        -0.012187   0.978850
       FINPIPE                  824        -0.013936   0.975859
    FLUOROCHEM                  824        -0.013145   0.977198
        FORTIS                  823        -0.016113   0.972082
           FSL                  822        -0.010542   0.981675
          GAIL                  822        -0.014528   0.974854
        GESHIP                  823        -0.014361   0.975152
         GICRE                  822        -0.012255   0.978761
      GILLETTE                  823        -0.012760   0.977878
         GLAXO                  823        -0.012764   0.977872
      GLENMARK                  824        -0.013067   0.977331
       GMDCLTD                  824        -0.016254   0.971869
    GMRAIRPORT                  824        -0.013873   0.975966
    GODFRYPHLP                  822        -0.016291   0.971755
      GODREJCP                  824        -0.013072   0.977322
     GODREJIND                  823        -0.011823   0.979469
    GODREJPROP                  817        -0.011852   0.979525
          GPPL                  823        -0.015876   0.972495
      GRANULES                  821        -0.009939   0.982725
      GRAPHITE                  823        -0.013874   0.975991
        GRASIM                  823        -0.012668   0.978034
     GRINDWELL                  824        -0.013107   0.977264
          GRSE                  823        -0.011828   0.979462
          GSFC                  824        -0.014371   0.975126
         GVT&D                  824        -0.013679   0.976295
           HAL                  823        -0.015515   0.973169
       HDFCAMC                  821        -0.025509   0.955911
      HDFCLIFE                  824        -0.012890   0.977631
           HEG                  822        -0.011598   0.979877
    HEROMOTOCO                  822        -0.027404   0.952544
          HFCL                  821        -0.012025   0.979174
      HINDALCO                  823        -0.013335   0.976895
    HINDCOPPER                  820        -0.018347   0.968160
     HINDPETRO                  820        -0.012184   0.978839
    HINDUNILVR                  824        -0.013069   0.977328
      HINDZINC                  824        -0.013126   0.977231
        HONAUT                  824        -0.014027   0.975706
          HSCL                  822        -0.011793   0.979545
         HUDCO                  821        -0.024217   0.958073
     ICICIBANK                  824        -0.012793   0.977796
    ICICIPRULI                  824        -0.012931   0.977562
          IDEA                  821        -0.010835   0.981198
    IDFCFIRSTB                  823        -0.012447   0.978409
           IEX                  824        -0.013091   0.977290
          IIFL                  824        -0.016120   0.972101
      INDIACEM                  823        -0.012880   0.977675
       INDIANB                  822        -0.012535   0.978286
        INDIGO                  823        -0.013500   0.976625
    INDUSTOWER                  822        -0.015060   0.973937
      INOXWIND                  823        -0.014233   0.975341
     INTELLECT                  822        -0.012158   0.978914
           IOB                  824        -0.013911   0.975902
           IOC                  821        -0.055753   0.903635
       IPCALAB                  823        -0.014362   0.975115
           IRB                  823        -0.014699   0.974591
         IRCON                  824        -0.013171   0.977155
          IRFC                  824        -0.026187   0.954679
           ITI                  824        -0.015091   0.973881
    JBCHEPHARM                  823        -0.014373   0.975124
          JBMA                  822        -0.013070   0.977331
     JINDALSAW                  822        -0.012660   0.978074
    JINDALSTEL                  823        -0.011659   0.979748
    JMFINANCIL                  823        -0.015311   0.973506
           JSL                  819        -0.010772   0.981340
     JSWENERGY                  821        -0.012228   0.978771
      JSWSTEEL                  824        -0.013552   0.976509
      JUBLFOOD                  824        -0.014118   0.975552
    JUBLINGREA                  821        -0.009508   0.983462
    JUBLPHARMA                  819        -0.015170   0.973704
      JUSTDIAL                  822        -0.012491   0.978360
     JYOTHYLAB                  822        -0.015919   0.972454
      JYOTICNC                  823        -0.013697   0.976270
    KAJARIACER                  824        -0.013405   0.976758
    KALYANKJIL                  820        -0.009658   0.983212
    KARURVYSYA                  820        -0.015520   0.973137
        KAYNES                  824        -0.013107   0.977263
           KEC                  823        -0.013592   0.976470
           KEI                  819        -0.011180   0.980621
      KFINTECH                  823        -0.013480   0.976660
          KIMS                  823        -0.011812   0.979488
    KIRLOSBROS                  824        -0.013084   0.977302
     KIRLOSENG                  824        -0.013698   0.976263
          KPIL                  822        -0.016305   0.971826
      KPITTECH                  824        -0.013720   0.976226
       KPRMILL                  822        -0.013798   0.976123
    LALPATHLAB                  823        -0.012058   0.979070
    LATENTVIEW                  824        -0.013812   0.976069
    LAURUSLABS                  823        -0.019105   0.966940
     LEMONTREE                  824        -0.013745   0.976183
     LICHSGFIN                  820        -0.014293   0.975266
          LICI                  824        -0.021919   0.962065
    LINDEINDIA                  823        -0.021090   0.963460
         LODHA                  821        -0.014697   0.974563
            LT                  824        -0.015492   0.973188
           LTF                  823        -0.013328   0.976907
       LTFOODS                  824        -0.013974   0.975797
         LUPIN                  820        -0.017229   0.970176
           M&M                  823        -0.021454   0.962825
      MAHABANK                  824        -0.013119   0.977244
    MANAPPURAM                  821        -0.012328   0.978655
      MANYAVAR                  823        -0.012507   0.978307
    MAPMYINDIA                  824        -0.013807   0.976079
        MARICO                  824        -0.013019   0.977413
        MARUTI                  823        -0.013027   0.977424
     MAXHEALTH                  824        -0.014731   0.974504
           MCX                  820        -0.018166   0.968568
       MEDANTA                  821        -0.023383   0.959618
          MFSL                  824        -0.013054   0.977354
           MGL                  822        -0.013591   0.976481
         MHRIL                  824        -0.013090   0.977292
     MINDACORP                  824        -0.013040   0.977377
          MMTC                  822        -0.028535   0.950626
     MOTHERSON                  823        -0.012471   0.978368
    MOTILALOFS                  823        -0.016312   0.971802
       MPHASIS                  823        -0.012521   0.978284
           MRF                  822        -0.014851   0.974328
          MRPL                  823        -0.016278   0.971798
         MSUMI                  824        -0.013102   0.977273
    MUTHOOTFIN                  823        -0.013194   0.977139
     NAM-INDIA                  818        -0.008671   0.984925
    NATCOPHARM                  822        -0.016838   0.970847
    NATIONALUM                  824        -0.013126   0.977232
        NAUKRI                  822        -0.013853   0.976049
          NAVA                  823        -0.013586   0.976481
    NAVINFLUOR                  822        -0.013522   0.976588
        NAZARA                  824        -0.013505   0.976589
          NBCC                  822        -0.016938   0.970722
           NCC                  821        -0.011958   0.979260
     NESTLEIND                  824        -0.013469   0.976650
        NETWEB                  824        -0.017311   0.970039
    NEULANDLAB                  824        -0.015045   0.973962
        NEWGEN                  824        -0.016201   0.971962
          NHPC                  823        -0.011820   0.979475
         NIACL                  824        -0.013116   0.977249
      NLCINDIA                  824        -0.015628   0.972953
          NMDC                  823        -0.015198   0.973688
       NSLNISP                  823        -0.013212   0.977112
          NTPC                  818        -0.011722   0.979687
        NUVAMA                  822        -0.011371   0.980262
         NYKAA                  821        -0.010363   0.982002
          OFSS                  821        -0.022990   0.960307
           OIL                  821        -0.020564   0.964428
       OLECTRA                  823        -0.014902   0.974181
          ONGC                  823        -0.013931   0.975898
     PATANJALI                  822        -0.012217   0.978825
         PAYTM                  821        -0.010664   0.981489
          PCBL                  821        -0.011780   0.979580
    PERSISTENT                  822        -0.012708   0.977991
      PETRONET                  822        -0.014159   0.975480
           PFC                  823        -0.012515   0.978294
    PHOENIXLTD                  820        -0.012307   0.978688
           PNB                  822        -0.011826   0.979488
    PNBHOUSING                  823        -0.012723   0.977942
      PNCINFRA                  824        -0.013158   0.977177
     POLICYBZR                  822        -0.012142   0.978952
       POLYCAB                  822        -0.010685   0.981430
       POLYMED                  823        -0.012878   0.977678
    POONAWALLA                  823        -0.013024   0.977431
     POWERGRID                  821        -0.009976   0.982662
    POWERINDIA                  821        -0.035176   0.939343
     PPLPHARMA                  821        -0.012777   0.977879
       PRAJIND                  820        -0.019342   0.966593
      PRESTIGE                  822        -0.011398   0.980216
         PTCIL                  824        -0.013741   0.976189
         QUESS                  824        -0.013687   0.976281
        RADICO                  822        -0.013857   0.976007
       RAINBOW                  824        -0.013123   0.977237
       RAYMOND                  824        -0.009612   0.983224
       RBLBANK                  823        -0.020230   0.964973
           RCF                  822        -0.011666   0.979760
        RECLTD                  822        -0.019665   0.965949
     REDINGTON                  822        -0.011539   0.979976
       RKFORGE                  822        -0.013278   0.977018
       RRKABEL                  822        -0.011608   0.979860
      RTNINDIA                  824        -0.013148   0.977194
        SAFARI                  824        -0.013749   0.976176
          SAIL                  823        -0.014310   0.975229
    SAMMAANCAP                  823        -0.016430   0.971534
      SAREGAMA                  823        -0.012934   0.977583
          SBFC                  824        -0.013124   0.977235
       SBILIFE                  822        -0.011979   0.979229
          SBIN                  823        -0.015000   0.974047
    SCHAEFFLER                  823        -0.011777   0.979548
     SCHNEIDER                  822        -0.011232   0.980499
           SCI                  824        -0.017248   0.970149
    SHRIRAMFIN                  822        -0.018152   0.968622
     SHYAMMETL                  822        -0.030529   0.947291
       SIEMENS                  822        -0.018395   0.968109
         SOBHA                  818        -0.015412   0.973345
     SOLARINDS                  823        -0.012720   0.977945
      SONACOMS                  824        -0.013145   0.977199
    STARHEALTH                  824        -0.012523   0.978254
      SUMICHEM                  824        -0.013771   0.976139
    SUNDARMFIN                  821        -0.014301   0.975292
     SUNPHARMA                  823        -0.014681   0.974606
       SUNTECK                  824        -0.014161   0.975480
         SUNTV                  823        -0.015564   0.973033
    SUPREMEIND                  822        -0.012758   0.977908
        SUZLON                  822        -0.027724   0.952074
      SWANCORP                  821        -0.022709   0.960703
        SWIGGY                  824        -0.013769   0.976143
       SWSOLAR                  823        -0.015150   0.973805
         SYRMA                  822        -0.012062   0.979088
         TANLA                  823        -0.011753   0.979589
      TATACOMM                  823        -0.012365   0.978548
    TATACONSUM                  824        -0.014267   0.975300
     TATAELXSI                  824        -0.013026   0.977401
    TATAINVEST                  824        -0.029063   0.949700
     TATAPOWER                  824        -0.013777   0.976130
     TATASTEEL                  823        -0.014952   0.974143
        TBOTEK                  824        -0.013358   0.976838
         TECHM                  824        -0.013909   0.975906
      TEJASNET                  823        -0.012747   0.977900
       THERMAX                  824        -0.013127   0.977229
      TITAGARH                  824        -0.013146   0.977197
          TMPV                  824        -0.015003   0.974035
    TORNTPHARM                  824        -0.013623   0.976390
    TORNTPOWER                  822        -0.014580   0.974728
         TRENT                  821        -0.012423   0.978466
    TRITURBINE                  822        -0.012739   0.977929
       TRIVENI                  823        -0.013124   0.977262
          TTML                  824        -0.015435   0.973287
      TVSMOTOR                  819        -0.018288   0.968365
       UCOBANK                  824        -0.013167   0.977162
    UJJIVANSFB                  824        -0.013112   0.977255
     UNIONBANK                  823        -0.014731   0.974476
      UNITDSPR                  823        -0.014614   0.974674
      UNOMINDA                  822        -0.011387   0.980234
      USHAMART                  824        -0.013145   0.977198
        UTIAMC                  824        -0.016030   0.972258
    VAIBHAVGBL                  824        -0.013122   0.977238
        VARROC                  823        -0.013480   0.976660
           VBL                  823        -0.013389   0.976813
          VEDL                  819        -0.015961   0.972390
        VIJAYA                  820        -0.012251   0.978797
        VOLTAS                  822        -0.011288   0.980403
           VTL                  824        -0.013560   0.976497
    WAAREEENER                  824        -0.013063   0.977338
       WELCORP                  822        -0.012481   0.978377
    WELSPUNLIV                  822        -0.010513   0.981724
      WESTLIFE                  824        -0.013636   0.976368
     WHIRLPOOL                  823        -0.013334   0.976906
         WIPRO                  824        -0.013093   0.977288
    WOCKPHARMA                  824        -0.013149   0.977192
       YESBANK                  824        -0.013151   0.977188
          ZEEL                  824        -0.012431   0.978410
     ZFCVINDIA                  824        -0.013378   0.976805
     ZYDUSLIFE                  822        -0.013495   0.976654

## 13. Overlap/capacity diagnostics including clustering, partial-sector coverage and 1%-risk sizing
                                      Metric          Dimension                                                                                                      Value
                    ENABLED_ACCEPTED_ENTRIES                                                                                                                         852.0
                    ENABLED_COMPLETED_TRADES                                                                                                                         825.0
                 ENABLED_INCOMPLETE_ACCEPTED                                                                                                                          27.0
       MAX_SIMULTANEOUS_COMPLETED_LIFECYCLES                                                                                                                          50.0
     SIMULTANEOUS_LIFECYCLE_COVERAGE_PERCENT                                                                                                                         100.0
      MAX_SAME_DAY_ENABLED_QUALIFIED_SIGNALS                                                                                                                          15.0
       MAX_SAME_DAY_ENABLED_ACCEPTED_ENTRIES                                                                                                                          15.0
SAME_DAY_ENABLED_QUALIFIED_DISTRIBUTION_JSON                    {"1": 83, "10": 2, "12": 2, "15": 2, "2": 64, "3": 40, "4": 33, "5": 27, "6": 12, "7": 6, "8": 10, "9": 2}
                MEDIAN_INITIAL_RISK_FRACTION                                                                                                                      0.050481
              MEDIAN_IMPLIED_POSITION_WEIGHT                                                                                                                      0.198095
                 MAX_IMPLIED_POSITION_WEIGHT                                                                                                                      1.435378
                     MAPPED_ACCEPTED_ENTRIES                                                                                                                          24.0
                   UNMAPPED_ACCEPTED_ENTRIES                                                                                                                         828.0
                    MAPPING_COVERAGE_PERCENT                                                                                                                      2.816901
                          SECTOR_ENTRY_COUNT               AUTO                                                                                                        4.0
                          SECTOR_ENTRY_COUNT               BANK                                                                                                        3.0
                          SECTOR_ENTRY_COUNT             ENERGY                                                                                                        6.0
                          SECTOR_ENTRY_COUNT FINANCIAL_SERVICES                                                                                                        2.0
                          SECTOR_ENTRY_COUNT               FMCG                                                                                                        1.0
                          SECTOR_ENTRY_COUNT     INFRASTRUCTURE                                                                                                        4.0
                          SECTOR_ENTRY_COUNT              METAL                                                                                                        2.0
                          SECTOR_ENTRY_COUNT             PHARMA                                                                                                        2.0

Frozen enabled-trade diagnostics:
                              Metric             Value
                    R_Multiple_COUNT               825
                      R_Multiple_MIN         -3.909746
                   R_Multiple_MEDIAN         -0.456854
                     R_Multiple_MEAN          0.072442
                      R_Multiple_MAX         15.582553
                    Base_Net_R_COUNT               825
                      Base_Net_R_MIN          -3.97291
                   Base_Net_R_MEDIAN         -0.525008
                     Base_Net_R_MEAN         -0.014416
                      Base_Net_R_MAX         15.487691
                  Stress_Net_R_COUNT               825
                    Stress_Net_R_MIN         -4.004492
                 Stress_Net_R_MEDIAN         -0.564871
                   Stress_Net_R_MEAN         -0.057846
                    Stress_Net_R_MAX          15.44026
                  Severe_Net_R_COUNT               825
                    Severe_Net_R_MIN         -4.036074
                 Severe_Net_R_MEDIAN         -0.617501
                   Severe_Net_R_MEAN         -0.101275
                    Severe_Net_R_MAX         15.392829
                        Return_COUNT               825
                          Return_MIN         -0.247592
                       Return_MEDIAN         -0.023557
                         Return_MEAN          0.002167
                          Return_MAX          0.657061
              Holding_Sessions_COUNT               825
                Holding_Sessions_MIN                 0
             Holding_Sessions_MEDIAN               6.0
               Holding_Sessions_MEAN           9.50303
                Holding_Sessions_MAX                64
               Pct_Above_SMA50_COUNT               825
                 Pct_Above_SMA50_MIN              50.0
              Pct_Above_SMA50_MEDIAN         62.880325
                Pct_Above_SMA50_MEAN         66.466594
                 Pct_Above_SMA50_MAX         87.983707
        SMA50_Breadth_Coverage_COUNT               825
          SMA50_Breadth_Coverage_MIN          0.896208
       SMA50_Breadth_Coverage_MEDIAN          0.980119
         SMA50_Breadth_Coverage_MEAN          0.981843
          SMA50_Breadth_Coverage_MAX               1.0
                  Composite_RS_COUNT               825
                    Composite_RS_MIN              70.0
                 Composite_RS_MEDIAN         82.632653
                   Composite_RS_MEAN         83.215153
                    Composite_RS_MAX         99.879276
                  Pullback_Age_COUNT               825
                    Pullback_Age_MIN                 3
                 Pullback_Age_MEDIAN               5.0
                   Pullback_Age_MEAN          5.393939
                    Pullback_Age_MAX                10
            Pullback_Depth_ATR_COUNT               825
              Pullback_Depth_ATR_MIN          0.514314
           Pullback_Depth_ATR_MEDIAN          1.613113
             Pullback_Depth_ATR_MEAN          1.617368
              Pullback_Depth_ATR_MAX          2.490529
         Entry_Extension_ATR14_COUNT               825
           Entry_Extension_ATR14_MIN         -1.955345
        Entry_Extension_ATR14_MEDIAN         -0.322834
          Entry_Extension_ATR14_MEAN         -0.386921
           Entry_Extension_ATR14_MAX          0.422505
                   Exit_Reason_COUNT         SMA20=539
                   Exit_Reason_COUNT       STOP_GAP=11
                   Exit_Reason_COUNT STOP_INTRADAY=275
Nifty500_Distance_From_SMA200_MEDIAN          0.131866

## 14. Integrity audit
No rows.

## 15. Mandatory gate table
                      Gate  Pass  Mandatory     Value                 Threshold Status
            INTEGRITY_ZERO  True       True         0                      == 0   PASS
        SAMPLE_SUFFICIENCY  True       True       825                    >= 300   PASS
           BASE_SETUP_MEAN False       True -0.000379                       > 0   FAIL
             BASE_SETUP_PF False       True  0.987024                   >= 1.20   FAIL
     BASE_PRACTICAL_MEAN_R False       True -0.014416                   >= 0.15   FAIL
       BASE_PRACTICAL_R_PF False       True  0.975019                   >= 1.20   FAIL
   STRESS_PRACTICAL_MEAN_R False       True -0.057846                       > 0   FAIL
     STRESS_PRACTICAL_R_PF False       True  0.905144                    > 1.00   FAIL
REGIME_MEAN_DISCRIMINATION  True       True -0.014416        enabled > disabled   PASS
 REGIME_RPF_DISCRIMINATION  True       True  0.975019        enabled > disabled   PASS
     TEMPORAL_FIRST_MEAN_R  True       True  0.053281                       > 0   PASS
       TEMPORAL_FIRST_R_PF  True       True   1.09507                    > 1.00   PASS
    TEMPORAL_SECOND_MEAN_R False       True -0.334567                       > 0   FAIL
      TEMPORAL_SECOND_R_PF False       True  0.489918                    > 1.00   FAIL
   TOP_FIVE_REMOVED_MEAN_R False       True -0.088127                       > 0   FAIL
     TOP_FIVE_REMOVED_R_PF False       True  0.848219                    > 1.00   FAIL
           LOSO_ALL_MEAN_R False       True       359    > 0 for every omission   FAIL
             LOSO_ALL_R_PF False       True       359 > 1.00 for every omission   FAIL
              FINAL_STATUS False      False      FAIL         status precedence   FAIL

## 16. One formal final status and explicit next action
Formal M1 status: FAIL
FAIL -> close M1 and proceed to Candidate 2
No alternate thresholds, rescue suggestions, or post-result strategy changes are proposed.

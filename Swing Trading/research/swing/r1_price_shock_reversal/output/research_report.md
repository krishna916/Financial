# R1 Short-Term Price-Shock Reversal — Historical Evidence

Formal status: `FAIL`

This report records the frozen R1 experiment mechanically. It is evidence only; no post-hoc filter, threshold, subgroup rescue, or strategy recommendation is generated here.

## Frozen methodology

Point-in-time Nifty 500 membership; signal window 2023-08-01 through 2026-08-25; prior-20 sample volatility (ddof=1), prior-20 median volume and traded value; Shock_Score <= -2.0; low-volume ratio <= 1.0; high-volume control ratio >= 1.5; immediate next-session Open entry; structural stop at shock-day Low - 0.25 ATR14; T+6 Open exit; five-session horizon; base/stress/severe friction 0.40%/0.60%/0.80%; bootstrap 10,000 resamples with seed 20260828.

## Data coverage

Manifest symbols: 662; usable/downloaded symbols: 652; visible download failures: 10.

## Cohorts and accounting

All Shock_Score <= -2 candidates: 13722; cohort counts: {'HIGH_VOLUME': 8025, 'MIDDLE_VOLUME': 3511, 'LOW_VOLUME': 2165, 'NOT_ELIGIBLE_VOLUME': 21}.
Qualified low-volume signals: 1595; accepted entries: 1427; incomplete accepted entries: 3; cancellations: 168.
Cancellation reasons: {'OPEN_BELOW_STRUCTURAL_STOP': 89, 'SAME_SYMBOL_LOCKOUT': 74, 'MISSING_NEXT_SESSION': 5}.
High-volume control signals: 5816; completed raw control outcomes: 5092.

## Setup and practical outcomes

     Lens  Completed_Trades  Winners  Losers  Win_Rate  Gross_Return_Mean  Gross_Return_Median  Gross_Return_PF  Base_Net_Mean_Return  Base_Net_Return_PF  Stress_Net_Mean_Return  Stress_Net_Return_PF  Severe_Net_Mean_Return  Severe_Net_Return_PF  Gross_R_Mean  Gross_R_Median  Gross_R_PF  Base_Net_Mean_R  Base_Net_R_PF  Stress_Net_Mean_R  Stress_Net_R_PF  Severe_Net_Mean_R  Severe_Net_R_PF
    setup              1424      811     612  0.569522           0.009365             0.007259         1.623417              0.005365            1.318914                0.003365               1.18921                0.001365              1.072681           NaN             NaN         NaN              NaN            NaN                NaN              NaN                NaN              NaN
practical              1424      369    1055  0.259129                NaN                  NaN              NaN                   NaN                 NaN                     NaN                   NaN                     NaN                   NaN      0.096691            -1.0    1.130672         -0.30496       0.715036          -0.505785         0.591056          -0.706611         0.496667

## High-volume falsification comparison

 Low_Volume_Trades  High_Volume_Trades  Low_Volume_Gross_Mean_Return  High_Volume_Gross_Mean_Return  Low_Volume_Gross_PF  High_Volume_Gross_PF  Low_Mean_Exceeds_High  Low_PF_Exceeds_High
              1424                5092                      0.009365                       0.010558             1.623417              1.616497                  False                 True

## Temporal robustness

     Period Signal_Start Signal_End  Completed_Trades  Base_Net_Mean_Return  Base_Net_Return_PF
 FIRST_HALF   2023-08-01 2025-02-11               747              0.007061            1.381072
SECOND_HALF   2025-02-12 2026-08-25               677              0.003494            1.233852

## Calendar-year diagnostics

 Year  Completed_Trades  Gross_Mean_Return  Base_Net_Mean_Return  Base_Net_Return_PF
 2023               141           0.023572              0.019572            3.022876
 2024               484           0.014711              0.010711            1.716093
 2025               453           0.003382             -0.000618            0.969836
 2026               346           0.003932             -0.000068            0.996106

## Outlier and leave-one-symbol-out diagnostics

                      Analysis  Removed_Trades  Remaining_Trades  Base_Net_Mean_Return  Base_Net_Return_PF
TOP_FIVE_GROSS_WINNERS_REMOVED               5              1419              0.004656            1.275812

Omitted_Symbol  Remaining_Trades  Base_Net_Mean_Return  Base_Net_Return_PF
        360ONE              1421              0.005482            1.327221
       3MINDIA              1422              0.005373            1.319401
      AARTIIND              1422              0.005276            1.313196
         AAVAS              1420              0.005182            1.307213
           ABB              1420              0.005360            1.318731
    ABBOTINDIA              1421              0.005390            1.320078
     ABCAPITAL              1420              0.005409            1.322026
         ABFRL              1422              0.005420            1.322657
         ABLBL              1423              0.005392            1.320740
         ABREL              1422              0.005418            1.323377
       ABSLAMC              1422              0.005378            1.320316
           ACC              1417              0.005325            1.316744
     ACMESOLAR              1423              0.005287            1.314049
    ADANIENSOL              1419              0.005312            1.315970
      ADANIENT              1418              0.005238            1.310305
    ADANIGREEN              1421              0.005212            1.309175
    ADANIPORTS              1421              0.005330            1.316492
    ADANIPOWER              1421              0.005379            1.319652
      AEGISLOG              1422              0.005330            1.316384
        AFCONS              1421              0.005383            1.319641
         AFFLE              1421              0.005394            1.321327
        AIAENG              1418              0.005402            1.320974
          AIIL              1422              0.005321            1.315875
    AJANTPHARM              1419              0.005284            1.314222
         ALKEM              1419              0.005308            1.314840
         AMBER              1423              0.005335            1.316881
     AMBUJACEM              1418              0.005362            1.318028
    ANANDRATHI              1423              0.005334            1.316814
      ANANTRAJ              1423              0.005361            1.318419
        ANURAS              1421              0.005462            1.325614
     APLAPOLLO              1418              0.005375            1.318986
        APLLTD              1422              0.005294            1.314509
    APOLLOHOSP              1421              0.005347            1.317756
    APOLLOTYRE              1418              0.005484            1.327251
         APTUS              1420              0.005365            1.319346
         ARE&M              1421              0.005270            1.312581
    ASAHIINDIA              1422              0.005285            1.313723
      ASHOKLEY              1421              0.005376            1.319138
    ASIANPAINT              1417              0.005412            1.320896
       ASTERDM              1421              0.005345            1.317103
        ASTRAL              1417              0.005446            1.324230
          ATGL              1418              0.005342            1.316508
          ATUL              1422              0.005345            1.317245
        AUBANK              1420              0.005453            1.324626
    AUROPHARMA              1423              0.005360            1.318362
    AVANTIFEED              1423              0.005315            1.315724
           AWL              1421              0.005366            1.318601
    BAJAJ-AUTO              1423              0.005383            1.320042
    BAJAJFINSV              1422              0.005367            1.318888
      BAJAJHFL              1423              0.005327            1.316406
    BAJAJHLDNG              1416              0.005520            1.329096
    BAJFINANCE              1423              0.005381            1.319840
    BALKRISIND              1418              0.005327            1.316141
    BALRAMCHIN              1421              0.005380            1.319683
    BANDHANBNK              1422              0.005282            1.313550
    BANKBARODA              1422              0.005332            1.316836
          BASF              1423              0.005392            1.320716
     BATAINDIA              1420              0.005407            1.321619
     BAYERCROP              1421              0.005391            1.320211
          BBTC              1422              0.005429            1.323364
           BCG              1423              0.005451            1.325374
           BDL              1421              0.005441            1.324047
           BEL              1423              0.005305            1.315128
          BEML              1421              0.005398            1.320701
    BERGEPAINT              1419              0.005311            1.314585
    BHARATFORG              1419              0.005377            1.319588
    BHARTIARTL              1422              0.005358            1.318026
    BHARTIHEXA              1423              0.005413            1.322375
        BIOCON              1422              0.005392            1.320443
    BIRLACORPN              1422              0.005416            1.322906
           BLS              1421              0.005367            1.319640
       BLUEJET              1423              0.005406            1.321803
    BLUESTARCO              1422              0.005386            1.319964
      BOSCHLTD              1421              0.005446            1.324596
          BPCL              1421              0.005387            1.320540
       BRIGADE              1421              0.005326            1.316548
     BRITANNIA              1419              0.005427            1.322455
           BSE              1422              0.005287            1.313797
         BSOFT              1420              0.005342            1.316994
        CAMPUS              1423              0.005384            1.320104
          CAMS              1421              0.005367            1.319930
         CANBK              1422              0.005381            1.320338
    CANFINHOME              1421              0.005341            1.317377
      CANHLIFE              1423              0.005372            1.319116
    CARBORUNIV              1420              0.005323            1.315794
    CASTROLIND              1421              0.005413            1.322177
          CDSL              1421              0.005511            1.329530
       CEATLTD              1419              0.005260            1.311833
         CELLO              1423              0.005379            1.319710
     CENTRALBK              1422              0.005396            1.320722
          CERA              1422              0.005354            1.317819
          CESC              1422              0.005354            1.317783
          CGCL              1419              0.005403            1.320880
       CGPOWER              1423              0.005348            1.317681
    CHAMBLFERT              1415              0.005295            1.314774
    CHEMPLASTS              1423              0.005321            1.316048
    CHENNPETRO              1421              0.005338            1.316773
      CHOICEIN              1422              0.005431            1.323477
      CHOLAFIN              1423              0.005370            1.318985
    CHOLAHLDNG              1421              0.005405            1.321265
         CIPLA              1422              0.005404            1.321338
         CLEAN              1419              0.005445            1.324156
     COALINDIA              1422              0.005390            1.320347
    COCHINSHIP              1421              0.005410            1.322106
       COHANCE              1419              0.005292            1.314321
        COLPAL              1422              0.005397            1.320840
        CONCOR              1420              0.005323            1.316132
    CONCORDBIO              1420              0.005310            1.315359
    COROMANDEL              1417              0.005404            1.321446
     CRAFTSMAN              1422              0.005350            1.317630
     CREDITACC              1422              0.005394            1.320733
        CRISIL              1421              0.005419            1.322452
      CROMPTON              1418              0.005427            1.322975
           CUB              1418              0.005400            1.321406
    CUMMINSIND              1420              0.005330            1.315956
        CYIENT              1421              0.005398            1.321262
         DABUR              1422              0.005390            1.320287
     DALBHARAT              1420              0.005294            1.313774
    DATAPATTNS              1422              0.005219            1.309789
      DBREALTY              1423              0.005421            1.323028
    DCMSHRIRAM              1423              0.005383            1.319992
     DEEPAKNTR              1423              0.005339            1.317124
     DELHIVERY              1418              0.005214            1.309734
     DELTACORP              1423              0.005340            1.317210
       DEVYANI              1421              0.005432            1.324280
      DIVISLAB              1420              0.005428            1.322656
           DLF              1419              0.005378            1.319665
         DMART              1422              0.005282            1.313563
       DRREDDY              1422              0.005383            1.319703
    EASEMYTRIP              1422              0.005390            1.320286
        ECLERX              1423              0.005396            1.321035
     EICHERMOT              1423              0.005360            1.318359
      EIDPARRY              1420              0.005338            1.316964
       EIHOTEL              1422              0.005365            1.319007
        ELECON              1423              0.005325            1.316305
     ELGIEQUIP              1422              0.005349            1.317734
      EMAMILTD              1417              0.005421            1.323394
        EMCURE              1423              0.005393            1.320774
     ENDURANCE              1419              0.005309            1.314794
    ENGINERSIN              1423              0.005349            1.317749
    EQUITASBNK              1423              0.005399            1.321281
          ERIS              1423              0.005358            1.318286
       ESCORTS              1423              0.005370            1.318992
       ETERNAL              1421              0.005291            1.314210
      EXIDEIND              1419              0.005339            1.316615
          FACT              1415              0.005199            1.309203
     FINCABLES              1421              0.005428            1.322988
       FINPIPE              1423              0.005371            1.319051
      FIVESTAR              1422              0.005465            1.326197
    FLUOROCHEM              1421              0.005408            1.321478
      FORCEMOT              1423              0.005349            1.317721
        FORTIS              1420              0.005331            1.316140
           FSL              1422              0.005496            1.328606
          GAIL              1420              0.005222            1.309506
        GESHIP              1418              0.005459            1.325805
         GICRE              1420              0.005290            1.313551
      GILLETTE              1421              0.005313            1.315830
         GLAND              1417              0.005370            1.318930
         GLAXO              1420              0.005343            1.317744
      GLENMARK              1422              0.005313            1.315389
       GMDCLTD              1421              0.005467            1.326008
    GMMPFAUDLR              1423              0.005341            1.317231
    GMRAIRPORT              1420              0.005301            1.314238
          GNFC              1423              0.005368            1.318831
      GOCOLORS              1423              0.005382            1.319930
    GODFRYPHLP              1423              0.005385            1.320179
       GODIGIT              1422              0.005344            1.317727
     GODREJIND              1421              0.005359            1.318187
    GODREJPROP              1419              0.005606            1.336511
          GPPL              1419              0.005184            1.307513
      GRANULES              1419              0.005282            1.313677
      GRAPHITE              1415              0.005405            1.322810
        GRASIM              1419              0.005402            1.320776
       GRAVITA              1423              0.005404            1.321641
          GRSE              1422              0.005339            1.318185
          GSFC              1422              0.005314            1.315449
         GVT&D              1422              0.005248            1.311482
           HAL              1422              0.005384            1.320592
    HAPPSTMNDS              1421              0.005390            1.320046
       HAVELLS              1420              0.005450            1.324999
     HBLENGINE              1422              0.005463            1.326031
       HCLTECH              1421              0.005403            1.321042
         HDBFS              1423              0.005299            1.314751
       HDFCAMC              1419              0.005219            1.309123
      HDFCBANK              1422              0.005394            1.320582
      HDFCLIFE              1422              0.005378            1.319367
           HEG              1418              0.005569            1.333581
    HEROMOTOCO              1420              0.005335            1.316836
          HFCL              1423              0.005383            1.320031
    HINDCOPPER              1421              0.005355            1.318072
     HINDPETRO              1422              0.005418            1.322576
    HINDUNILVR              1420              0.005363            1.318236
      HINDZINC              1423              0.005336            1.316983
     HOMEFIRST              1422              0.005380            1.319872
        HONASA              1422              0.005320            1.315807
        HONAUT              1418              0.005477            1.326153
          HSCL              1420              0.005292            1.313794
         HUDCO              1417              0.005481            1.326959
       HYUNDAI              1423              0.005416            1.322638
     ICICIBANK              1420              0.005349            1.317575
       ICICIGI              1419              0.005422            1.322189
    ICICIPRULI              1421              0.005394            1.320558
          IDBI              1421              0.005281            1.313232
          IDEA              1417              0.005233            1.311626
    IDFCFIRSTB              1422              0.005373            1.319141
           IEX              1421              0.005393            1.320290
          IFCI              1419              0.005449            1.324027
          IGIL              1421              0.005310            1.315236
           IGL              1421              0.005472            1.326463
           IKS              1421              0.005366            1.318531
         INDGN              1423              0.005349            1.317705
      INDHOTEL              1419              0.005328            1.316396
      INDIACEM              1422              0.005279            1.313338
     INDIAMART              1418              0.005312            1.315242
       INDIANB              1422              0.005287            1.313826
        INDIGO              1422              0.005353            1.317868
    INDUSINDBK              1419              0.005415            1.322434
    INDUSTOWER              1417              0.005377            1.319062
          INFY              1423              0.005367            1.318812
     INOXINDIA              1422              0.005360            1.318377
      INOXWIND              1418              0.005372            1.318499
     INTELLECT              1422              0.005445            1.324632
           IOB              1420              0.005356            1.317903
           IOC              1421              0.005343            1.317011
           IRB              1421              0.005359            1.317956
         IRCON              1420              0.005208            1.309733
         IRCTC              1421              0.005382            1.319451
         IREDA              1423              0.005323            1.316163
          IRFC              1422              0.005439            1.324128
           ITC              1419              0.005442            1.323504
           ITI              1419              0.005295            1.313724
       J&KBANK              1423              0.005362            1.318503
     JAMNAAUTO              1422              0.005330            1.316459
    JBCHEPHARM              1418              0.005391            1.320546
          JBMA              1422              0.005275            1.313093
     JINDALSAW              1421              0.005410            1.322755
    JINDALSTEL              1416              0.005320            1.315807
        JIOFIN              1423              0.005382            1.319918
      JKCEMENT              1418              0.005399            1.320251
     JKLAKSHMI              1421              0.005375            1.319373
        JKTYRE              1422              0.005352            1.317668
    JMFINANCIL              1421              0.005406            1.321462
           JSL              1421              0.005317            1.315408
     JSWCEMENT              1422              0.005394            1.320627
      JSWDULUX              1423              0.005328            1.316467
     JSWENERGY              1422              0.005304            1.314876
      JSWINFRA              1418              0.005279            1.312443
      JSWSTEEL              1420              0.005364            1.318332
      JUBLFOOD              1419              0.005336            1.317104
    JUBLINGREA              1420              0.005369            1.319106
    JUBLPHARMA              1423              0.005325            1.316325
      JUSTDIAL              1423              0.005424            1.323222
           JWL              1420              0.005501            1.328397
     JYOTHYLAB              1421              0.005358            1.317843
    KAJARIACER              1415              0.005299            1.314848
    KALYANKJIL              1422              0.005373            1.319587
     KANSAINER              1422              0.005374            1.319150
    KARURVYSYA              1421              0.005297            1.314211
        KAYNES              1423              0.005362            1.318478
           KEC              1420              0.005376            1.319298
           KEI              1423              0.005350            1.317807
      KFINTECH              1419              0.005253            1.311415
          KIMS              1420              0.005411            1.321379
    KIRLOSBROS              1423              0.005413            1.322399
     KIRLOSENG              1422              0.005301            1.314637
        KNRCON              1420              0.005360            1.318292
     KOTAKBANK              1423              0.005364            1.318600
          KPIL              1418              0.005430            1.323111
      KPITTECH              1421              0.005559            1.333361
       KPRMILL              1419              0.005302            1.315616
          KRBL              1423              0.005360            1.318382
    LALPATHLAB              1419              0.005295            1.314637
    LATENTVIEW              1422              0.005392            1.321174
    LAURUSLABS              1422              0.005413            1.322046
     LEMONTREE              1423              0.005393            1.320764
      LENSKART              1423              0.005354            1.318030
      LGEINDIA              1422              0.005380            1.319543
     LICHSGFIN              1421              0.005358            1.318128
          LICI              1420              0.005383            1.320081
    LINDEINDIA              1423              0.005382            1.319905
      LLOYDSME              1422              0.005334            1.316634
         LODHA              1419              0.005344            1.317061
            LT              1423              0.005378            1.319593
           LTF              1423              0.005374            1.319313
       LTFOODS              1422              0.005424            1.322972
           LTM              1421              0.005367            1.318812
          LTTS              1421              0.005395            1.320398
         LUPIN              1419              0.005291            1.313586
        LXCHEM              1422              0.005256            1.311973
        M&MFIN              1422              0.005305            1.314895
      MAHABANK              1421              0.005288            1.313637
       MAHLIFE              1422              0.005283            1.313588
    MAHSEAMLES              1423              0.005338            1.317094
    MANAPPURAM              1420              0.005265            1.312431
       MANKIND              1422              0.005321            1.315844
      MANYAVAR              1420              0.005373            1.318713
    MAPMYINDIA              1422              0.005379            1.319655
        MARICO              1423              0.005386            1.320284
     MAXHEALTH              1422              0.005346            1.317334
       MAZDOCK              1419              0.005151            1.305577
           MCX              1423              0.005348            1.317692
       MEDANTA              1418              0.005499            1.327762
    METROBRAND              1420              0.005357            1.317690
    METROPOLIS              1422              0.005370            1.318882
          MFSL              1421              0.005371            1.318971
           MGL              1419              0.005300            1.314257
     MINDACORP              1422              0.005344            1.317251
          MMTC              1423              0.005379            1.319679
     MOTHERSON              1419              0.005443            1.324964
    MOTILALOFS              1421              0.005495            1.328243
       MPHASIS              1421              0.005367            1.318498
          MRPL              1419              0.005227            1.309604
         MSUMI              1421              0.005388            1.320235
    MUTHOOTFIN              1420              0.005330            1.315991
     NAM-INDIA              1423              0.005350            1.317766
    NATCOPHARM              1420              0.005438            1.323932
    NATIONALUM              1422              0.005250            1.311612
        NAUKRI              1420              0.005523            1.330191
    NAVINFLUOR              1421              0.005308            1.315036
          NBCC              1419              0.005249            1.311869
           NCC              1421              0.005189            1.307897
     NESTLEIND              1418              0.005408            1.321102
        NETWEB              1423              0.005424            1.323273
     NETWORK18              1423              0.005367            1.318808
        NEWGEN              1423              0.005441            1.324620
            NH              1423              0.005349            1.317727
          NHPC              1419              0.005263            1.312009
         NIACL              1423              0.005290            1.314239
      NLCINDIA              1422              0.005240            1.311055
          NMDC              1420              0.005341            1.317682
          NTPC              1421              0.005364            1.319316
        NUVOCO              1423              0.005351            1.317819
         NYKAA              1422              0.005359            1.318293
    OBEROIRLTY              1419              0.005421            1.322591
          OFSS              1422              0.005446            1.324685
           OIL              1423              0.005394            1.320884
     ONESOURCE              1422              0.005457            1.325505
          ONGC              1421              0.005378            1.319294
       PAGEIND              1418              0.005328            1.315953
     PATANJALI              1420              0.005380            1.319310
         PAYTM              1423              0.005331            1.316680
          PCBL              1420              0.005261            1.312191
    PERSISTENT              1423              0.005470            1.326885
      PETRONET              1420              0.005496            1.328393
           PFC              1422              0.005340            1.316975
        PFIZER              1422              0.005356            1.317983
    PHOENIXLTD              1422              0.005399            1.320988
    PIDILITIND              1417              0.005407            1.320611
         PIIND              1420              0.005402            1.321332
           PNB              1423              0.005319            1.315925
    PNBHOUSING              1418              0.005297            1.313787
      PNCINFRA              1421              0.005264            1.312248
     POLICYBZR              1423              0.005410            1.322100
       POLYCAB              1423              0.005365            1.318670
    POONAWALLA              1417              0.005416            1.321822
     POWERGRID              1420              0.005415            1.321998
     PPLPHARMA              1422              0.005392            1.320428
       PRAJIND              1420              0.005370            1.319978
    PREMIERENE              1422              0.005374            1.319314
      PRESTIGE              1423              0.005437            1.324279
    PRINCEPIPE              1423              0.005337            1.317012
       PVRINOX              1420              0.005375            1.319725
         QUESS              1421              0.005410            1.321812
        RADICO              1420              0.005413            1.322785
       RAILTEL              1422              0.005473            1.326830
          RAIN              1423              0.005200            1.308896
       RAINBOW              1423              0.005317            1.315823
    RAJESHEXPO              1423              0.005332            1.316717
        RALLIS              1423              0.005340            1.317206
      RAMCOCEM              1417              0.005445            1.323642
     RATNAMANI              1423              0.005381            1.319842
       RAYMOND              1421              0.005325            1.315993
           RBA              1422              0.005301            1.314666
       RBLBANK              1421              0.005337            1.317083
           RCF              1421              0.005396            1.320998
     REDINGTON              1421              0.005431            1.323371
      RELIANCE              1419              0.005351            1.317541
        RENUKA              1423              0.005344            1.317448
          RHIM              1423              0.005356            1.318154
         RITES              1420              0.005345            1.317625
         ROUTE              1420              0.005414            1.321683
       RRKABEL              1418              0.005412            1.323006
          RVNL              1422              0.005429            1.323351
      SAGILITY              1423              0.005305            1.315143
          SAIL              1423              0.005289            1.314183
       SAILIFE              1421              0.005291            1.313892
    SAMMAANCAP              1422              0.005328            1.316585
      SAPPHIRE              1422              0.005400            1.321120
       SARDAEN              1422              0.005207            1.309067
      SAREGAMA              1420              0.005378            1.319759
          SBFC              1422              0.005395            1.320683
       SBICARD              1420              0.005447            1.324681
       SBILIFE              1418              0.005396            1.320345
          SBIN              1422              0.005387            1.320038
    SCHAEFFLER              1416              0.005360            1.318779
           SCI              1423              0.005375            1.319384
      SHREECEM              1423              0.005361            1.318417
    SHRIRAMFIN              1422              0.005404            1.321389
     SHYAMMETL              1421              0.005299            1.314316
       SIEMENS              1419              0.005280            1.313178
     SIGNATURE              1421              0.005387            1.320491
      SKFINDIA              1421              0.005328            1.316012
         SOBHA              1422              0.005378            1.320028
     SOLARINDS              1421              0.005295            1.315150
      SONACOMS              1420              0.005371            1.319547
    SONATSOFTW              1419              0.005465            1.326527
         SPARC              1422              0.005370            1.318986
           SRF              1419              0.005362            1.317925
    STARHEALTH              1418              0.005426            1.322775
      SUMICHEM              1423              0.005445            1.324901
    SUNDARMFIN              1421              0.005359            1.318544
     SUNPHARMA              1421              0.005394            1.320493
       SUNTECK              1423              0.005445            1.324935
         SUNTV              1422              0.005418            1.322437
      SUPRAJIT              1423              0.005369            1.318948
    SUPREMEIND              1419              0.005448            1.324667
        SUZLON              1421              0.005432            1.323321
      SWANCORP              1419              0.005559            1.332862
        SWIGGY              1423              0.005423            1.323173
       SWSOLAR              1422              0.005455            1.325403
       SYNGENE              1417              0.005357            1.317776
         SYRMA              1423              0.005402            1.321528
      TATACHEM              1423              0.005383            1.320013
      TATACOMM              1422              0.005370            1.318959
    TATACONSUM              1423              0.005382            1.319965
     TATAELXSI              1421              0.005402            1.320935
    TATAINVEST              1422              0.005368            1.318870
     TATAPOWER              1423              0.005361            1.318435
     TATASTEEL              1421              0.005327            1.315980
      TATATECH              1423              0.005375            1.319365
        TBOTEK              1423              0.005367            1.318822
           TCS              1421              0.005382            1.319563
         TECHM              1421              0.005324            1.315820
       TECHNOE              1422              0.005363            1.318350
      TEJASNET              1421              0.005360            1.318719
       THERMAX              1422              0.005377            1.319370
       TIINDIA              1422              0.005294            1.314256
        TIMKEN              1416              0.005471            1.325665
      TITAGARH              1422              0.005341            1.317464
         TITAN              1423              0.005390            1.320563
          TMCV              1423              0.005423            1.323166
          TMPV              1421              0.005152            1.305600
    TORNTPHARM              1417              0.005308            1.314540
    TORNTPOWER              1419              0.005384            1.320633
         TRENT              1421              0.005412            1.321896
       TRIDENT              1423              0.005359            1.318307
    TRITURBINE              1420              0.005190            1.307912
       TRIVENI              1421              0.005376            1.319848
          TTML              1423              0.005359            1.318314
      TVSMOTOR              1422              0.005297            1.314412
        TVSSCS              1422              0.005308            1.315078
           UBL              1422              0.005405            1.321689
       UCOBANK              1422              0.005423            1.322863
    UJJIVANSFB              1422              0.005385            1.319878
    ULTRACEMCO              1421              0.005358            1.318211
     UNIONBANK              1422              0.005345            1.317278
      UNITDSPR              1421              0.005434            1.323883
      UNOMINDA              1421              0.005281            1.313269
           UPL              1417              0.005366            1.318406
        UTIAMC              1422              0.005311            1.315269
        VARROC              1422              0.005390            1.320513
          VEDL              1423              0.005315            1.315698
        VGUARD              1422              0.005473            1.326788
        VIJAYA              1423              0.005317            1.315804
        VIPIND              1422              0.005481            1.327479
           VMM              1423              0.005378            1.319601
        VOLTAS              1419              0.005295            1.314027
           VTL              1423              0.005385            1.320177
       WELCORP              1422              0.005305            1.314891
    WELSPUNLIV              1420              0.005433            1.323163
      WESTLIFE              1423              0.005371            1.319087
     WHIRLPOOL              1417              0.005495            1.327685
         WIPRO              1422              0.005410            1.321854
       YESBANK              1422              0.005315            1.315937
          ZEEL              1420              0.005366            1.319031
    ZENSARTECH              1421              0.005349            1.317693
     ZFCVINDIA              1421              0.005543            1.332065
     ZYDUSLIFE              1421              0.005391            1.320383

## Forward-return diagnostics

 Holding_Sessions  Observations  Mean_Return  Median_Return
                1          1427     0.004346       0.003651
                3          1424     0.005956       0.002411
                5          1424     0.009365       0.007259
               10          1416     0.017807       0.009858
               20          1407     0.016150       0.007519

## Bootstrap intervals

                          Metric  Estimate  CI_Lower  CI_Upper     Seed  Resamples  Confidence
         GROSS_SETUP_MEAN_RETURN  0.009365  0.006642  0.012065 20260828      10000        0.95
      BASE_NET_SETUP_MEAN_RETURN  0.005365  0.002642  0.008065 20260828      10000        0.95
       BASE_NET_PRACTICAL_MEAN_R -0.304960 -0.445622 -0.156833 20260828      10000        0.95
LOW_MINUS_HIGH_GROSS_MEAN_RETURN -0.001193 -0.004325  0.001967 20260828      10000        0.95

## Overlap/capacity diagnostics

 Accepted_Entries  Max_Simultaneous_Trades  Average_Simultaneous_Trades  Max_Same_Day_Entries  Overlapping_Entries  Overlap_Percentage                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    Same_Day_Entry_Counts  Median_Implied_Position_Weight  Max_Implied_Position_Weight  Max_Simultaneous_Implied_Gross_Capital
             1427                       75                    10.621461                    49                 1421            0.995795 {"2026-03-20": 49, "2025-01-07": 44, "2026-05-13": 44, "2023-10-25": 37, "2024-08-06": 33, "2025-07-28": 31, "2024-01-24": 30, "2024-02-13": 30, "2024-10-23": 27, "2024-12-23": 26, "2026-03-24": 26, "2025-09-29": 25, "2025-01-14": 24, "2023-12-21": 23, "2024-07-22": 23, "2024-05-10": 21, "2025-12-09": 21, "2026-01-27": 20, "2026-07-09": 19, "2023-10-10": 18, "2024-10-08": 18, "2025-08-04": 18, "2026-01-21": 18, "2025-04-08": 17, "2026-03-16": 17, "2026-05-12": 16, "2024-10-04": 15, "2024-03-14": 14, "2025-01-28": 14, "2025-06-20": 14, "2025-07-29": 14, "2023-09-13": 13, "2024-05-08": 12, "2024-11-14": 12, "2026-01-09": 11, "2024-10-07": 9, "2026-06-09": 9, "2024-01-09": 8, "2024-02-29": 8, "2024-06-05": 8, "2024-10-18": 8, "2024-10-22": 8, "2025-01-13": 8, "2025-02-12": 8, "2025-11-07": 8, "2026-02-03": 8, "2026-03-10": 8, "2026-07-23": 8, "2024-03-13": 7, "2024-09-19": 7, "2025-02-17": 7, "2025-07-14": 7, "2025-08-11": 7, "2026-03-05": 7, "2024-01-18": 6, "2024-05-07": 6, "2025-08-07": 6, "2026-06-11": 6, "2024-03-12": 5, "2024-04-16": 5, "2024-09-12": 5, "2024-09-17": 5, "2024-11-05": 5, "2025-04-02": 5, "2025-04-28": 5, "2025-08-29": 5, "2025-11-19": 5, "2025-11-24": 5, "2025-12-04": 5, "2026-01-20": 5, "2026-03-04": 5, "2026-06-02": 5, "2026-07-24": 5, "2023-12-13": 4, "2024-01-19": 4, "2024-05-31": 4, "2024-07-09": 4, "2024-09-09": 4, "2024-09-20": 4, "2024-09-30": 4, "2024-10-28": 4, "2024-12-18": 4, "2024-12-24": 4, "2025-01-09": 4, "2025-01-27": 4, "2025-02-28": 4, "2025-05-07": 4, "2025-07-23": 4, "2025-08-01": 4, "2025-09-23": 4, "2025-10-09": 4, "2026-02-20": 4, "2023-08-03": 3, "2023-08-16": 3, "2023-09-29": 3, "2023-10-05": 3, "2023-10-19": 3, "2023-12-11": 3, "2024-02-09": 3, "2024-02-14": 3, "2024-08-26": 3, "2024-09-10": 3, "2024-09-18": 3, "2024-09-26": 3, "2024-12-20": 3, "2024-12-31": 3, "2025-01-06": 3, "2025-03-03": 3, "2025-03-12": 3, "2025-07-02": 3, "2025-07-25": 3, "2025-07-30": 3, "2025-09-25": 3, "2025-11-06": 3, "2025-12-11": 3, "2025-12-18": 3, "2025-12-29": 3, "2026-05-19": 3, "2026-06-12": 3, "2026-07-08": 3, "2026-07-15": 3, "2026-07-31": 3, "2026-08-17": 3, "2026-08-18": 3, "2023-08-28": 2, "2023-09-21": 2, "2023-09-25": 2, "2023-10-26": 2, "2023-11-02": 2, "2024-01-10": 2, "2024-01-29": 2, "2024-03-05": 2, "2024-03-20": 2, "2024-08-05": 2, "2024-08-09": 2, "2024-10-30": 2, "2024-11-08": 2, "2024-11-22": 2, "2024-12-13": 2, "2025-01-10": 2, "2025-01-22": 2, "2025-01-23": 2, "2025-02-11": 2, "2025-05-21": 2, "2025-06-12": 2, "2025-06-16": 2, "2025-06-18": 2, "2025-06-19": 2, "2025-07-03": 2, "2025-07-04": 2, "2025-08-13": 2, "2025-08-25": 2, "2025-08-28": 2, "2025-09-26": 2, "2025-11-11": 2, "2025-12-08": 2, "2025-12-17": 2, "2025-12-19": 2, "2025-12-30": 2, "2026-01-12": 2, "2026-01-13": 2, "2026-02-16": 2, "2026-02-25": 2, "2026-03-12": 2, "2026-06-30": 2, "2026-07-20": 2, "2026-07-27": 2, "2026-08-12": 2, "2026-08-25": 2, "2023-08-02": 1, "2023-08-04": 1, "2023-08-07": 1, "2023-08-14": 1, "2023-08-17": 1, "2023-08-24": 1, "2023-09-05": 1, "2023-09-14": 1, "2023-09-15": 1, "2023-09-27": 1, "2023-10-04": 1, "2023-10-23": 1, "2023-10-27": 1, "2023-11-10": 1, "2023-11-21": 1, "2023-11-23": 1, "2023-11-24": 1, "2023-12-20": 1, "2024-01-03": 1, "2024-01-04": 1, "2024-01-05": 1, "2024-01-11": 1, "2024-01-17": 1, "2024-01-31": 1, "2024-02-05": 1, "2024-02-22": 1, "2024-03-06": 1, "2024-03-07": 1, "2024-03-11": 1, "2024-03-27": 1, "2024-04-04": 1, "2024-04-19": 1, "2024-04-23": 1, "2024-04-24": 1, "2024-04-29": 1, "2024-05-16": 1, "2024-05-22": 1, "2024-06-20": 1, "2024-06-25": 1, "2024-07-11": 1, "2024-07-12": 1, "2024-07-19": 1, "2024-07-26": 1, "2024-08-02": 1, "2024-08-07": 1, "2024-08-14": 1, "2024-08-16": 1, "2024-08-28": 1, "2024-09-02": 1, "2024-09-03": 1, "2024-09-25": 1, "2024-10-01": 1, "2024-10-29": 1, "2024-10-31": 1, "2024-11-11": 1, "2024-11-13": 1, "2024-11-18": 1, "2024-11-27": 1, "2024-12-17": 1, "2024-12-19": 1, "2024-12-27": 1, "2025-01-03": 1, "2025-01-20": 1, "2025-01-29": 1, "2025-02-04": 1, "2025-02-06": 1, "2025-03-04": 1, "2025-03-11": 1, "2025-03-17": 1, "2025-03-20": 1, "2025-04-11": 1, "2025-04-25": 1, "2025-05-02": 1, "2025-05-05": 1, "2025-05-12": 1, "2025-05-23": 1, "2025-05-27": 1, "2025-05-30": 1, "2025-06-03": 1, "2025-06-04": 1, "2025-06-24": 1, "2025-07-09": 1, "2025-07-11": 1, "2025-07-17": 1, "2025-07-21": 1, "2025-08-18": 1, "2025-08-22": 1, "2025-09-05": 1, "2025-09-09": 1, "2025-09-12": 1, "2025-09-24": 1, "2025-10-08": 1, "2025-10-15": 1, "2025-10-20": 1, "2025-10-21": 1, "2025-10-24": 1, "2025-10-27": 1, "2025-10-31": 1, "2025-11-03": 1, "2025-11-04": 1, "2025-11-10": 1, "2025-11-25": 1, "2025-11-28": 1, "2025-12-16": 1, "2025-12-31": 1, "2026-01-02": 1, "2026-01-07": 1, "2026-01-14": 1, "2026-01-16": 1, "2026-02-06": 1, "2026-02-09": 1, "2026-04-24": 1, "2026-05-04": 1, "2026-07-02": 1, "2026-07-07": 1, "2026-07-22": 1, "2026-07-29": 1, "2026-08-04": 1, "2026-08-05": 1, "2026-08-06": 1, "2026-08-10": 1, "2026-08-13": 1, "2026-08-19": 1, "2026-08-24": 1}                        0.683725                    29.850645                               72.844606

## Sector mapping/concentration diagnostics

Mapped-entry concentration only; unmapped symbols remain UNMAPPED and are excluded from mapped concentration.

                   Metric         Sector_Key       Value
  MAPPED_ACCEPTED_ENTRIES                      56.000000
UNMAPPED_ACCEPTED_ENTRIES                    1371.000000
 MAPPING_COVERAGE_PERCENT                       3.924317
       MAPPED_ENTRY_COUNT               AUTO    1.000000
       MAPPED_ENTRY_COUNT               BANK    8.000000
       MAPPED_ENTRY_COUNT             ENERGY   12.000000
       MAPPED_ENTRY_COUNT FINANCIAL_SERVICES    1.000000
       MAPPED_ENTRY_COUNT               FMCG    9.000000
       MAPPED_ENTRY_COUNT     INFRASTRUCTURE   12.000000
       MAPPED_ENTRY_COUNT                 IT    4.000000
       MAPPED_ENTRY_COUNT              METAL    3.000000
       MAPPED_ENTRY_COUNT             PHARMA    6.000000
     UNMAPPED_ENTRY_COUNT           UNMAPPED 1371.000000

## Regime diagnostics

Regime labels are joined on the exact Signal_Date; diagnostics do not affect eligibility or mandatory gates.

  Regime  Completed_Trades  Gross_Mean_Return  Base_Net_Mean_Return  Base_Net_Return_PF
 RISK_ON               515           0.015950              0.011950            1.976107
   MIXED               456           0.008971              0.004971            1.322047
RISK_OFF               453           0.002275             -0.001725            0.926384

## Point-in-time and integrity audit

Persisted audit violation rows: 0. Numeric comparisons use np.isclose(rtol=1e-9, atol=1e-12); dates and integers use exact equality.

## Mandatory validation gates

                     Gate    Observed              Threshold  Pass  Mandatory
       SAMPLE_SUFFICIENCY 1424.000000                 >= 300  True       True
         GROSS_SETUP_MEAN    0.009365                    > 0  True       True
      BASE_NET_SETUP_MEAN    0.005365               >= 0.002  True       True
        BASE_NET_SETUP_PF    1.318914                >= 1.20  True       True
    STRESS_NET_SETUP_MEAN    0.003365                    > 0  True       True
      STRESS_NET_SETUP_PF    1.189210                 > 1.00  True       True
    BASE_PRACTICAL_MEAN_R   -0.304960                >= 0.15 False       True
      BASE_PRACTICAL_R_PF    0.715036                >= 1.20 False       True
       CONTROL_GROSS_MEAN    0.009365     > high-volume mean False       True
         CONTROL_GROSS_PF    1.623417       > high-volume PF  True       True
 TEMPORAL_FIRST_HALF_MEAN    0.007061                    > 0  True       True
   TEMPORAL_FIRST_HALF_PF    1.381072                  > 1.0  True       True
TEMPORAL_SECOND_HALF_MEAN    0.003494                    > 0  True       True
  TEMPORAL_SECOND_HALF_PF    1.233852                  > 1.0  True       True
    TOP_FIVE_REMOVED_MEAN    0.004656                    > 0  True       True
      TOP_FIVE_REMOVED_PF    1.275812                  > 1.0  True       True
            LOSO_ALL_MEAN    0.005151   > 0 for every symbol  True       True
              LOSO_ALL_PF    1.305577 > 1.0 for every symbol  True       True
           INTEGRITY_ZERO    0.000000                   == 0  True       True

## Artifact inventory

The accompanying CSV artifacts contain feature validation, shock cohorts, entries/cancellations, setup/practical/control outcomes, forward diagnostics, validation metrics, temporal/outlier/LOSO/control/bootstrap summaries, overlap/capacity, sector, regime, and PIT diagnostics, validation gates, and this report.

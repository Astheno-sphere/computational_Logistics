# State-Only Fallback Geo Summary

- input rows: 893

## Classification Counts

- `runtime_missed_county_containment`: 542
- `outside_state_but_near_claimed_state_county`: 157
- `no_county_bank_for_state`: 79
- `inside_state_near_county_edge`: 51
- `zero_zero_bad_source_point`: 29
- `inside_state_far_from_any_county`: 28
- `outside_claimed_state_far_away`: 6
- `missing_state_geometry`: 1

## Top State Splits

```
geo_classification                           state
runtime_missed_county_containment            NY       100
                                             FL        65
                                             HI        63
                                             CA        62
no_county_bank_for_state                     AS        55
runtime_missed_county_containment            NJ        49
                                             WA        45
                                             PR        31
outside_state_but_near_claimed_state_county  NY        26
zero_zero_bad_source_point                   CA        24
runtime_missed_county_containment            OR        24
outside_state_but_near_claimed_state_county  FL        22
runtime_missed_county_containment            MA        21
                                             ME        20
outside_state_but_near_claimed_state_county  WA        19
                                             ME        14
                                             CA        13
runtime_missed_county_containment            TX        13
                                             MD        12
no_county_bank_for_state                     VI        10
```

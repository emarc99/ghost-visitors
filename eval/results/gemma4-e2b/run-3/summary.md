# Eval: gemma4:e2b

| | Gemma alone | Gemma + guard |
| --- | --- | --- |
| Planted problems found (of 7) | 7 | 7 |
| False alarms (kinds not planted) | 4 | 0 |
| Claims with no matching measurement | 4 | 0 by construction |
| Complaints about the fixed site | 5 | 1 |

Ghosts that said they succeeded but never reached the confirmation page: 0

| Site | Ghost | Outcome | Reached /thanks | Found (alone) | Found (guard) | False (alone) | Steps | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| broken | marisol | succeeded | yes | horizontal_scroll, slow_load, small_tap_target | horizontal_scroll, slow_load, small_tap_target | - | 8 | 188.5 |
| broken | tomas | ran_out_of_steps | no | not_keyboard_reachable, unnamed_control | not_keyboard_reachable, unnamed_control | - | 16 | 401.6 |
| broken | rosa | succeeded | yes | low_contrast, small_text | low_contrast, small_text | - | 9 | 211.6 |
| fixed | marisol | succeeded | yes | - | - | horizontal_scroll, small_tap_target | 7 | 150.4 |
| fixed | tomas | ran_out_of_steps | no | - | - | - | 16 | 352.6 |
| fixed | rosa | succeeded | yes | - | - | small_tap_target, small_text | 8 | 207.5 |

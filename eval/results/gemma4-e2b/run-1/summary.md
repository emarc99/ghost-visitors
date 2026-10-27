# Eval: gemma4:e2b

| | Gemma alone | Gemma + guard |
| --- | --- | --- |
| Planted problems found (of 7) | 7 | 7 |
| False alarms (kinds not planted) | 3 | 1 |
| Claims with no matching measurement | 2 | 0 by construction |
| Complaints about the fixed site | 4 | 1 |

Ghosts that said they succeeded but never reached the confirmation page: 0

| Site | Ghost | Outcome | Reached /thanks | Found (alone) | Found (guard) | False (alone) | Steps | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| broken | marisol | succeeded | yes | horizontal_scroll, slow_load, small_tap_target | horizontal_scroll, slow_load, small_tap_target | - | 8 | 182.6 |
| broken | tomas | ran_out_of_steps | no | not_keyboard_reachable, unnamed_control | not_keyboard_reachable, unnamed_control | - | 16 | 410.2 |
| broken | rosa | succeeded | yes | low_contrast, small_text | low_contrast, small_text | - | 11 | 249.6 |
| fixed | marisol | succeeded | yes | - | - | small_tap_target | 6 | 147.2 |
| fixed | tomas | ran_out_of_steps | no | - | - | - | 16 | 412.1 |
| fixed | rosa | succeeded | yes | - | - | low_contrast, small_text | 8 | 182.8 |

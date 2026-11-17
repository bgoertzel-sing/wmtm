status=ok canary_ok=True neg_proved=False goals=42 proved=36 timeouts=0 add_fail=0 pred_fail=0 steps=30

| case | note implication (vars kept / skolems inside) | note-impl goal | asked | proved | STV | proof |
|---|---|---|---|---|---|---|
| C1_anything_X_is_Y | none (no Implication atom) | no | (Member sk_lute_1@01 quiet) | no | - | - |
| C1_anything_X_is_Y | none (no Implication atom) | no | (Member sk_lute_1@01 thing__member_acoustic) | no | - | - |
| C2_every_A_that_B_is_C | Implication vars=$e,$x sk=- goals=1 | yes | (Member tweety happy) | yes | [1.0, 0.8919] | (: (by s1_r1_implication@02 (conjunction s2_c1_member@02 s2_v1_member@02 s2_v1_agent@02)) (Member tweety happy) (STV 1.0 0.891889659763245)) |
| C3_if_someone_V_they_are_W | Implication vars=$e,$x sk=sk_drum_1@03,sk_they_1@03 goals=0 | no | (Member marta loud) | no | - | - |
| C3_if_someone_V_they_are_W | Implication vars=$e,$x sk=sk_drum_1@03,sk_they_1@03 goals=0 | no | (Member sk_they_1@03 loud) | yes | [0.9, 0.0314] | (: (by s1_r1_implication@03 (conjunction s2_v1_member@03 s2_v1_agent@03 (by coref_patient (conjunction s2_c1_coref@03 s2_v1_patient@03)))) (Member sk_they_1@03 loud) (STV 0.9 0.03140673444967913)) |
| C4_two_premise_conjunction | Implication vars=$x sk=- goals=0; Implication vars=$s,$s2,$x sk=sk_ball@04 goals=0 | no | (Member sk_toy_1@04 ball) | no | - | - |
| C5_negated_conclusion | Implication vars=$x sk=- goals=0; Implication vars=$s,$x sk=sk_liquid@05 goals=0 | no | (Member sk_pond_1@05 liquid) | no | - | - |
| C6_near_miss_other_class | none (no Implication atom) | no | (Member sk_trumpet_1@06 quiet) | no | - | - |

note_impl stats: {"note_impl": 6, "ground": 0, "with_vars": 6, "bi": 0, "and_premise": 6, "premise_in_kb": 1, "premise_missing": 5, "concl_not_ground": 0, "cross_note": 0, "concl_stated": 0, "dup_goal": 0, "goals": 1, "impl_with_goal": 1}

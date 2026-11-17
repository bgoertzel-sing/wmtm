# Lowered atoms (invented notes; master_loader.plan, sph 24e37182 lower.py master target, PR 43 a70dc86)

Note suffix in labels/skolems: __ep_note_20991117T0000NNZ = case NN.  Statement order as loaded.

## C1_anything_X_is_Y

Text: Anything acoustic is quiet. The lute is acoustic.

```
(: s1_k1_inheritance__ep_note_20991117T000001Z (Inheritance thing__member_acoustic quiet) (STV 0.9 0.7))
(: s2_x1_member__ep_note_20991117T000001Z (Member sk_lute_1__ep_note_20991117T000001Z lute) (STV 1.0 0.99))
(: s2_c1_member__ep_note_20991117T000001Z (Member sk_lute_1__ep_note_20991117T000001Z acoustic) (STV 1.0 0.99))
```

- no Implication atom in this note

## C2_every_A_that_B_is_C

Text: Every bird that sings is happy. Tweety is a bird that sings.

```
(: s1_r1_implication__ep_note_20991117T000002Z (Implication (And (Member $x bird) (Member $e sing) (Agent $e $x)) (Member $x happy)) (STV 1.0 0.9))
(: s2_n1_name__ep_note_20991117T000002Z (Name tweety "Tweety") (STV 1.0 0.99))
(: s2_c1_member__ep_note_20991117T000002Z (Member tweety bird) (STV 1.0 0.99))
(: s2_v1_member__ep_note_20991117T000002Z (Member sk_sing_2__ep_note_20991117T000002Z sing) (STV 1.0 0.99))
(: s2_v1_agent__ep_note_20991117T000002Z (Agent sk_sing_2__ep_note_20991117T000002Z tweety) (STV 1.0 0.99))
(: s2_h1_habitual__ep_note_20991117T000002Z (Habitual sk_sing_2__ep_note_20991117T000002Z) (STV 1.0 0.99))
```

- note implication `s1_r1_implication__ep_note_20991117T000002Z`: Implication, variables ['$e', '$x'], skolem constants inside none, note-impl goals ['(Member tweety happy)'], {'premise_in_kb': 1}

## C3_if_someone_V_they_are_W

Text: If someone plays the drum, they are loud. Marta plays the drum.

```
(: s1_x1_member__ep_note_20991117T000003Z (Member sk_person_1__ep_note_20991117T000003Z person) (STV 1.0 0.99))
(: s1_x2_member__ep_note_20991117T000003Z (Member sk_drum_1__ep_note_20991117T000003Z drum) (STV 1.0 0.99))
(: s1_r1_implication__ep_note_20991117T000003Z (Implication (And (Member $e play) (Agent $e $x) (Patient $e sk_drum_1__ep_note_20991117T000003Z)) (Member sk_they_1__ep_note_20991117T000003Z loud)) (STV 1.0 0.9))
(: s1_k1_coref__ep_note_20991117T000003Z (Coref sk_they_1__ep_note_20991117T000003Z sk_person_1__ep_note_20991117T000003Z) (STV 0.99 0.9))
(: s2_n1_name__ep_note_20991117T000003Z (Name marta "Marta") (STV 1.0 0.99))
(: s2_x1_member__ep_note_20991117T000003Z (Member sk_drum_2__ep_note_20991117T000003Z drum) (STV 1.0 0.99))
(: s2_v1_member__ep_note_20991117T000003Z (Member sk_play_2__ep_note_20991117T000003Z play) (STV 1.0 0.99))
(: s2_v1_agent__ep_note_20991117T000003Z (Agent sk_play_2__ep_note_20991117T000003Z marta) (STV 1.0 0.99))
(: s2_v1_patient__ep_note_20991117T000003Z (Patient sk_play_2__ep_note_20991117T000003Z sk_drum_2__ep_note_20991117T000003Z) (STV 1.0 0.99))
(: s2_h1_habitual__ep_note_20991117T000003Z (Habitual sk_play_2__ep_note_20991117T000003Z) (STV 1.0 0.99))
(: s2_c1_coref__ep_note_20991117T000003Z (Coref sk_drum_2__ep_note_20991117T000003Z sk_drum_1__ep_note_20991117T000003Z) (STV 0.8 0.9))
```

- note implication `s1_r1_implication__ep_note_20991117T000003Z`: Implication, variables ['$e', '$x'], skolem constants inside ['sk_drum_1__ep_note_20991117T000003Z', 'sk_they_1__ep_note_20991117T000003Z'], note-impl goals none, {'premise_missing': 1}

## C4_two_premise_conjunction

Text: Anything that is red and round is a ball. The toy is red. The toy is round.

```
(: s1_r1_implication__ep_note_20991117T000004Z (Implication (And (Member $x thing) (Member $x red) (Member $x round)) (Member $x ball)) (STV 0.9 0.7))
(: s1_r1_implication_2__ep_note_20991117T000004Z (Implication (And (Member $x thing) (Holds $s (Member $x red)) (Holds $s2 (Member $x round))) (And (Holds (sk_ball__ep_note_20991117T000004Z $x $s $s2) (Member $x ball)) (During (sk_ball__ep_note_20991117T000004Z $x $s $s2) $s) (During (sk_ball__ep_note_20991117T000004Z $x $s $s2) $s2))) (STV 0.9 0.7))
(: s2_x1_member__ep_note_20991117T000004Z (Member sk_toy_1__ep_note_20991117T000004Z toy) (STV 1.0 0.99))
(: s2_c1_member__ep_note_20991117T000004Z (Member sk_toy_1__ep_note_20991117T000004Z red) (STV 1.0 0.99))
(: s3_x1_member__ep_note_20991117T000004Z (Member sk_toy_2__ep_note_20991117T000004Z toy) (STV 1.0 0.99))
(: s3_c1_coref__ep_note_20991117T000004Z (Coref sk_toy_2__ep_note_20991117T000004Z sk_toy_1__ep_note_20991117T000004Z) (STV 0.99 0.9))
(: s3_c2_member__ep_note_20991117T000004Z (Member sk_toy_2__ep_note_20991117T000004Z round) (STV 1.0 0.99))
```

- note implication `s1_r1_implication__ep_note_20991117T000004Z`: Implication, variables ['$x'], skolem constants inside none, note-impl goals none, {'premise_missing': 1}
- note implication `s1_r1_implication_2__ep_note_20991117T000004Z`: Implication, variables ['$s', '$s2', '$x'], skolem constants inside ['sk_ball__ep_note_20991117T000004Z'], note-impl goals none, {'premise_missing': 1}

## C5_negated_conclusion

Text: Anything frozen is not liquid. The pond is frozen.

```
(: s1_r1_implication__ep_note_20991117T000005Z (Implication (And (Member $x thing) (Member $x frozen)) (Not (Member $x liquid))) (STV 1.0 0.9))
(: s1_r1_implication_2__ep_note_20991117T000005Z (Implication (And (Member $x thing) (Holds $s (Member $x frozen))) (Not (And (Holds (sk_liquid__ep_note_20991117T000005Z $x $s) (Member $x liquid)) (During (sk_liquid__ep_note_20991117T000005Z $x $s) $s)))) (STV 1.0 0.9))
(: s2_x1_member__ep_note_20991117T000005Z (Member sk_pond_1__ep_note_20991117T000005Z pond) (STV 1.0 0.99))
(: s2_c1_member__ep_note_20991117T000005Z (Member sk_pond_1__ep_note_20991117T000005Z frozen) (STV 1.0 0.99))
```

- note implication `s1_r1_implication__ep_note_20991117T000005Z`: Implication, variables ['$x'], skolem constants inside none, note-impl goals none, {'premise_missing': 1}
- note implication `s1_r1_implication_2__ep_note_20991117T000005Z`: Implication, variables ['$s', '$x'], skolem constants inside ['sk_liquid__ep_note_20991117T000005Z'], note-impl goals none, {'premise_missing': 1}

## C6_near_miss_other_class

Text: Anything acoustic is quiet. The trumpet is metallic.

```
(: s1_k1_inheritance__ep_note_20991117T000006Z (Inheritance thing__member_acoustic quiet) (STV 0.9 0.7))
(: s2_x1_member__ep_note_20991117T000006Z (Member sk_trumpet_1__ep_note_20991117T000006Z trumpet) (STV 1.0 0.99))
(: s2_c1_member__ep_note_20991117T000006Z (Member sk_trumpet_1__ep_note_20991117T000006Z metallic) (STV 1.0 0.99))
```

- no Implication atom in this note

## Narrowed-class definitions loaded (shared, no note suffix)

```
(: kind__thing__member_acoustic (Inheritance thing__member_acoustic thing) (STV 1.0 0.99))
(: by_1__thing__member_acoustic (NarrowBy thing__member_acoustic (Is acoustic)) (STV 1.0 0.99))
```

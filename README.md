# fluid-router2

A six-instruction dispatch that routes a **content-bearing bug** to its repair, and
repairs it to a fixpoint.

A content-bearing bug is one where the code **runs**, **returns a number**, and the
**number is wrong**. No crash, no exception, no stack trace. Nothing in a traceback
finds it, because nothing went wrong at the language level — the answer is just
not the answer.

Every expression here was authored by a synthesis engine in **0.35 seconds** total.
None of it was written by hand.

```
  dispatch         256 states   0 wrong
  replay            25 steps    0 wrong   across 16 held-out jobs
  termination      256 states   0 that ADVANCE fails to reduce
  1.55 ns per decision
```

## The law

Six lanes. One per class, each mapping an observation bit to a priority slot.

| slot | class | the observation a body measures | verdict |
|---|---|---|---|
| 0 | `NOPROGRESS` | the last repair did not move the mask | **minimal in D∩I** |
| 1 | `DEGENERATE` | the posed targets take one value | forced `+`-join |
| 2 | `TRUNCATED` | exact on the posed domain, wrong on the real one | forced `-`-join |
| 3 | `EVALUATOR` | grader semantics differ from the machine's on this data | forced `-`-join |
| 4 | `FOLDED` | the harness scores a right and a wrong implementation the same | forced `+`-join |
| 5 | `CIRCULAR` | the posed observation equals the target | forced `-`-join |

```c
LANE0(x)  x >> 7                                  /* 1 op,  minimal in D∩I */
LANE1(x)  (1 & (x >> 6)) + (1 & (x >> 6))
LANE2(x)  ((x >> 5) << 2) - ((x >> 6) << 3)
LANE3(x)  ((x >> 4) << 3) - ((x >> 5) << 4)
LANE4(x)  (x & (1 << 3)) + (x & (1 << 3))
LANE5(x)  ((x >> 2) << 5) - ((x >> 3) << 6)
```

Slot 0 is the engine being sharper than the obvious. A hand-written version would
mask — `1 & (x >> 7)`. The engine dropped the mask, because bit 7 is the top of the
posed domain and the shift alone is already 0 or 1. One instruction, and the only
one it proved minimal.

## The core it runs on

Three expressions, authored earlier for a completely different question — *which
token do I write next* — and **unchanged** since:

```c
EMIT(m)     m & (-m)                        /* the lowest live bit: which fault to handle */
ADVANCE(m)  m - (m & (-m))                  /* clear it and keep going */
HALT(m)     (m - (m - 1)) + ((-m) >> 31)    /* nothing left */
```

This is their sixth domain. The others: writing a token sequence, HTTP admission,
the synthesis loop itself, candidate discovery, and bug classification. The
dispatch has never been edited for any of them.

`ADVANCE` is why this is a solver and not a classifier: it strictly reduces a live
mask, which is what makes the repair loop terminate. The verifier checks that on
all 256 states.

## Solving, not naming

```
measure -> EMIT names the slot -> apply the repair -> RE-MEASURE -> until HALT
```

`SOLVED` is not "named correctly". It means the run that was wrong became right:
the final law is **exact on the real domain**, under **machine semantics**, with a
harness that can actually tell a correct implementation from a wrong one.

## Results — 16 held-out jobs

Every job is a **different instance** of the classes, in a **different domain**, and
the law had never seen any of them. Every observation bit is **measured by running
the job** — nothing is labelled by hand. The law never sees the truth column.

```
job                          truth                    what the law did             outcome
parity, posed even           DEGENERATE               DEGENERATE                   SOLVED
half-flag, posed 0..127      DEGENERATE+TRUNCATED     DEGENERATE                   SOLVED
nibble bit, posed 0..31      TRUNCATED                TRUNCATED                    SOLVED
x<<24 graded in python       EVALUATOR                EVALUATOR                    SOLVED
scramble, xor harness        FOLDED                   FOLDED                       SOLVED
predict x from x             CIRCULAR                 CIRCULAR                     DEAD
x<<24, posed 0..127          CLEAN                    CLEAN, no repair             SOLVED
nibble 0..31 + xor harness   TRUNCATED+FOLDED         TRUNCATED -> FOLDED          SOLVED
lowest set bit, clean        CLEAN                    CLEAN, no repair             SOLVED
complement, clean            CLEAN                    CLEAN, no repair             SOLVED
bit 3, clean                 CLEAN                    CLEAN, no repair             SOLVED
add one, clean               CLEAN                    CLEAN, no repair             SOLVED
flaky reference              NO SLOT: nondeterministic DEGENERATE -> NOPROGRESS    ABANDONED
starved material             NO SLOT: lean material   CLEAN, no repair             not solved
16-bit, clean                CLEAN                    CLEAN, no repair             SOLVED
16-bit, truncated            DEGENERATE+TRUNCATED     DEGENERATE                   SOLVED

solved 13 of 16    abandoned 1    unsalvageable 1    false alarms on clean 0   [17.0 s]
```

Three things in that table are worth more than the score.

**It iterates.** `nibble 0..31 + xor harness` carries two independent faults. The
law handles `TRUNCATED`, re-measures, finds `FOLDED` still live, handles that, and
halts. Two rounds, driven by `ADVANCE`.

**It ports across data size.** The two 16-bit jobs run on the same lanes, untouched.
The law reads observation bits, not data — so the width of the thing being debugged
never reaches it.

**It disagreed with the labels twice and was right twice.** `half-flag posed
0..127` was labelled truncated; the mask showed `DEGENERATE,TRUNCATED`, because
posing only 0..127 makes the target all-zero — degenerate is the sharper
diagnosis, and one widen cleared both. `x<<24 posed 0..127` was labelled a two-bug
job; the mask was `00000` and that was correct: `127 << 24` does not overflow, and
`(x << 24)` extrapolates to the full domain exactly.

## What it cannot do

Stated because it was measured, not because it is a caveat.

- **`CIRCULAR` is named, never repaired.** `predict x from x` comes back `DEAD`.
  Drop the feature and there is nothing left. Diagnosis is not repair.
- **A class with no slot used to loop forever.** Given a nondeterministic reference,
  the law named the nearest thing it had — `DEGENERATE` — repaired, measured the
  identical mask, and did that until the round cap. Then it printed a grade, which
  was meaningless, because the reference is not a function. `NOPROGRESS` is the fix:
  *the repair I myself chose changed nothing, so the fault is not the one I named.*
  It now `ABANDON`s. That is a **guard, not a diagnosis** — it says "not in this
  taxonomy", never what is actually wrong.
- **Starved material still reads `CLEAN`.** No law is authored, so nothing false is
  claimed, but the fault cannot be named. Closing it means supplying the engine's
  own `starved` event as a seventh observation.
- **It finds nothing on its own.** It routes observations a body has already made.
  Deciding to check a result against an independent evaluator, or to verify outside
  the posed domain, is still the body's job. The brain names the class; the body
  gathers what it needs to be named.

## Run it

No dependencies. Re-checks the dispatch exhaustively and replays every recorded
step of all 16 jobs:

```bash
cc -O2 -o checklaws verify/verify.c && ./checklaws
```

To re-author the laws from supply, or to re-run the 16 jobs, you need the synthesis
engine, which is proprietary and **not in this repository**. Both scripts exit
cleanly without it:

```bash
SPHERE_ENGINE=/path/to/engine python3 author/author.py
SPHERE_ENGINE=/path/to/engine python3 solve/solve.py
```

## Layout

```
law/law.json        the six authored lanes, their verdicts, EMIT/ADVANCE/HALT
author/author.py    re-authors every lane from supply alone
solve/solve.py      the 16 held-out jobs, every observation measured by running
traces/traces.json  the observation trace of each job, as recorded
verify/verify.c     generated, no dependencies
verify/gen.py       generates verify.c from law.json and traces.json
results/            captured output of both runs
```

`verify.c` is generated, never hand-transcribed — copying six expressions and
sixteen traces into another language by hand is the exact step that produces a
verifier which checks the wrong thing.

## What was supplied and what was authored

**Supplied:** that six classes exist, which observation bit carries each, the order
they must be handled in, and the repairs a body can perform.

**Authored:** every expression in `law/law.json`, and every verdict beside it.

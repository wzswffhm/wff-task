# LabelX Annotation Rules Index

Read the task's supplied rules document as the authority. Use this index to navigate its four review stages.

## Stage 1: Input Quality

| Label | Use for |
| --- | --- |
| I1 | Ambiguous or incomplete instruction |
| I2 | Low real-world office value / obviously artificial task |
| I3 | Referenced input resource missing or inaccessible |
| I4 | Rubric misses core requirements or only checks surface form |
| I5 | Rubric cannot distinguish good and poor outputs |
| I6 | Unreasonable weights or unclear scoring triggers |
| I7 | Rubric is fabricated, irrelevant, or needs reconstruction |
| I8 | Rubric hard-codes a non-unique solution path |

## Stage 2: Trajectory Quality

| Label | Use for |
| --- | --- |
| P1 | Starts execution before understanding environment/materials |
| P2 | Skips a required analysis or execution step |
| P3 | Repeats the same failed approach three or more times |
| P4 | Uses five or more divergent attempts without convergence |
| P5 | Fails to verify the generated result |
| P6 | Makes a domain/professional judgment error |
| P7 | More than 30% of calls are unrelated to the task |

## Stage 3: Output Quality

| Label | Use for |
| --- | --- |
| A1 | Required deliverable or required content is missing |
| A2 | File is unopenable, damaged, empty, or unusable |
| A3 | Required section, sheet, structure, or header is wrong/missing |
| A4 | Layout or formatting is visibly poor |
| A5 | Domain/professional information is wrong |
| A6 | Basic fact, calculation, reference, or hallucination is wrong |
| A7 | Content is mostly template language or low-information filler |
| A8 | Output misuses, contradicts, or cannot trace cited input material |

## Stage 4: Evaluation Credibility

| Label | Use for |
| --- | --- |
| E1 | Automatic score conflicts with actual quality |
| E2 | Judge is easy to mislead by style, verbosity, or confidence |
| E3 | Surface compliance obtains a score without solving the task |
| E4 | Keyword matching ignores meaningful context |
| E5 | Required terms are accepted anywhere rather than required location |
| E6 | Skeleton/format passes while content is empty or junk |
| E7 | Output appears to fit a Judge-favored generic template |

## Attribution

- Prefer `Data` when Stage 1 has a material defect.
- Prefer `Model` when inputs are sound but execution or output is faulty.
- Prefer `Judge` when rubric design and scoring cause the mismatch.
- Prefer `Environment` when execution is blocked by a real runtime/dependency restriction.

## Notes

- The source document contains a later Stage 3 flow diagram with mismatched A-label descriptions. Use the formal Stage 3 table above.
- Maintain the original scoring mode where possible. Make criteria atomic and tied to inspectable evidence.

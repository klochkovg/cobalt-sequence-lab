# Example dataset

## `input/messy.fasta`

17 synthetic records (random sequences, written for this project, MIT licensed), each with one
deliberate problem. "Detected" is what `cobalt validate` / `cobalt stats` report today.

| Record ID | Problem | Detected |
| --- | --- | --- |
| `clean_ref` | none, the baseline | passes |
| `lower_case` | all bases lowercase | uppercased by `normalize` |
| `mixed_case` | random mixed case | uppercased by `normalize` |
| `iupac_ambiguity` | scattered `N R Y K M S W` | `alphabetic_class` ambiguous, `ambiguity_fraction` 0.07 |
| `n_run` | 50 `N` in a row (scaffold gap) | ambiguous, `ambiguity_fraction` 0.38 |
| `invalid_chars` | `X * 1 J ?` inside DNA | `invalid_characters`: `* 1 ?` only, type `unknown` |
| `alignment_gaps` | `-` and `.` gap characters | `invalid_characters` (9), type `unknown` |
| `gi\|2765001\|gb\|AB000001.1\|AB000001` | NCBI-style pipe ID | not flagged; kept as is |
| `spaced_id` | repeated spaces and a tab in the description | not flagged; kept as is |
| `dup_id` (x2) | the same ID twice | `duplicate_id` |
| `empty_record` | header with no sequence | `empty_sequence` |
| `too_short` | 4 bases | not flagged (no minimum length rule) |
| `unwrapped` | 300 bases on one line | read fine; rewrapped by `normalize` |
| `ragged_wrap` | lines of 70, 15, 55, 10 bases | read fine; rewrapped by `normalize` |
| `rna_record` | RNA (`U`) among DNA records | type RNA |
| `protein_record` | protein among nucleotides, ends with `*` | `invalid_characters` (`*`), type `unknown` |

```bash
cobalt validate examples/input/messy.fasta --json
cobalt stats examples/input/messy.fasta
cobalt normalize examples/input/messy.fasta --fasta cleaned.fasta
```

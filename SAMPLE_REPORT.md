# Completeness checker — sample report

Run the tests from the repository root:

```bash
python3 -m unittest discover -s tests -v
```

Test run (2026-11-21, this PR):

```text
test_complete_listing ... ok
test_fixtures_file ... ok
test_input_is_not_modified ... ok
test_invalid_deadline ... ok
test_missing_and_blank_fields ... ok
test_missing_title_key_and_invalid_url ... ok
test_source_confirmed_no_deadline ... ok
test_source_confirmed_rolling_deadline ... ok
test_vague_deadline_spring ... ok

----------------------------------------------------------------------
Ran 9 tests in 0.002s

OK
```

Sample report, generated from the synthetic fixtures in
`fixtures/synthetic_listings.json`:

```text
COMPLETE: Synthetic Community Arts Grant - parsed_deadline=2027-03-04
NEEDS_REVIEW: (untitled) - needs attention: title, source_url, deadline
NEEDS_REVIEW: Synthetic Invalid Deadline Grant - needs attention: deadline
COMPLETE: Synthetic Rolling Opportunity - parsed_deadline=(none - rolling/no deadline)
NEEDS_REVIEW: Synthetic Vague Deadline Listing - needs attention: deadline
```

Notes:

- All fixtures are synthetic only.
- The vague-deadline case ("Spring 2027") returns NEEDS_REVIEW naming
  the `deadline` field, and its parsed date stays blank — no date is
  guessed or converted.
- Inputs are never modified.

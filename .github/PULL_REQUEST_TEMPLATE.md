## What changes

<!-- One or two sentences. Link the issue if there is one. -->

## Type

- [ ] Weight / threshold change (`scoring_config.json`)
- [ ] Formula / method change (`scoring.py`): bump `SCORING_VERSION` and the config `version`
- [ ] New data source or seed list (`run.py`, `hype_build.py`)
- [ ] Page / docs
- [ ] Bug fix

## Why it separates signal from noise better

<!-- The argument, not "project X moves up". -->

## eval.py output (required for any scoring change)

<details><summary>python eval.py</summary>

```
paste the full output here
```

</details>

## Checklist

- [ ] `python -m unittest discover tests` passes
- [ ] METHODOLOGY.md updated if a formula, weight or threshold changed
- [ ] No invented numbers: every new value comes from a source, missing stays `null` / —
- [ ] No caches, history, raw research, tokens or local paths committed

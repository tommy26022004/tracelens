# data/

Workspace for sample SME loan documents used during development and evaluation.

## Ordered development tests

`ordered_tests_v1/BAT_DAU_O_DAY.md` starts the numbered 01–16 test sequence. Each case includes Vietnamese instructions, independently authored expected values and an observation template. Upload only files inside the case's `upload/` folder. All system test statuses start as `not_run`; generation and fixture-integrity checks do not establish extraction accuracy.

The pack contains 24 PDF-named files, including one intentionally invalid file. Cases 01, 15 and 16 contain instructions/references rather than additional PDFs. Case 16 reuses the retained 32-PDF package. These controlled variants are development fixtures, not independent held-out evaluation data.

Recreate in a new output directory from `backend/` using `python scripts/generate_ordered_test_pack.py --help` for options. The generator refuses to overwrite an existing output directory.

## Existing large package

After the owner's cleanup request, `realistic_scenarios/realistic_01` is the retained 32-PDF package, including its manifest and ground-truth files. PDFs are organised in subfolders. The identical `realistic_01_upload_ready` copy and other generated sample/scenario packages were moved to the Windows Recycle Bin on 2026-09-30.

`source_documents` and `verification` were preserved: they contain source archives and previous verification evidence, not spare input packages. Existing benchmark reports are historical and may refer to removed packages. Scripts that expect `samples`, `scenarios` or other removed packages need those datasets regenerated or restored before use. Generator code was not removed.

```
data/
├── realistic_scenarios/realistic_01/  # retained 32-PDF input package
└── processed/    # parsed JSON, extracted figures, debug artefacts
```

**Do NOT commit real customer documents.** This folder is gitignored except for
the README. Use synthetic or properly anonymised samples only.

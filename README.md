# shsciencegroup-literature-skill

Codex skill for SH Science Group literature-base workflows.

This skill is currently intended **only for SH Science Group members** and is designed for the internal literature website:

https://literature.shsciencegroup.online

It helps Codex analyze local paper PDFs, detect whether the paper already exists in the SH Lab literature base, upload new PDFs, and write structured paper-analysis notes back to the website.

## Scope

This skill is not a general-purpose paper manager. It assumes access to the SH Science Group literature API and project permissions inherited by `literature.shsciencegroup.online`.

Supported workflows:

- Single-paper ingestion from a local PDF.
- Batch planning from a PDF directory.
- Batch planning from multiple explicit PDF paths.
- Duplicate detection by DOI, normalized title, original PDF filename, and stored PDF filename.
- Updating notes for an existing paper instead of uploading a duplicate PDF.
- Writing notes using the 12-section `paper-reading-zh` analysis structure.

## Requirements

- Codex with local skill support.
- Membership/access to SH Science Group literature system.
- A valid `user_token` for `literature.shsciencegroup.online`.
- Python 3.10+.
- Optional but recommended: `pypdf`, used for DOI/title extraction from PDFs.

Do not commit or hard-code tokens. Provide tokens at runtime, or set:

```powershell
$env:SH_LITERATURE_TOKEN = "<user_token>"
```

## Installation

Clone or copy this folder into your Codex skills directory:

```text
C:\Users\<you>\.codex\skills\shsciencegroup-literature-skill
```

Then restart Codex so the skill metadata is reloaded.

## Usage

Single paper:

```text
文献入库 <课题ID> <PDF绝对路径>
```

Example:

```text
文献入库 B02 "D:\科研\papers\example.pdf"
```

Batch directory:

```text
文献批量入库 <课题ID> <PDF目录绝对路径>
```

Batch explicit paths:

```text
文献批量入库 <课题ID> <PDF绝对路径1> <PDF绝对路径2>
```

## Workflow

The skill follows a conservative write path:

1. Parse project ID and PDF input.
2. Validate local PDF paths.
3. Validate token with `/api/me`.
4. Validate project access with `/api/projects`.
5. Detect whether each paper already exists in the target project.
6. Generate paper notes using the `paper-reading-zh` structure.
7. Ask for explicit confirmation.
8. Upload new PDFs or update notes for existing papers.
9. Re-read the library after write operations for verification.

Single-paper confirmation phrase:

```text
确认入库
```

Batch confirmation phrase:

```text
确认批量入库
```

## Helper Script

The deterministic API operations are implemented in:

```text
scripts/literature_base_upload.py
```

Common commands:

```powershell
python scripts/literature_base_upload.py check --project-id B02 --token "<token>"
python scripts/literature_base_upload.py find-existing --project-id B02 --pdf "D:\path\paper.pdf" --token "<token>"
python scripts/literature_base_upload.py plan-batch --project-id B02 --pdf-dir "D:\path\papers" --token "<token>"
python scripts/literature_base_upload.py plan-batch --project-id B02 --pdf "D:\path\a.pdf" --pdf "D:\path\b.pdf" --token "<token>"
python scripts/literature_base_upload.py upload --project-id B02 --pdf "D:\path\paper.pdf" --notes-file "D:\path\notes.txt" --token "<token>"
python scripts/literature_base_upload.py update-notes --project-id B02 --item-id "<item_id>" --notes-file "D:\path\notes.txt" --token "<token>"
```

## Safety Notes

- The skill does not upload or update anything until the user explicitly confirms.
- Existing papers are updated by notes only; duplicate PDFs are avoided.
- Ambiguous duplicate matches are skipped until a user selects the correct item.
- Tokens should be treated as secrets and must not be stored in the repository.

## Tests

Run local tests:

```powershell
python tests\test_batch_inputs.py
python -m py_compile scripts\literature_base_upload.py tests\test_batch_inputs.py
```

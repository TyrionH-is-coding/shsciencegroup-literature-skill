---
name: shsciencegroup-literature-skill
description: >
  Use shsciencegroup-literature-skill when the user asks to archive a paper into the SH Lab literature
  base, especially with the trigger phrase "文献入库 <课题ID> <PDF绝对路径>" or
  similar requests to analyze a paper PDF, upload it to
  https://literature.shsciencegroup.online/, and write the paper analysis into
  the notes field. This workflow must validate the user token and project
  permission before doing any PDF analysis. If the paper is already in the
  library, update notes only instead of uploading again.
---

# shsciencegroup-literature-skill

## Trigger

Use this skill for single-paper commands in this form:

```text
文献入库 <课题ID> <PDF绝对路径>
```

Examples:

```text
文献入库 M1 D:\科研\papers\example.pdf
文献入库 A03 "D:\科研\my papers\paper with spaces.pdf"
```

Use this skill for batch commands in either directory mode or multi-path mode:

```text
文献批量入库 <课题ID> <PDF目录绝对路径>
文献批量入库 <课题ID> <PDF绝对路径1> <PDF绝对路径2> ...
```

Examples:

```text
文献批量入库 B02 "D:\科研\papers\APS mechanism"
文献批量入库 B02 "D:\科研\papers\a.pdf" "D:\科研\papers\b.pdf"
```

`<课题ID>` is the SH Lab literature project id. `<PDF绝对路径>` must point to a local PDF file. For batch mode, the input can be one PDF directory, multiple PDF paths, or a combination of both.

## Required Order

For a single paper, always follow this order. Do not analyze the PDF until token, project access, and duplicate detection pass.

1. Parse the project id and absolute PDF path from the user command.
2. Verify the PDF path exists, is a file, and has a `.pdf` extension.
3. Get the literature token:
   - Prefer environment variable `SH_LITERATURE_TOKEN`.
   - If missing, ask the user for either the raw `user_token` or a literature/dashboard URL containing `user_token=...`.
   - Do not save the token unless the user explicitly asks.
4. Run the helper script in `check` mode to validate:
   - `GET https://literature.shsciencegroup.online/api/me`
   - `GET https://literature.shsciencegroup.online/api/projects`
   - target project id is visible to the token.
5. Run the helper script in `find-existing` mode to check whether this paper is already in the project library.
   - Match by DOI exact match first.
   - Then match by normalized title similarity, with Greek beta/hyphen variants normalized.
   - Also match exact local PDF basename against item `pdf_original_name` and `pdf_filename`.
   - If one existing item is found, continue with notes-update mode and do not upload the PDF again.
   - If no existing item is found, continue with upload mode.
   - If multiple existing items are found, stop and ask the user which item should receive the notes.
6. After access validation and duplicate check pass, analyze the PDF by following `paper-reading-zh` strictly.
7. Save the full `paper-reading-zh` analysis locally if it is long, then create the notes text.
8. Show a confirmation to the user and wait for the exact approval phrase:

```text
确认入库
```

For an already-uploaded paper, make the confirmation explicit:

```text
该文献已存在，将只补充/更新备注，不重复上传 PDF。回复“确认入库”后执行。
```

9. If no existing item was found, run the helper script in `upload` mode with the PDF and notes.
10. If an existing item was found, run the helper script in `update-notes` mode with the item id and notes.
11. Run the helper script in `check-library` mode to verify the library can be read after the operation.
12. Report the project id, PDF filename, operation type (`uploaded` or `notes_updated`), item id if known, and any caveats.

## Batch Required Order

For `文献批量入库`, do not analyze any PDF until the batch plan has been generated.

1. Parse the project id and batch inputs.
   - Directory mode: scan direct child `.pdf` files by default.
   - Multi-path mode: accept multiple quoted absolute PDF paths.
   - A command may combine `--pdf-dir` and `--pdf` inputs internally.
2. Verify token and project access once with `check`.
3. Run `plan-batch` to collect PDFs, extract DOI/title, and check duplicates against the project library.
4. Show the batch plan to the user before analysis:
   - `upload`: paper not found in library; needs PDF upload and notes.
   - `update-notes`: paper already exists; update notes only.
   - `ambiguous`: multiple matches; skip until the user selects an item id.
   - `error`: invalid path or unreadable PDF; skip and report.
5. Ask for the exact approval phrase:

```text
确认批量入库
```

6. After approval, process only `upload` and `update-notes` entries one by one.
7. For every processed PDF, generate notes using the 12-section `paper-reading-zh` structure.
8. Execute each item independently and keep going after per-item failures unless the failure is token/project-wide.
9. At the end, run `check-library` and report a table of uploaded, notes-updated, skipped, and failed papers.

## Analysis And Notes Format

The analysis content must follow the installed `paper-reading-zh` rules, not a custom short summary. Use the paper full text, not only the abstract.

Required notes structure:

```text
【Codex 文献分析】
入库时间：YYYY-MM-DD HH:mm

1. 研究问题与重要性
...

2. 前人工作与不足
...

3. 重建作者的思考路径
...

4. 核心 Intuition
...

5. 具体方法与完整 Pipeline
...

6. 核心数学推导（无则说明并跳过）
...

7. 实验设计与结论
...

8. Take-aways
...

9. 最脆弱的假设
...

10. 最小复现实验
...

11. 最强反例设计
...

12. Follow-up Research Idea
...
```

If the web notes field would become too long, keep all 12 headings and write dense paragraphs under each heading. Do not collapse the notes into a five-part abstract-style summary unless the user explicitly asks for a short note.

## Helper Script

Use `scripts/literature_base_upload.py` for shsciencegroup-literature-skill API operations:

```powershell
python scripts/literature_base_upload.py check --project-id M1 --token "<token>"
python scripts/literature_base_upload.py find-existing --project-id M1 --pdf "D:\path\paper.pdf" --token "<token>"
python scripts/literature_base_upload.py plan-batch --project-id M1 --pdf-dir "D:\path\papers" --token "<token>"
python scripts/literature_base_upload.py plan-batch --project-id M1 --pdf "D:\path\a.pdf" --pdf "D:\path\b.pdf" --token "<token>"
python scripts/literature_base_upload.py upload --project-id M1 --pdf "D:\path\paper.pdf" --notes-file "D:\path\notes.txt" --token "<token>"
python scripts/literature_base_upload.py update-notes --project-id M1 --item-id "<item_id>" --notes-file "D:\path\notes.txt" --token "<token>"
python scripts/literature_base_upload.py check-library --project-id M1 --token "<token>"
```

If `--token` is omitted, the script reads `SH_LITERATURE_TOKEN`.

## API Details

Base URL:

```text
https://literature.shsciencegroup.online
```

Known endpoints:

```text
GET   /api/me?user_token=...
GET   /api/projects?user_token=...
GET   /api/projects/{project_id}/library?user_token=...
POST  /api/projects/{project_id}/upload?user_token=...
PATCH /api/projects/{project_id}/items/{item_id}?user_token=...
```

Upload form fields:

```text
files       PDF file
category_id default "uncat"
notes       paper analysis notes
```

## Safety Rules

- Never upload before successful token and project validation.
- Never upload before the user replies `确认入库`.
- Before upload, always check for an existing paper by DOI, title similarity, `pdf_original_name`, and `pdf_filename`. If found, update notes only.
- In batch mode, do not process `ambiguous` or `error` entries without explicit user instruction.
- Do not invent a project id. If the project id is not visible in `/api/projects`, stop and report the visible project ids.
- If multiple existing matches are returned, stop and ask the user which item id should be updated.
- Do not continue if the PDF cannot be read or analyzed enough to produce meaningful notes.
- Do not expose the token in the final answer.



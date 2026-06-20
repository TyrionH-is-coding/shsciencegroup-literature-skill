# shsciencegroup-literature-skill

`shsciencegroup-literature-skill` 是面向 SH Science Group 文献库工作流的 Codex skill。

本 skill 目前**仅限 SH Science Group 成员使用**，专门用于组内文献库网站：

https://literature.shsciencegroup.online

它可以帮助 Codex 分析本地论文 PDF，判断文献是否已经存在于 SH Lab 文献库中，上传新 PDF，并把结构化文献分析写入网页文献条目的备注字段。

## 适用范围

本 skill 不是通用文献管理工具。它假设使用者拥有 SH Science Group 文献系统访问权限，并能使用 `literature.shsciencegroup.online` 的项目权限和 API。

当前支持的工作流：

- 从本地 PDF 进行单篇文献入库。
- 从 PDF 文件夹生成批量入库计划。
- 从多个明确 PDF 路径生成批量入库计划。
- 按 DOI、规范化标题、原始 PDF 文件名、系统保存 PDF 文件名查重。
- 已存在文献只更新备注，不重复上传 PDF。
- 按 `paper-reading-zh` 的 12 节结构生成文献分析备注。

## 使用要求

- Codex，并支持本地 skills。
- SH Science Group 文献系统成员权限。
- 有效的 `literature.shsciencegroup.online` `user_token`。
- Python 3.10 或以上。
- 可选但推荐安装 `pypdf`，用于从 PDF 提取 DOI 和标题。

不要把 token 提交到仓库，也不要硬编码 token。运行时提供 token，或临时设置环境变量：

```powershell
$env:SH_LITERATURE_TOKEN = "<user_token>"
```

## 安装

将本文件夹克隆或复制到 Codex skills 目录：

```text
C:\Users\<you>\.codex\skills\shsciencegroup-literature-skill
```

然后重启 Codex，使 skill 元数据重新加载。

## 使用方法

单篇文献：

```text
文献入库 <课题ID> <PDF绝对路径>
```

示例：

```text
文献入库 B02 "D:\科研\papers\example.pdf"
```

批量目录：

```text
文献批量入库 <课题ID> <PDF目录绝对路径>
```

批量多个 PDF 路径：

```text
文献批量入库 <课题ID> <PDF绝对路径1> <PDF绝对路径2>
```

## 工作流程

本 skill 采用保守写入流程：

1. 解析课题 ID 和 PDF 输入。
2. 校验本地 PDF 路径。
3. 通过 `/api/me` 校验 token。
4. 通过 `/api/projects` 校验课题访问权限。
5. 检查目标课题中是否已有同一篇文献。
6. 使用 `paper-reading-zh` 结构生成文献分析备注。
7. 要求用户明确确认。
8. 对新文献上传 PDF；对已存在文献只更新备注。
9. 写入后重新读取文献库进行校验。

单篇确认语：

```text
确认入库
```

批量确认语：

```text
确认批量入库
```

## 辅助脚本

确定性的 API 操作由以下脚本实现：

```text
scripts/literature_base_upload.py
```

常用命令：

```powershell
python scripts/literature_base_upload.py check --project-id B02 --token "<token>"
python scripts/literature_base_upload.py find-existing --project-id B02 --pdf "D:\path\paper.pdf" --token "<token>"
python scripts/literature_base_upload.py plan-batch --project-id B02 --pdf-dir "D:\path\papers" --token "<token>"
python scripts/literature_base_upload.py plan-batch --project-id B02 --pdf "D:\path\a.pdf" --pdf "D:\path\b.pdf" --token "<token>"
python scripts/literature_base_upload.py upload --project-id B02 --pdf "D:\path\paper.pdf" --notes-file "D:\path\notes.txt" --token "<token>"
python scripts/literature_base_upload.py update-notes --project-id B02 --item-id "<item_id>" --notes-file "D:\path\notes.txt" --token "<token>"
```

## 安全说明

- 用户明确确认前，本 skill 不会上传或更新网页内容。
- 已存在文献只更新备注，避免重复上传 PDF。
- 多重匹配的文献会跳过，直到用户指定正确的 item id。
- token 应视为敏感信息，不应存入仓库。

## 测试

运行本地测试：

```powershell
python tests\test_batch_inputs.py
python -m py_compile scripts\literature_base_upload.py tests\test_batch_inputs.py
```

---

## English Version

`shsciencegroup-literature-skill` is a Codex skill for SH Science Group literature-base workflows.

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

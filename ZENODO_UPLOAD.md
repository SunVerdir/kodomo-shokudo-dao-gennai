# Zenodo への投稿手順（このフォルダを使う）

査読前論文として投稿する。査読済みとは書かない。

## アップロードするファイル

必須:

1. `paper/WORKING_PAPER.md`（本文。PDF 化できる場合は PDF を主ファイルにし、Markdown を追加ファイルにする）
2. `paper/POLICY_BRIEF.md`
3. リポジトリ一式の ZIP（`.git` を除く）、または GitHub 公開後の Release アーカイブ

任意:

- `paper/zenodo-metadata.json` の内容を Web フォームへ転記（Zenodo は JSON の自動読込を保証しない）

## フォーム上の推奨値

| 項目 | 値 |
|---|---|
| Upload type | Publication |
| Publication type | Working paper |
| Language | Japanese |
| License（文書） | CC BY 4.0 |
| ORCID | 0009-0003-1371-5267 |
| Communities | 空でよい。政策コミュニティがあれば後から追加 |

## 投稿後に必ず行うこと

1. 発行された DOI を `README.md`、`CITATION.cff`、本論文ヘッダ、GitHub リポジトリ説明に書く。
2. GitHub の About に DOI バッジまたは URL を置く。
3. コードを直したら Zenodo で **新バージョン** を作り、DOI の版を分ける。古い提言と新しい実装が混線しないようにする。

## PDF 化（任意）

Pandoc がある場合の例:

```bash
pandoc paper/WORKING_PAPER.md -o paper/WORKING_PAPER.pdf --from markdown --pdf-engine=xelatex -V lang=ja
```

環境により失敗する。その場合は Markdown のままで投稿して差し支えない。

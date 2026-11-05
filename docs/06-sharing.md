# Gitでの共有手順

## 現在の状態

2026年11月5日、参加者本人が運営の招待を承認し、この提出用リポジトリをclone済みです。

| 項目 | 状態 |
| --- | --- |
| 提出用リポジトリ | https://github.com/Devfest-Hackathon-2026/df-2026-t033 |
| 公開範囲 | public（誰でも閲覧可能） |
| ローカルブランチ | main（origin/mainを追跡） |
| origin | https://github.com/Devfest-Hackathon-2026/df-2026-t033.git |
| 他の3人の招待・編集権限 | 未確認 |
| 開発用リポジトリ | 未設定 |

今回の資料統合はローカル変更のみで、コミット・pushはしていません。運営のREADMEとLICENSEを保持しています。配布PDFは持ち込まず、元の準備用フォルダもそのまま残しています。

## 提出用と開発用の使い分け

運営の[README](../README.md)に従い、このリポジトリには最終版の作品と資料を置きます。GitHub ActionsとGitHub Pagesは利用できません。開発用の別リポジトリが推奨されていますが、作成先や公開範囲はチームで決定します。

開発用にしか存在しない内容は審査対象になりません。最終成果物は11月10日17:00（日本時間）までに提出用へ反映し、必要な提出手続きを完了してください。締切後は読み取り専用になります。

## 今回の資料を初めて共有する

以下は現在のclone済みフォルダで、PowerShellから実行するための手順です。今回の統合では実行していません。最初に変更内容と対象を確認します。

```powershell
Set-Location C:\Users\rk132\df-2026-t033
git status --short --branch
git diff -- README.md .gitignore
git switch -c docs/team-preparation
git add -- README.md .gitignore docs/01-rules.md docs/02-team.md docs/03-schedule.md docs/04-decisions.md docs/05-environments.md docs/06-sharing.md
git diff --cached --check
git diff --cached
```

差分に個人情報、非公開URL、秘密情報、配布PDFが含まれないことを確認してから次を実行します。Gitの作者情報は本人のものを使ってください。途中でエラーが出た場合は続けず、原因を確認します。

```powershell
git commit -m "docs: add team preparation documents"
git push -u origin docs/team-preparation
```

GitHubで `docs/team-preparation` から `main` へのPull Requestを作り、1人以上のレビュー後にマージします。同名ブランチがある場合は別名を使用してください。originは登録済みなので追加不要です。元の準備用リポジトリの `.git` や履歴は持ち込みません。

## 他の3人が参加する

1. 各自が運営の招待を受諾し、提出用リポジトリの編集権限を確認します。公開ページを閲覧できるだけでは編集権限の確認になりません。
2. Gitを使う各自のPCで以下を実行します。

```powershell
git clone https://github.com/Devfest-Hackathon-2026/df-2026-t033.git
Set-Location df-2026-t033
```

3. READMEと[参加前のルール](01-rules.md)を読みます。資料はmainへのマージ後に共有されます。
4. A〜Dと実際のメンバーの対応や連絡先は、非公開のチーム連絡手段で共有します。

## 以後の資料更新

作業中の変更がないことを `git status` で確認してから、最新のmainを取得し、変更ごとに新しい作業用ブランチを作ります。

```powershell
git switch main
git pull --ff-only
git switch -c docs/update-team-notes
```

変更したファイルだけを追加し、差分を確認してコミット・pushし、Pull Requestでレビューを依頼します。競合は担当者同士で内容を確認して解決し、強制pushで他人の変更を消さないでください。

配布PDFと非公開の連絡情報はGitHubへ載せません。開発成果物を後で移す場合も、過去の履歴に秘密情報が含まれていないか確認してください。

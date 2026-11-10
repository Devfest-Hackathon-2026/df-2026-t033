# Windowsで使う：チーム向け手順

## 環境を準備

GitとPython 3.12が入ったPowerShellで実行します。clone済みなら先頭2行の代わりに、そのフォルダへ移動します。

```powershell
git clone https://github.com/Devfest-Hackathon-2026/df-2026-t033.git
cd df-2026-t033
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r fingerprint_model/requirements.txt
$python = (Resolve-Path .\.venv\Scripts\python.exe).Path
& $python -m unittest discover -s fingerprint_model/tests -v
```

activate不要です。PowerShellを開き直したらリポジトリへ移動し、`$python` の行を再実行します。依存はrequirementsで固定しています。

## ソースだけで動作確認

**数式模様の合成デモで、実指紋性能の確認ではありません。** 同梱モデルとは別に、まず自分のPCで小さなデモモデルを作ります。出力が既にあれば別名を使います。

```powershell
& $python -m fingerprint_model generate --output fingerprint_model/local/demo-data --identities 12 --impressions 2 --seed 20261108
& $python -m fingerprint_model train --manifest fingerprint_model/local/demo-data/manifest.csv --output fingerprint_model/local/demo-run --epochs 30 --seed 42
$sample = Import-Csv fingerprint_model/local/demo-data/manifest.csv |
    Where-Object { $_.split -eq 'test' -and $_.label -eq 'loop' } |
    Select-Object -First 1
& $python -m fingerprint_model predict --model fingerprint_model/local/demo-run/model.npz --image "fingerprint_model/local/demo-data/$($sample.path)" --source synthetic
```

JSONが表示され、モデル・評価結果は `local/demo-run/` に保存されます。合成U字や同心輪は本物のcore/deltaを再現していません。

## 最新方式で写真を試す

学習済みモデルを同梱しています。データ取得・学習は不要です。次の写真パスとEXIF方向適用後ROI座標を実際の入力へ置き換えます。

```powershell
& $python -m fingerprint_model.integration --image C:\path\photo.jpg --domain phone --roi '100,200,900,1400'
```

指腹全体へ切り出し済みならROI省略可。candidateを音楽ルールへ利用できますが、推定であることを表示します。needs_reviewは不確実性の情報で、強制的な承認手続きではありません。正解確率や本人識別には使用しません。Python import・JSON契約は [INTEGRATION.md](INTEGRATION.md)。

## 実画像モデルを作る

[FAMILY公式配布](https://data.mendeley.com/datasets/m4kz5ygxrn/1)の正規取得と[SOURCES.md](SOURCES.md)の条件確認から始めます。これはスマホ写真ではなく接触スキャンです。3分類正解表は配布されておらず、今回の個別ラベルもGit非共有です。

[ANNOTATION.md](ANNOTATION.md)でローカル取り込みとHTMLレビューを行います。同一家族・指・撮り直し・重複画像を別splitに分散させません。FAMILYでは別家族間にも同一画像があるため、画像重複で結ばれた家族も同一groupへ統合する確認が必要です。保留を自動で三択にしません。

全splitに3クラスを用意したレビュー出力が `local/my-review/` にある例：

```powershell
& $python -m fingerprint_model.annotation export --csv fingerprint_model/local/my-review/annotations-reviewed.csv --allow-provisional
& $python -m fingerprint_model.audit lock --manifest fingerprint_model/local/my-review/manifest-reviewed.csv --output fingerprint_model/local/my-review/partition-lock.json
& $python -m fingerprint_model.pattern train --manifest fingerprint_model/local/my-review/manifest-reviewed.csv --lock fingerprint_model/local/my-review/partition-lock.json --output fingerprint_model/local/my-pattern/templates.npz
```

`--allow-provisional` は単独の暫定レビューを明示する指定です。学習はtrainとvalidationをテンプレート化しtestを除外します。学習成功は性能保証ではありません。方法比較はグループを分けた開発評価で行い、方法固定後の別人物・別指の写真を最終評価用に残します。

## Git共有の境界

ソース・テスト・集計・同梱参考モデルを共有します。assets/pattern-v1のモデルはCC BY 4.0で出典・加工を明記しています。元画像、写真、個別CSV、manifest、生ログ、その他のモデルはlocal内の非共有のままです。除外ファイルをgit add -fで追加しません。

## この手順の確認状況

Python 3.12・requirements記載版の既存環境で19テストが合格。ソースだけの合成デモに加え、wheel作成・別targetへのインストール・リポジトリ外からのimportと同梱モデル推論を確認しました。新規venvへのインターネット経由依存インストール自体は未検証です。

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

**数式模様の合成デモで、実指紋性能の確認ではありません。** cloneに実画像モデルはありません。まず自分のPCで小さなデモモデルを作ります。出力が既にあれば別名を使います。

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

**別途最新templateモデルを準備した人向けです。clone直後は以下のモデルがなく実行できません。** 合成デモのmodel.npzとは互換性がありません。

写真はGit除外済み `fingerprint_model/local/phone-photos/` に置きます。パスとROI座標は例なので、実際の写真に合わせます。座標はEXIF方向適用後の左・上・右・下です。

```powershell
& $python -m fingerprint_model.pattern predict --model fingerprint_model/local/my-pattern/templates.npz --image fingerprint_model/local/phone-photos/photo.jpg --domain phone --roi '100,200,900,1400'
```

指腹全体へ切り出し済みなら `--roi` を省略できます。模様中心だけでなく周囲の流れも残し、元画像はローカルで保持します。自動指検出ではありません。スキャンには `--domain scan` を使います。

- `candidate`: arch / loop / whorlの参考候補。
- `decision`: reference_candidateは参考表示、retakeは品質不足、insufficient_matchは比較領域不足。
- `verified_label`: null。experimentalはtrueです。
- `quality` / `reasons`: 読めた領域や競合理由。similarity/marginは正解確率ではありません。

現状archは開発評価0/4。写真の正解率は未検証です。本人識別・認証には使いません。

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

ソース・テスト・集計レポートを共有します。実画像、写真、個別レビューCSV、manifest、lockの個別内容、モデルnpz、生ログは `fingerprint_model/local/` 内に置きます。テンプレートにも実画像由来の方向情報があるため公開しません。既存モデルをチームへ渡す場合は非公開artifactの共有範囲と保管方法を別途決めます。

```powershell
git status --short
git check-ignore fingerprint_model/local/phone-photos/photo.jpg
```

除外ファイルに `git add -f` を使わないでください。この運用とCC BYの帰属表示義務は別です。

## この手順の確認状況

Python 3.12・requirements記載版の既存環境で16テストが合格。実画像・既存モデルをコピーせずソースだけを隔離フォルダへコピーし、上記と同じ小規模生成・学習・1枚推論を実行しました。新規venvへのインターネット経由pipインストール自体は未検証です。

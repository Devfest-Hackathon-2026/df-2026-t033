# ローカル画像のレビュー

[QUICKSTART.md](QUICKSTART.md)で環境を準備してください。実画像・ラベル・HTMLはcloneには含まれません。FAMILYには3分類正解表がなく、画像を見たレビューが必要です。既存32枚は単独AIの暫定形態ラベルで、人の確認済み正解ではありません。外側ZIPに内側ZIPがある場合は手元で展開して内側ZIPか画像フォルダを指定します。

## 取り込みとブラウザでの確認

PowerShellで実行します。`--input` はダウンロードしたZIPまたは画像フォルダに変更します。出力先は必ずGit除外済みの `fingerprint_model/local/` 配下です。

```powershell
Set-Location C:\path\df-2026-t033
$python = './.venv/Scripts/python.exe'
& $python -m fingerprint_model.annotation import --input 'C:\path\downloads\YOUR-DATA.zip' --output fingerprint_model/local/family-review-v1 --license 'CC-BY-4.0; attribution recorded locally' --provenance 'FAMILY FINGERPRINT DATASET v1 https://data.mendeley.com/datasets/m4kz5ygxrn/1' --limit 60
Start-Process fingerprint_model/local/family-review-v1/review.html
```

取り込みは自動分類しません。画像の全範囲を保ち、EXIF回転を反映したメタデータなしPNGと元ファイルを別々にローカル保存します。元画像には位置情報等が残る可能性があり、元画像・レビュー・CSVを公開Gitへ入れません。ZIPのパス逸脱、リンク、暗号化、1ファイル20MB・展開合計512MB超は拒否します。対応形式PNG/JPEG/BMP/TIFF、最大8192px・3200万画素、複数フレーム不可。失敗や重複は `intake-report.json` に記録し、正常画像だけ取り込みます。制限を超えた大規模データは小さなサブフォルダで進めます。

HTMLでは全体を収めて表示し、クリックで原寸PNGを開けます。分類・根拠・仮名レビュアーID・人物/家族グループ・分割を入力し、**「レビューCSVを保存」**を押します。ダウンロードされた `annotations-reviewed.csv` を、このHTMLと同じフォルダへ移動してください。画面を閉じる前に保存し、同名の既存CSVは上書きせず保管します。再開は次のコマンドで保存CSVからHTMLを再生成します（HTMLだけ更新）。Excelは不要です。

```powershell
& $python -m fingerprint_model.annotation sheet --csv fingerprint_model/local/family-review-v1/annotations-reviewed.csv
```

## 判定の基準

[NIST Pattern Classification](https://tsapps.nist.gov/trainingtool/FundamentalAFISSearching/PatternClassification.html)を要約した作業基準です。専門家による同定の代替ではありません。

- **arch**：plain/tentedを統合。横断する隆線の山形、または角・突き上げ等を観察。tentedはloopの条件の一部だけを満たすことがあります。
- **loop**：十分な折り返し、delta、coreとdeltaの間の隆線を確認し、入った側へ戻る流れを記録。左右を統合します。
- **whorl**：通常2つのdeltaと中心の隆線構造を確認。plain/central pocket/double loop/accidentalを統合。ただしaccidentalには例外があり、単に丸く見えるだけで決めません。

**画像端でdeltaが見えないことは、deltaが存在しない証拠ではありません。** 中央だけの極小cropで三択を強制しないでください。撮影枠は模様中心と周辺の流れを含め、元の大きな画像をローカル保持します。必要情報が枠外なら `pattern_coverage=insufficient`、読めなければ `quality_status=fail`。境界例・複数候補は `unknown/pending/disputed` として訓練から除外します。unknownを4番目の正解クラスにしません。

`source_label` は配布元ラベルがある場合だけそのまま保存。推測で埋めません。`subclass` は分かる場合に `plain_arch / tented_arch / left_loop / right_loop / plain_whorl / central_pocket_whorl / double_loop_whorl / accidental_whorl` 等を入力。根拠欄には見えた構造と欠けた範囲を短く記録します。

## 分割と学習への接続

同じ人物は同じ `group_id` と同じsplit。FAMILYは家族単位に加え、同一画像で結ばれた別家族も同じグループへ統合します。全データの重複調査が必要です。名前・ファイル連番から人物を勝手に推定せず、元の対応表を確認してください。撮り直しや別の指・加工画像も同じグループへまとめます。最初は各クラス20〜30の独立した指を小規模目安にしますが、十分な精度を保証する量ではありません。train約70%、validation約15%、test約15%を**グループ単位**で先に割り当て、全分割に3クラスを確保します。

通常は2人が別々に分類と根拠を入力し、一致した行だけ `agreed` にします。本人が別名を入力して2人に見せかけません。プログラムは異なるIDと一致を検査しますが、レビュー実施の真偽は保証できません。

```powershell
& $python -m fingerprint_model.annotation export --csv fingerprint_model/local/family-review-v1/annotations-reviewed.csv
& $python -m fingerprint_model.audit lock --manifest fingerprint_model/local/family-review-v1/manifest-reviewed.csv --output fingerprint_model/local/family-review-v1/partition-lock.json
& $python -m fingerprint_model train --manifest fingerprint_model/local/family-review-v1/manifest-reviewed.csv --partition-lock fingerprint_model/local/family-review-v1/partition-lock.json --output fingerprint_model/local/real-run-new --epochs 300
```

1人で先に探索する場合は `provisional` として、exportへ **`--allow-provisional`** を明示追加できます。この経路は未合意の実験で、provenanceと監査JSONに記録されます。未記入・unknown・品質不良は依然除外されます。合意版と比較するときは新しい出力フォルダにコピーして別runで保存してください。

exportは人物グループの分割重複、同じ画像の別split、画像品質、全splitの3クラスを検査し、不足時は学習CSVを作りません。元レビューCSVのハッシュと除外画像IDを監査JSONへ保存します。訓練後も実指推論は未検証扱いのままです。別人物のスマホ撮影で、クラス別誤り・拒否率・撮り直し・ぼけ/背景を評価してから採用を判断します。

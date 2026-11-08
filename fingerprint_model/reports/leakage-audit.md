# データリーク監査と開発用の再検証

2026-11-08。**確認した範囲では、v2の評価画像が直接学習へ混入した証拠は見つかりませんでした。ただし「リークが絶対にない」「4/5が実用精度」とは言えません。** ラベルと画像の選び方による偏り、未検出の近似重複、少数評価が残ります。

## 確認した範囲

親エージェントが実装担当とは別に監査し、次を確認しました。生の画像名やラベル対応はローカル監査ファイルだけに保存しています。

| 対象 | 観測結果 |
| --- | --- |
| manifestとモデル | manifest SHA256がモデルmetadataと一致 |
| 出典グループ | 32行のgroup_idがsplitをまたがない |
| 全配布画像の完全重複 | 1,500枚→1,363ユニーク、重複集合135、別家族をまたぐ集合118 |
| 重複由来の分割 | 同一画素でつながる家族を推移的に結合、100フォルダ→88成分。同じ成分は同じsplit |
| 正規化 | train23枚とtrainのみの4変種＝115ベクトルから再計算したmean/scaleがモデルと完全一致、最大差0 |
| 学習再現 | testをfit引数へ渡さず、train/validationだけで300epoch/seed42を再実行。全モデル配列とbest epoch 2を完全再現、最大差0 |
| 近似重複の探索 | split間227ペアで63bit pHash距離の最小12、縮小画像相関の最大0.9167。上位6ペア比較を実際に目視し、明らかな同画像の再crop/reencodeは検出せず |

pHash・相関・上位候補の目視だけで、全ての再撮影・変形・同じ指を検出できるわけではありません。家族フォルダは出典上の区分で、実際の人物の独立性を保証する情報ではありません。本人照合を目的とした推定はしていません。

コード上も、平均・標準偏差とclass weightはtrainのみ、幾何拡張もtrainのみです。epoch選択・スコアしきい値・距離半径はvalidationのみ。autocontrastは各1枚の画素から計算する共通前処理で、test集合の統計を学習に渡していません。全画像の重複照合は分割を作るための処理で、分類器をfitする入力ではありません。

## 直接混入と区別すべき偏り

- 全画像を一覧で見て読みやすい例・不足クラスの候補を選び、単独AIが暫定ラベルを付けています。無作為標本でも専門家の独立正解でもありません。
- arch候補は細部が未確定な形態ラベルを含みます。旧pendingの1例を形態実験へ採用した履歴を残しています。曖昧なラベルはスコアを変え得ます。
- v1の0/4を見た後にデータを増やし、v2では別成分の5枚を評価しました。v1→v2は同じ未使用評価での改善比較ではありません。v2の5枚も今は観察済みであり、今後の最終評価には使えません。
- スクリプトと保存結果は残っていますが、当時の事前固定・一度しか評価していないことを暗号学的に証明するロックや改ざん不能な時系列ログはありません。「testを1回しか見ていない」と監査で断言しません。

## 是正したこと

`fingerprint_model.audit lock` を追加し、manifest全体・label/group/split/provenance・画像bytesのSHA256を固定しました。現在の32行をローカル `partition-lock-v1.json` に保存しています。変更があればverifyと今後のreal-data trainが拒否します。real trainには `--partition-lock` が必須です。

**このロックは今後の変更検知で、過去の事前固定の証明ではありません。** ローカルファイルなので、所有者が意図して新ロックを作ることまで防ぐ仕組みでもありません。ラベル修正等は新しい版・理由を残し、都合のよい評価分割への差替えを行わない運用が必要です。

今回は新しいtestへ交換せず、v2の元test5枚を除いた27枚だけでnested group CVを実施しました。ロック照合では全画像のbytesを読みますが、このCVの特徴抽出・fit・モデル選択・評価に元test5枚は入りません。既存v2モデルと元5枚の結果は変更していません。

## 27枚でのnested group CV

開発27枚・25成分を外側3foldへ分割。各外側foldの評価成分を避け、残りの成分内でさらにinner train/validationを分けました。全foldの計画を最初のfit前に保存し、分割成立の条件はクラス/グループ数だけです。各inner trainだけで正規化・拡張・クラス重みを作り、inner validationだけでepochと拒否条件を選択。外側評価は最後に行いました。v2と同じ固定設定を使い、このCV結果への追加チューニングはしていません。

| 集計 | 結果 |
| --- | --- |
| 強制3択の一致 | 10 / 27（37.0%） |
| pooled macro-F1 | 0.339 |
| 各inner trainの最多クラス固定基準 | 8 / 27、macro-F1 0.200 |
| 拒否処理あり | 11採用・16 unknown、採用中5一致 |
| 外側foldごとの一致率 | 40.0% / 37.5% / 33.3% |

この結果は、以前の5枚4一致が安定した性能を示していないことを裏付けます。CVも少数・選択済み・暫定AIラベル上の開発診断で、スマホ写真の最終精度ではありません。[集計JSON](development-cv-metrics.json)を保存しました。

## 次の評価をどう分けるか

今後の特徴改善や設定比較は、この固定した開発データ内で行います。試した設定とCV結果を残し、最良CV値を外部精度として扱いません。最終確認には、人が確認したラベルと未使用のスマホ指写真が必要です。

撮影枠・ピント・明るさの調整に見た写真は開発用です。同じ指の撮り直しをtrainと最終評価へ分けません。方法を固定した後に別の指/人物単位で確保した写真を、最終評価用として一度だけ評価する設計にします。現状で安定した3分類器として採用する根拠は不足しています。

## 再実行

```powershell
Set-Location C:\path\df-2026-t033
$python = './.venv/Scripts/python.exe'
& $python -m fingerprint_model.audit verify --manifest fingerprint_model/local/family-real-v2/manifest-reviewed.csv --lock fingerprint_model/local/family-real-v2/partition-lock-v1.json
& $python -m fingerprint_model.audit cv --manifest fingerprint_model/local/family-real-v2/manifest-reviewed.csv --lock fingerprint_model/local/family-real-v2/partition-lock-v1.json --output fingerprint_model/local/real-development-cv-repeat --epochs 300 --folds 3
```

同じ出力フォルダは上書きしません。テスト13件には分割/画像変更検知、test画像を特徴抽出しないこと、外側/内側成分の非重複、nested CVの小規模実行を追加しています。

# 他の担当のシステムへ組み込む

学習済みの参考モデルを `assets/pattern-v1/` に同梱しました。clone後、requirementsを入れれば学習・データ取得なしで呼び出せます。元画像・個別ラベル・スマホ写真は同梱しません。モデルは実スキャン画像由来の方向特徴を含みます。[モデルカード・帰属表示](assets/pattern-v1/MODEL_CARD.md)を確認してください。

## セットアップとCLI

リポジトリ直下のPowerShellで実行します。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r fingerprint_model/requirements.txt
.\.venv\Scripts\python.exe -m fingerprint_model.integration --image C:\path\photo.jpg --domain phone --roi '100,200,900,1400'
```

写真パス・座標は例です。ROIはEXIF方向適用後の左・上・右・下で、指腹の中心と周辺の流れを残します。すでに切り出した画像はROI省略可。任意写真からの完全な自動指検出ではありません。

## Python API（推奨）

バックエンドの起動時に1回生成し、アップロードしたbytesを渡します。別バックエンド環境では `python -m pip install C:\path\df-2026-t033` でインストールできます。モデルも一緒にインストールされ、リポジトリ外からimportできます。

```python
from fingerprint_model.integration import FingerprintClassifier

classifier = FingerprintClassifier()  # 同梱モデルを検証してメモリに保持

def analyze_upload(image_bytes: bytes, roi=None):
    return classifier.predict(image_bytes, domain="phone", roi=roi)

# ローカルファイルも同じ入口
# result = classifier.predict("photo.jpg", domain="phone", roi=(100,200,900,1400))
```

推論APIは写真の保存・ログ出力をしません。モデル読込失敗は起動時例外として扱い、サービスを不完全な状態で稼働させないでください。入力エラーはJSONの `decision=error` です。パス入力は信頼できるバックエンド内部だけで使い、利用者にサーバー上の任意パスを指定させません。

PNG/JPEGのみ、20MB以下、各辺64〜8192px、合計3200万画素以下、単一フレーム。HTTPを実装する担当も、本文読込前に上限を設けてください。bytesから一時写真ファイルを作りません。

## JSON契約

全結果に次のキーを返します。

| キー | 意味 |
|---|---|
| schema_version | `fingerprint-candidate-v1` |
| candidate | `arch` / `loop` / `whorl` / null |
| decision | `reference_candidate` / `retake` / `insufficient_match` / `error` |
| quality / reasons | 品質の辞書と理由コードの配列 |
| needs_review / experimental | 常にtrue |
| verified_label | 常にnull |
| method / model_sha256 | 処理方式・実際にロードしたモデルの版確認 |

候補がある場合にはrelative_similarity、class_distances、support_margin等も返します。これらを正解確率や承認フラグへ変換しないでください。`retake`は撮り直し、`insufficient_match`は比較根拠不足、`error`は入力エラーです。候補なしを自動でarchへ変換しません。

## 各担当への接続

フロントで撮影・ROI選択 → バックエンドでアップロード制限 → `classifier.predict(bytes)` → 参考候補と注意を表示 → 作曲担当が候補に対応する音楽ルールを選びます。

作曲側へはcandidateだけでなくdecisionとneeds_reviewも渡し、保留時の撮り直し・手動選択を用意してください。密度・minutiae・本人識別は実装していません。必要なAPI認証、通信保護、レート制限、ファイル保管方針はバックエンド側の責務です。この変更にHTTPサーバーや新依存は追加していません。

現状は開発27枚で14一致、arch0/4。単独AIの暫定スキャンラベルとの比較で、スマホの正解率は未検証です。「動く」と「正しく判定できる」を分けて扱ってください。

## チームでの検証

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s fingerprint_model/tests -v
.\.venv\Scripts\python.exe -m fingerprint_model.integration --image fingerprint_model/assets/synthetic-demo.png --domain scan
```

同梱PNGは人工的な同心輪で実指画像ではありません。APIの動作確認用で、実指精度の証拠には使いません。

needs_reviewは不確実性を伝えるフラグで、必須の人手承認フローではありません。音楽生成に参考候補を使うかは製品側で判断できます。

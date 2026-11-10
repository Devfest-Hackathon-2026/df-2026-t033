# Fingerprint Symphony — v14 + 最小バックエンド接続版

## この版でできること

- v14 の React 画面・カメラ・写真選択・個人曲・共同曲の機能を維持。
- 参加者 A / B / C の画像を選んで登録すると、**Python FastAPI に画像を一時送信して形式・容量・寸法を検証**。
- 画像検証が成功したらブラウザのプレビューが更新され、従来どおり「指紋から個人曲を生成」を操作できる。
- **指紋特徴抽出と作曲は JavaScript（ブラウザ内）で実行**。今回の FastAPI は特徴抽出も作曲も行わない。
- サーバー側はデータベースや画像フォルダを持たない。画像は一時的に読み込み、検証後に破棄する（multipart パーサーが一時ファイルを使う可能性あり）。
- 同意がない画像は送信しない。カメラ画像も同じ検証 API を通す。
- 「友達と作る」「ランダムで作る」は従来どおり未実装。

> **重要：** もともとブラウザ単体で画像を選択できる仕様だったため、「アップロード不可」の原因がバックエンド未実装だったと断定はできません。この版ではAPI通信を新たに追加しました。実端末での確認は必要です。

## フォルダ

```text
fingerprint-symphony/
├─ frontend/                React + Vite（画面、ブラウザ内の指紋解析と作曲）
│  ├─ src/App.jsx
│  ├─ src/api.js           FastAPIに画像を送る処理（新規）
│  ├─ vite.config.js       /api を localhost:8000 に転送（修正）
│  └─ firebase.json        Hosting → Cloud Run /api リライト案（修正）
├─ backend/
│  ├─ main.py              画像検証API（新規）
│  ├─ requirements.txt
│  ├─ Dockerfile
│  └─ tests/test_api.py
├─ docs/                   v14 の画面・連携メモ
└─ music-engine-reference/ 指紋解析・作曲エンジンの参照テスト
```

## 初めて使うときの最短手順（Windows）

展開フォルダの `start_backend.bat` を開き、APIサーバーが起動したら `start_frontend.bat` を開いてください。**2つの黒い画面は、利用中閉じないでください。** 初回は Python / npm の依存パッケージをインストールします。どちらかが起動できなければ、下記の手動起動手順でエラーを確認してください。

`http://localhost:8000/api/health` が `status: ok`、`http://localhost:5173/` が画面の確認先です。

## Windows / VS Code での起動（ターミナルを2つ使う）

事前に Python 3.11 以上、Node.js 22.12 以上、npm をインストール。

**① ターミナル1（バックエンド）**

```powershell
cd .\backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

`http://localhost:8000/api/health` にアクセスして `"status":"ok"` が返ればOK。`http://localhost:8000/docs` でAPI一覧を確認できます。

**② ターミナル2（フロントエンド）**

```powershell
cd .\frontend
npm install
npm run dev
```

`http://localhost:5173/` で操作する。手順は「この端末で作る → 人数選択 → 本人の同意にチェック → 画像アップロードまたは撮影 → サーバー画像検証 → 個人曲を生成 → 共同曲を生成 → 再生」。

Vite が `/api/*` を `http://127.0.0.1:8000` に転送するので、開発時の CORS 設定は不要です。

### アップロードに失敗した場合

1. 先に FastAPI が起動しているか `http://localhost:8000/api/health` で確認する。
2. **同意チェック後**に「画像をアップロード」を押す。
3. JPEG/PNG/WebP、10 MB以下、縦横192〜8192 px、総画素2400万以下の画像を使う。
4. `http://localhost:5173` から開く（HTMLファイルのダブルクリック起動は不可）。
5. 画面上にエラーが出る場合はその文字列と、開発者ツールの Console / Network を確認する。

## API

- `GET /api/health` — 起動確認
- `POST /api/images/validate` — **multipart/form-data**で画像を受け取って検証、永続保存なし

| フォームフィールド | 値 |
| --- | --- |
| `participant_id` | `A` / `B` / `C` |
| `consent` | `true`（本人同意あり） |
| `image` | JPEG / PNG / WebP 画像ファイル |

成功例：

```json
{"status":"accepted","participant_id":"A","image_format":"jpeg","width":900,"height":900,"image_persisted":false,"features_extracted":false,"next_step":"browser_fingerprint_analysis"}
```

失敗例：

```json
{"status":"error","code":"INVALID_IMAGE","message":"画像を読み取れませんでした。撮り直してください。"}
```

受け付けた画像は **ブラウザ内の指紋解析とは別に、形式確認のためにだけサーバーへ送られます**。Python は解析結果や音源を返しません。

## テスト

```powershell
cd .\backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

参照エンジンのテストは `music-engine-reference/` で `node test.cjs` と `node test-analysis.cjs`。

## 公開（未実施）

構成案は **Firebase Hosting（React） + Cloud Run（FastAPI）**。`frontend/firebase.json` に `/api/**` を `fingerprint-backend`（東京リージョン）へ転送する例を設定済みです。**Cloud Run のサービス名・リージョンが実際と異なるなら必ず変更**してください。先に Cloud Run を公開し、次に Hosting を公開します。

- Cloud Run の公開・Hosting とのリライトには Google Cloud の課金設定が必要な場合があります。無料枠の有無と支出上限を事前に確認してください。
- 不特定多数に公開する前にレート制限、リクエスト上限、CORS/Origin相当のアクセス制御、運用上のログ・一時ファイル保持、費用上限を検討してください。
- **今回はデプロイを実行していません**。本番の安定稼働や外部ユーザーからのアクセスは未検証です。
- 指紋画像はセンシティブです。クラウド側のアクセスログ・リクエスト記録・一時ディスクの保持条件も別途確認してください。
- スマホのブラウザでカメラを使う場合はHTTPS（またはlocalhostの開発環境）が必要です。

## 修正と検証範囲

- 新規FastAPI画像検証（同意・形式・容量・寸法のチェック）と自動テスト6件。
- フロントはアップロード / カメラ撮影を **同じAPIに接続**。受付失敗時に成功表示しない。旧画面の音楽生成ロジックは維持。
- 削除・同意撤回時に、送信中の古いレスポンスを画面に採用しない。
- 画像送信についての同意文を「サーバー送信なし」から実装に合わせて修正。
- JSX/JavaScriptの構文検査は成功。**npmレジストリへ接続できず、Reactの本番ビルドと実ブラウザ操作はこの環境で未検証**。

## 追加した動作確認（2026-11-10）

- `python -m pytest -q backend/tests/test_api.py`：**6件成功**。
- `python tests/run_node_smoke.py`：実際にFastAPIサーバーを起動し、**フロントの `src/api.js` からPNG・撮影ファイル相当のJPEG・WebPを送信して正常応答を確認**。破損JPEG・非対応GIF・MIMEと中身の不一致・空ファイルは拒否を確認。合成画像を利用。
- 指紋解析と作曲の付属Nodeテスト：合格。
- ReactファイルのJSX/JavaScript構文検証：合格。
- **未確認**：この環境ではnpm依存関係の取得ができず、またブラウザの画面アクセスが制限されていたため、`npm run dev` の画面上でクリックしてアップロードするE2E確認、実スマホカメラ確認は実施できていません。画面での操作確認はローカルで必要です。
- 最小APIは指紋パターンの品質検証を行いません。形式に問題のない風景写真なども受付可能ですが、生成時の指紋解析で失敗する場合があります。

## このリポジトリでの確認

作曲・解析の参照テストは不足していたdist参照を修正し、実際のfrontendソースを直接読み込むようにしています。

```powershell
node web/music-engine-reference/test.cjs
node web/music-engine-reference/test-analysis.cjs
```

両テストとPython構文チェックは通過しました。取り込み環境では外部DNS接続が失敗したため、npm install/build、FastAPI実行、実ブラウザ操作は再確認できていません。上記の起動手順で実機確認してください。合成画像のテストは実写真での精度を保証しません。

## 部分的な読み取りでの作曲

指紋の線が一部だけ読み取れた場合も、参考候補・部分的な隆線交差数で作曲を続行します。解析の注意点を参加者カードに表示します。隆線交差数が取得できない場合は「未取得」と表示し、音楽用の仮設定32（80 BPM）を使います。これは測定結果ではありません。

観測値が極端に小さい／大きい場合は、表示した観測値を保持し、音楽入力のみ80〜160 BPMに調整します。画像全体・中央70%・中央50%の解析範囲を選択できます。範囲により分類候補や交差数が変わるため、実写真での正確性を保証しません。真っ白・暗すぎる画像・ノイズなど、読める方向情報がない場合は引き続き撮り直しを案内します。

# 指紋パターン分類の実験コード

初めて使う人は **[QUICKSTART.md](QUICKSTART.md)** へ。Python 3.12、NumPy、Pillowで動くCLIです。

このGitにはソース・テスト・集計レポートを共有します。実画像、写真、個別ラベル、manifest、モデルは含めません。**clone直後に実画像モデルで推論することはできません。** ソースだけで動く合成デモを用意しています。

| 入口 | 用途 |
|---|---|
| `python -m fingerprint_model.pattern` | 最新方式。背景・陰影補正、512px方向場と学習テンプレートによる参考候補 |
| `python -m fingerprint_model` | 合成デモと従来128px線形softmax方式 |
| `python -m fingerprint_model.annotation` | ローカル画像のHTMLレビュー、CSV、学習manifestの作成 |
| `python -m fingerprint_model.audit` | 分割lock、画像ハッシュ、グループを分けた開発評価 |

二方式のモデルファイルは互換性がありません。最新方式は `candidate` を返しますが `verified_label` はnullです。類似度は正解確率ではありません。入力は手動ROIまたは事前切り出しで指腹全体を残します。全写真からの自動指検出ではありません。

固定した開発27枚では最新方式14/27一致、従来10/27。ただし **archは0/4** で、信頼できる3分類器には未到達です。ラベルは単独AIの暫定形態判定で、人の確認済み正解ではありません。異なる人の写真2枚は調整後の各5加工条件でwhorl候補・loop候補が各5/5一致しましたが、独立撮影の再現性や実写真の正解率ではありません。

- [最新方式の比較と制約](reports/pattern-candidate-improvement.md)
- [リーク監査](reports/leakage-audit.md)
- [旧線形方式の実験](reports/real-v2-experiment.md)
- [合成実験](reports/experiment.md)
- [取り込み・レビュー手順](ANNOTATION.md)
- [出典・加工・利用条件](SOURCES.md)

FAMILY正規取得だけでは同じモデルを再現できません。配布物に3分類の正解表はなく、今回の個別注釈もGit非共有です。新たにレビュー・グループ分割するか、既存artifactの非公開共有方法を別途決める必要があります。テンプレートは実画像由来の方向情報を保持するため公開Gitへ追加しません。本人識別・認証には使いません。

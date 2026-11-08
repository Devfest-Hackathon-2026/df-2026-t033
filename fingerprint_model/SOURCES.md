# 出典・加工内容

更新2026-11-08。新規コード・数式合成画像は[MIT](../LICENSE)。データ・依存ライブラリの条件とは別です。

Diptadip Maiti, Debashis Das (2023), **FAMILY FINGERPRINT DATASET**, Version 1, Mendeley Data, DOI [10.17632/m4kz5ygxrn.1](https://doi.org/10.17632/m4kz5ygxrn.1)。[公式配布](https://data.mendeley.com/datasets/m4kz5ygxrn/1)はCC BY 4.0表示。2026-11-08にユーザー取得ZIPを使用。著者の支持を意味しません。

全1,500 PNGを一覧確認し、EXIF方向反映、メタデータ除去、縮小、コントラスト補正、ROI・マスク・方向特徴を作成。単独AIの暫定形態ラベル32枚で従来線形実験を行い、最新templateは旧test5枚を除いた開発27枚と少角回転・移動を使用しました。配布元の3分類正解表はなく、人の確認済み正解ではありません。

実画像・個別注釈・manifest・モデルはGit非共有。このローカル保管はプロジェクトの判断で、CC BYが一律に再配布を禁じる意味ではありません。利用・加工・共有時は出典・ライセンスリンク・変更内容を維持してください。

利用者提供の異なる人のスマホ写真2枚は前処理調整用です。正解ラベルや訓練には使用せず、写真・個別ログは公開しません。

合成デモは新規数式生成で、外部画像・実在人物・学習済み重みを使いません。U字や同心輪は本物の指紋構造を再現していません。NumPy 2.3.5 / Pillow 13.0.0を使用し、各配布物のLICENSEに従います。

設計参照：[OpenCV構造テンソル解説](https://docs.opencv.org/4.10.0/d4/d70/tutorial_anisotropic_image_segmentation_by_a_gst.html)、[NIST Pattern Classification](https://tsapps.nist.gov/trainingtool/FundamentalAFISSearching/PatternClassification.html)。参照画像は学習せず、OpenCVは依存しません。外部モデル実装のコピーや転移学習はしていません。

音楽向け候補の実験用です。本人認証、性格・健康・血縁推定には使いません。最新方式のarch開発評価は0/4、実写真正解率は未検証。[最新報告](reports/pattern-candidate-improvement.md)を参照してください。

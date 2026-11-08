# 追加調査：すぐ試すデータの優先順位

調査日：2026年11月8日。[前回調査](09-fingerprint-datasets.md)を補う更新です。今回は**COLFISPOOFとFAMILY FINGERPRINT DATASETを追加し、取得優先順位を変更**します。実装対象はスマホで指先を枠に合わせた中央ROIから音楽向け特徴を抽出する処理で、本人識別ではありません。

## 結論：まずこの2つを使い分ける

| 優先 | データ | 今回使う理由 | 条件と限界 |
| --- | --- | --- | --- |
| 1：撮影に近い検証 | **COLFISPOOF：7,200枚** | 人工指紋をスマホで撮影。色・材質・撮影のばらつきを含むため、中央ROIの抽出成功/失敗を調べる補助として前回候補より有望 | 配布元は出典表示を要求し、そのうえで「without further restriction」と明記。生身の指の写真ではなく、実スマホ利用者の性能評価の代用にはしない |
| 2：隆線処理の基礎検証 | **FAMILY FINGERPRINT DATASET：1,500枚** | 実際の人の指紋で、512×512 PNG。前回のJLWより枚数が多く、模様の方向・曲がりの処理確認に使いやすい候補 | データページがCC BY 4.0。インク押印→スキャン→前処理で、皮膚表面をカメラ撮影した写真とは異なる |
| 3：合成contactlessの追加 | **IMPOSE-SYN：1,712＋15,136枚** | 多姿勢の合成contactless画像を含む。データ形態は目的に関連する | projectのApache 2.0と、別配布画像・重みへの適用範囲をまだ分離確認できていない。公開デモ等を無条件に承認済みとはしない |

**追加調査により、JLWだけを第一候補にする必要はなくなりました。** COLFISPOOFで撮影・材質の変動、FAMILYで実指紋の模様を点検し、最後に自分たちの枠撮影を少数加える構成を推奨します。大量のモデル学習を始める提案ではありません。

## 1. COLFISPOOF：最初に開く配布先

- [研究室の公式配布ページ](https://dasec.h-da.de/colfispoof/)
- [公式Nextcloudのデータ共有](https://cloud.h-da.de/s/xWFQDTKJYMkGnyE)
- [作者の前処理・分割・ROI補助資料](https://github.com/dasec/COLFISPOOF)

公式配布ページは7,200サンプル・72種類のpresentation attack instrument（人工の提示物）を説明しています。Download and Copyright節は、実験結果を使う論文・技術報告に謝辞と文献参照を求めたうえで、データを **“without further restriction”** で提供するとしています。申請・機関署名・非商用限定の条件はこの配布節にはありません。今回の検証へ進む根拠として、曖昧なコードライセンスより強いものと判断します。標準CCライセンス名を独自に付け直さず、実際の配布条件と出典を記録します。[公式条件](https://dasec.h-da.de/colfispoof/)

作者のWACV論文は、2種類のスマホで取得したこと、人工提示物に使う模様をSFinGe/SynCoLFinGerで生成し生存する個人の指紋を含まないことを説明しています。これは「写真ではない」という意味ではなく、**人工物を実カメラで撮影した画像**です。皮膚色・弾性・生体の反射までは同等と見なしません。[作者論文の公開ページ](https://openaccess.thecvf.com/content/WACV2023W/MAP-A/html/Kolberg_COLFISPOOF_A_New_Database_for_Contactless_Fingerprint_Presentation_Attack_Detection_WACVW_2023_paper.html)、[論文PDF](https://openaccess.thecvf.com/content/WACV2023W/MAP-A/papers/Kolberg_COLFISPOOF_A_New_Database_for_Contactless_Fingerprint_Presentation_Attack_Detection_WACVW_2023_paper.pdf)

このデータはPAD用ですが、今回PADを実装する必要はありません。色を落として方向場を求める、反射・不鮮明・薄い模様で欠損を返すなど、音楽特徴抽出の試験に使う案です。材料の色や背景を「指紋の個性」として取り込まないことを重点的に確認します。人工物画像だけで、本物の指を入力した際の合格率・本人識別性能を報告しません。

### すぐ試す手順

1. 公式ページからNextcloudを開く。本調査では共有名 `HDA_COLFISPOOF` まで確認できましたが、ファイル一覧はJavaScriptが必要で確認できていません。
2. 通常のブラウザで一覧が開いたらREADME等の説明を先に読み、容量を確認する。分割して取得できるなら、まず材質の異なる20〜50枚だけ選ぶ。全体一括の容量が大きい場合は無理に全取得しない。
3. `docs/local/datasets/colfispoof/` に保存し、元画像の形式・サイズ・前処理済みか・背景の有無を確認する。このパスは既存Git除外対象。
4. 手元の本番と同じ中央cropで、取得可能な2特徴、品質理由、処理時間を確認する。データ側が既に指先を切り抜いた画像なら、元のカメラ画面枠の検証と区別する。
5. 公開資料にJ. Kolberg, J. Priesnitz, C. Rathgeb, C. Busch, “COLFISPOOF: A New Database for Contactless Fingerprint Presentation Attack Detection Research”, WACV Workshops 2023と配布元URLを記載する。加工した内容も残す。

画像データの条件と補助コードのライセンスは別です。補助repoに前処理・ROI処理があることは確認しましたが、コードをそのまま製品へコピーする許可の確認とはしていません。まずデータを自分たちの抽出処理で試す案です。

## 2. FAMILY FINGERPRINT DATASET：1,500枚のCC BY 4.0データ

[一次配布元：Mendeley Data V1](https://data.mendeley.com/datasets/m4kz5ygxrn/1)

配布者Diptadip Maiti / Debashis Dasによる説明は、100家族の父・母・子、各人の右手5指で合計1,500画像、PNG、512×512です。ページのデータライセンスはCC BY 4.0で、今回確認した説明に別の非商用限定はありません。**出典・ライセンスリンク・変更表示を付けて検証用に採用する候補として推奨**します。一般的なプライバシー等の権利が残ることを理由に、明示された画像利用許諾まで否定しません。[配布情報](https://data.mendeley.com/datasets/m4kz5ygxrn/1)、[CC BY 4.0公式説明](https://creativecommons.org/licenses/by/4.0/)

作者論文のデータ収集節によると、インクと紙で採取し1200 ppiでスキャン、512×512へ切り出して画像強調を行っています。したがってスマホのピント・皮膚の反射を検証するセットではなく、**隆線が写った画像から安定して数値が返るかを見るセット**です。論文中の親子関係・医療用途の主張は本作品の要件や検証根拠として採用しません。[作者論文・データ収集節](https://www.ijraset.com/best-journal/quality-and-feature-analysis-of-parent-and-child-fingerprints-in-west-bengal-india)

### 取得後の進め方

1. Mendeley V1で `Download All` またはFilesから取得し、`docs/local/datasets/family/` に保存する。元データ・説明・条件をひとまとまりで保持する。
2. まず10〜20枚で実画像の画質・白黒極性・余白・ファイル名を確認する。本調査ではデータ本体の画質確認は未完了。
3. 処理の動作確認は100〜300枚程度から始め、必要なら全1,500枚を使う。枚数を「学習に十分」と自動判断せず、欠損率や数値の偏りを確認する。
4. 調整と評価に分けるなら家族単位で分割する案を採る。人物単位よりさらに強く、同じ家族・同じ元画像の加工版を両側に混ぜない。関係ラベルを音楽生成や表示には渡さない。
5. 公開Gitには画像や家族属性を入れず、DOI・ライセンス・加工手順・匿名の集計を残す。公開デモは自分たちの同意済み画像または人工サンプルを優先する。

出典例：Diptadip Maiti and Debashis Das (2023), “FAMILY FINGERPRINT DATASET”, Mendeley Data, V1, DOI: 10.17632/m4kz5ygxrn.1, CC BY 4.0。変更内容は実際に行ったcrop/グレースケール化等を追記します。

## 3. ほかに今回新しく確認した候補

| 候補 | 新しく分かったこと | 判断 |
| --- | --- | --- |
| [MBD: Multi-Biometric Dataset](https://data.mendeley.com/datasets/94ksjgbwnz/1) | 指紋・指静脈・虹彩・thermal faceを含む。MendeleyデータページでCC BY 4.0 | Finger_Print部分だけを試す追加候補。ただし画像数・取得機材・収集元を確認できず、FAMILYより後順位 |
| [Roboflow Fingerprint Segmentation](https://universe.roboflow.com/my-office-xwtpj/fingerprint-segmentation-gm8a9-cgi4y/dataset/1) | 配布ページがCC BY 4.0、元画像一覧990、v1は拡張後2,496画像。横反転と±15度回転で学習例を3倍にする設定を明示 | セグメンテーション例の追加候補。2,496人/独立画像とは数えない。実画像・元収集出典が未確認で、本番スマホ適合の第一候補にはしない |
| [MFP Mobile FingerPrint](https://ieee-dataport.org/documents/mfp-mobile-fingerprint) | 作者説明はスマホ約14cmから親指・人差し指を撮影。アクセス欄はDataPort Subscription必要と明記 | 技術的には近い。既存の購読/機関アクセスがあれば再評価するが、無料即時取得としては案内しない。ページ内スクリプトZIPだけからデータへのアクセス権を推定しない |
| [Skin Characteristics Dataset 1](https://figshare.com/articles/dataset/Skin_Characteristics_Dataset_1/1155434) | 調査上は品質・minutiae・皮膚特性の数値データ候補として見つかった | 中央ROIに必要な画像コーパスと確認できないので画像学習セットとして数えない |

Roboflow等の公開ページのCC表示を、第三者GitHubコードのライセンスと混同していません。一方で元収集の説明が十分でない候補は、その点を明示して後順位にしました。申請があるデータも使用禁止と断定せず、承認と用途条件が今回に合うか未確認という扱いです。

## 4. IMPOSE-SYNと生成器の再確認

**IMPOSE-SYN**：作者READMEはデータを学習・微調整向けに公開すると明記し、合成contactlessとして有望です。今回は公式Drive、GitHubのexample一覧、READMEに記載された例画像 `example/comparison/center.png` を確認しようとしましたが、ファイル内容を取得できませんでした。project Apache 2.0という事実は維持しつつ、別配布データのLICENSEを確認済みとはしません。優先して確認する先は[作者repo](https://github.com/Yu-Yy/IMPOSE)と[公式Drive](https://drive.google.com/drive/folders/1VYDTTkCG_iCnk-CjsgcqGLngyXOlSIZt?usp=sharing)です。

**Anguli**：IIScの公式ページはC++の合成指紋生成器と、完成したサンプル1K（61.5MB）・10K（615MB）の配布を案内しています。これは新規学習なしで量を揃える代替候補です。ただし確認できた公式ページでは、生成器の配布許諾と出力画像の公開利用条件を十分に分離できませんでした。mirrorの「open source」やLICENSEだけから出力の用途を確定しません。[IISc公式ページ](https://dsl.cds.iisc.ac.in/projects/Anguli/)

**SFinGe**：作者研究室は生成器とWindowsデモ版を案内しています。デモ版があることと、自由に配れる完成データがあることは別です。今回、出力画像をハッカソンで再利用する具体的条件を確認できなかったため、COLFISPOOF/FAMILYの取得より優先しません。[作者研究室](https://biolab.csr.unibo.it/sfinge.html)

生成器を動かす場合でも、合成模様を本物のスマホ写真として評価せず、実機評価を残します。今回、生成器の導入・モデル学習・画像生成は実施していません。

## 5. 今日の作業に落とすなら

1. **COLFISPOOFの20〜50枚**を材質を分けて選び、同じ中央crop→方向場→2特徴を通す。背景・反射・色が成功を偽装しないか見る。
2. **FAMILYの100〜300枚**で、数値範囲・欠損・同一画像の再現・処理時間を確認する。
3. **実機の自前写真を2〜4人、各指の撮り直しと失敗例付きで確認**し、最終の品質しきい値を調整する。公開データだけでスマホ品質が良いと結論しない。
4. 11/9中に抽出版としきい値を固定し、調整に使っていない人物/撮影回で確認、作曲側へ接続する。品質指標を音楽の個性に使わず、抽出不可は明示する。

これは短期の試験規模案です。方向場の計算は訓練不要、しきい値調整には実写、学習モデルを作るなら対象に合う教師ラベルと独立評価が必要です。人工物・押印・スマホ写真を混ぜた総枚数を性能根拠にしません。

## 6. 確認できた範囲と実物確認の状況

- 一次の配布ページ・条件・作者の収集説明を確認しました。COLFISPOOFの公式共有先は存在し、共有名まで取得できました。
- **データ本体のサンプル画像は、この環境では視覚確認できていません。** FAMILYの収集方法は作者論文本文で確認しましたが、配布PNGそのものの確認ではありません。
- Mendeleyの公開API、IMPOSE例画像、Nextcloudへの通常HTTPは名前解決に失敗しました。WebでもAPI/例画像/Driveは取得不可、NextcloudはJavaScript要求で一覧取得に至りませんでした。公開論文の画像取得も確認可能な画像として返らず、見たとは報告していません。
- 110MB/数GBの一括ダウンロード、アカウント作成、申請メール、条件への代理同意は行っていません。

今回は新しい有力な入手先と条件まで具体化しました。**すぐ試す優先順位はCOLFISPOOF→FAMILYへ更新**し、実画像の取得・目視確認は上記手順の最初に残します。

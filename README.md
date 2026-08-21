# ガバメントAI「源内」と段階的本人確認による子ども食堂DAO × Metaマルシェ 地方創生AXプロトタイプ

査読前ワーキングペーパー（非査読）に対応する、**再現可能な参考実装**です。  
政策の採択・予算措置・自治体への一般提供を示すものではありません。

| 項目 | 内容 |
|---|---|
| 著者 | 菅野敦也（Atsunari Sugano） |
| ORCID | [0009-0003-1371-5267](https://orcid.org/0009-0003-1371-5267) |
| Wikidata | [Q100455577](https://www.wikidata.org/wiki/Q100455577) |
| 版 | 0.1.0（2026-08-21） |
| コードライセンス | MIT（リポジトリ直下の `LICENSE`） |
| 文書ライセンス | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)（[`paper/LICENSE`](paper/LICENSE)） |
| ワーキングペーパー | [`paper/WORKING_PAPER.md`](paper/WORKING_PAPER.md) |
| 2ページブリーフ | [`paper/POLICY_BRIEF.md`](paper/POLICY_BRIEF.md) |

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22040861.svg)](https://doi.org/10.5281/zenodo.22040861)

---

## この成果物の役割

省庁・自治体・関係機関が決裁資料に載せるための材料は、次の三層です。

1. **証拠層（本リポジトリ + Zenodo）**: 版が固定され、引用でき、第三者が同じデモを再実行できる。
2. **制度層（ワーキングペーパー第6節）**: どの交付金・所管・法令の話なのかを切り分ける。
3. **実証層（まだない）**: 協定を結んだ1自治体の運用ログ。採用判断の本データはここにある。

GitHub と DOI は 1 を満たす装置です。2 と 3 の代替にはなりません。

---

## 事実と仮説

### 事実（デジタル庁の公表に依拠）

出典: [ガバメントAI「源内」｜デジタル庁](https://www.digital.go.jp/policies/genai)（2026年8月19日最終更新時点）

- **OSS 公開**: 2026年4月、源内はオープンソースとして公開されている。
- **大規模実証の対象**: 2026年度中に全府省庁 約18万人の政府職員が利用可能となる予定、と公表されている。
- **セキュリティの自己説明**: 政府統一基準に準拠し、デジタル庁内では機密性2情報を含むプロンプト入力、GSS 経由の SSO に対応すると説明されている。
- **横展開の4つの壁**: 「事例を知らない」「効果が不明瞭」「導入方法がわからない」「コストが高い」を、共通ルール・ドキュメント・OSS 化で取り除く方針が示されている。
- **自治体への提供**: 2026年8月19日、熊本地震の被災自治体等への**緊急提供**が公表されている。恒常的な全市区町村向け一般提供が制度化済み、という意味ではない。
- **国内 LLM**: 日本語・日本の文化・価値観に適合したモデルの調達・利用を進める方針が示されている。

源内の主対象は、2026年8月時点では政府職員・府省庁です。本プロトタイプが源内の公式アプリケーションであること、デジタル庁の推奨であること、を主張しません。

職員1人あたり約2か月の仮説検証が約3日に短縮された、といった個別効果の数字は、引用する場合はデジタル庁の当該資料の一次出典を本文で特定してください。本 README では、二次引用の誤記を避けるため効果数値の単独掲出を行いません。

### 仮説（本プロジェクト固有・未実証）

- 子ども食堂と地域マルシェを、監査可能な資金循環と段階的本人確認で接続すると、公金投入時の不正受給・説明責任の議論が具体化しやすい。
- OSS として公開すれば、先行自治体の実装を他団体が複製するコストが下がる。
- 源内（または同等の行政向け生成AI）は、提案要約・広報文案の下書きに使える。**職員確認なしの自動決定には使わない。**

仮説の検証指標は `generate_sanpo_yoshi_report()` の機械集計（入金・支出・概算食数・台帳整合）と、現地の実食数・満足度・事務時間を分けて記録する想定です。前者だけでは社会的効果の証明になりません。

---

## 本人確認：World ID は必須前提ではない

| 段階 | 想定 | 本コード |
|---|---|---|
| 0 | オフラインデモ | `identity_backend="world_id_mock"`（既定） |
| 1 | 既存の窓口確認・公的個人認証 | `identity_backend="public_credential"`（プレースホルダ） |
| 2 | World ID（ORB 等） | モックを Cloud API に差し替え |

公金・子ども・個人情報を扱う案件では、マイナンバーカード等の既存経路を既定にし、World ID を Sybil 耐性の**追加オプション**として比較検討するのが、制度上通りやすい順序です。暗号資産・NFT 収入は、本プロトタイプでは「将来の資金チャネル」として言及するに留め、デモの必須経路にはしていません。

---

## 公金投入の2障壁への対応（デモが示す範囲）

| 課題 | 仕組み | 限界 |
|---|---|---|
| 同一人物の多重登録 | `shokudo_operator_kyc` の nullifier | 実在確認の強度はバックエンド次第 |
| 台帳改ざん | ハッシュチェーンと `verify_chain_integrity()` | 運用端末の不正や初期入力の虚偽は検知しない |
| 使途の記録 | 支出時の運営者再認証 | 会計検査・監査法人の代替ではない |
| 領収書の二重請求 | `receipt_reference` の重複拒否 | 紙の真正性確認は別途必要 |
| 個人情報の最小化 | 氏名・住所を持たずハッシュのみ | 条例・委託契約上の整理は文書側で行う |

`export_audit_report()` は担当者が残高と整合性を確認するための**補助帳票**です。

---

## 構成

| 要素 | 役割 |
|---|---|
| `WorldIDVerifier` | World ID 検証のモック。live=True では未実装例外 |
| `PublicCredentialVerifier` | 公的確認のプレースホルダ |
| `GennaiAIAssistant` | 源内の入出力形を示すスタブ（実API非接続） |
| `Vendor` / `Sale` | Metaマルシェの出店・売上 |
| `KodomoShokudo` / `AuditLedger` | 食堂と改ざん検知台帳 |
| `DAOGovernance` | nullifier による一人一票 |
| `KodomoShokudoMetaMarcheEcosystem` | 統合 |
| `generate_sanpo_yoshi_report()` | 子ども・運営者・地域の機械集計 |

---

## 実行方法

Python 3.10 以降。外部パッケージは不要です。

```bash
python kodomo_shokudo_dao_meta_marche.py
python -m unittest tests.test_core
```

デモは仮想の入金・還元・支出と、多重登録・二重請求の拒否を JSON で出力します。

実サービスへ進める場合:

- World ID: `WorldIDVerifier.verify()` を Developer Portal の `/api/v2/verify/{app_id}` 検証結果の写像に替える。
- 源内: 取扱区分・SSO・プロンプト管理を、提供元の利用条件に従って別モジュールで実装する。本スタブを本番接続しない。

---

## 費用対効果について

現時点では**定性的な見込み**です。源内・World App が無償に近い既存インフラであること、本コードが MIT であることは初期検証コストを下げる方向に働きます。運用コスト削減幅は未測定です。2例目以降の複製コストが下がる、という主張は OSS の一般的性質に基づく仮説です。

---

## 相手別の次の一手

| 相手 | 本リポジトリで足りること | 別途必要なこと |
|---|---|---|
| デジタル庁 | 源内を公式アプリと誤認せず、横展開の4壁に対する OSS 事例として読める | 府省庁向け源内の利用条件との突合 |
| こども家庭庁・自治体こども部局 | 居場所づくりの資金の見え方のデモ | 既存補助・委託契約との接続 |
| 企画・デジタル担当 | オフラインで再現できる PoC | 情報セキュリティ・個人情報の庁内審査 |
| 財政・監査 | ハッシュチェーンと領収書重複拒否 | 会計規則に載る帳票と証拠書類 |

全国一斉導入ではなく、**実証1自治体**をゴールにするのが、README の仮説（魁がロールモデルになる）と整合します。

---

## 出典（構想の源泉）

機械可読な引用は `CITATION.cff`（GitHub の Cite this repository）を使ってください。

- [子ども食堂DAO政策提言](https://platform-clover.net/project/detail/1027)
- [DeSoc「子ども食堂DAOのPoC」](https://www.sunverdir.com/DeSoc)
- [Priority Blockspace for Humans](https://www.sunverdir.com/Priority-Blockspace-for-Humans)
- [子ども食堂DAO資金調達](https://www.sunverdir.com/fundraising)
- [Metaマルシェ](https://www.sunverdir.com/Meta-Marche)
- [SDGs Platform](https://www.sunverdir.com/SDGs-Platform)（内閣府地方創生SDGs官民連携プラットフォーム関連の紹介。過去の公的マッチング実績の継続性を示す）
- [note: 地方創生AXと源内](https://note.com/society/n/n830e905d8433)
- [ガバメントAI「源内」｜デジタル庁](https://www.digital.go.jp/policies/genai)

著者の他の関連発信(DAO-DeFi、kokusentoc、産学連携拠点に関するnote記事等)は、本文の個別の主張と直接結びつく形では引用していないため、ここには掲出していません。

---

## 支援・協業

研究と OSS を続けるための、採用・業務委託、公的実証（交付金・PoC）、CSR・企業版ふるさと納税・寄付を歓迎します。

- [LinkedIn](https://www.linkedin.com/in/sunverdir) / [Wantedly](https://www.wantedly.com/id/Arts) / [YOUTRUST](https://youtrust.jp/users/arts)
- GitHub Sponsor 導線: `.github/FUNDING.yml`

売り込み文ではなく、**実証協定の打診**を先に受けられる状態にすることが、採用に近い広報です。

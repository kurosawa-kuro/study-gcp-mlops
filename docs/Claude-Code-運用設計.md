# Claude Code 運用設計レビュー — 外部レビュアー提案 + 本リポでの採用状況

外部レビュアーから受け取った Claude Code 運用設計の提案 (CLAUDE.md 薄型化 / TASKS.md 運用 / DECISIONS.md / Plan Mode 運用ルール / `/compact` / RTK 検討) と、それに対する本リポ (`study-gcp-mlops`) での採用判断・反映結果を 1 ファイルにまとめる。**最初に「本リポでの採用状況」を読み、必要なら付録のレビュー原文を参照する**順序で構成。

---

## 本リポでの採用状況 (2026-05-02 反映済)

レビュー全 8 項目に対する判断と、本リポへ反映した変更:

| # | 提案 | 判断 | 反映先 |
|---|---|---|---|
| 1 | `CLAUDE.md` 薄型化 | **採用 (部分的)** | Phase 1 CLAUDE.md (142 → 86 行) / Phase 7 CLAUDE.md (151 → 133 行)。Phase 2/3/4/5 は元から薄い (30-35 行) ため変更なし。Phase 6 (179 行) は親 CLAUDE.md が "load-bearing" と明記しており不採用 |
| 2 | `docs/TASKS.md` 運用 | **採用 (全 7 Phase)** | 全 phase の `docs/TASKS.md` を新設。完了済 phase (1-6) は完了スナップショット形式、アクティブ Phase 7 は current-sprint 形式 (Wave 1 ✅ / Wave 2 🟡 / Wave 3 ⏳) |
| 3 | `docs/DECISIONS.md` 追加 | **既に先行実装済 (Phase 6/7)** | Phase 6/7 の `docs/decisions/` に ADR 0001〜0008 が稼働中。Phase 3/4/5 への展開は user 判断で見送り (実際に判断履歴が必要になった時点で追加する遅延運用) |
| 4 | Plan Mode 運用ルール | **採用 (運用慣習として、リポ docs には書かない)** | リポ側の docs ではなく Claude Code の `MEMORY.md` フィードバック層が自然 (新規ドキュメント化はしない) |
| 5 | `/compact` 運用 | **採用 (恒久情報は docs に書く方針)** | 会話圧縮は `/compact`、恒久的な設計判断は `docs/decisions/` ADR、作業進捗は `docs/TASKS.md`、仕様は `docs/01_仕様と設計.md` で棲み分け |
| 6 | 軽微修正は Copilot / 手修正 | **採用 (運用慣習)** | リポ side-effect なし |
| 7 | RTK (フック型ログ圧縮 OSS) | **不採用** | 学習リポなら `/compact` + docs 運用で代替可能。未検証 OSS のリスクがメリットを上回る。検証用リポで試す案も別 turn 送り |
| 8 | モデル使い分け | **採用 (運用慣習)** | リポ side-effect なし |

加えて以下を不採用とした (重複・load-bearing 配慮):

- **`CODING_RULES.md` / `DB_SCHEMA.md` / `API_SPEC.md` の新設**: 既に `docs/01_仕様と設計.md` (機能仕様+設計) / `infra/terraform/modules/data/*` + `pipeline/data_job/dataform/` (スキーマ正本) / `app/schemas/` + `app/api/routers/` (API 正本) が分散正本として機能。新設は二重管理を生む
- **`PROJECT_OVERVIEW.md` / `PHASES.md` の新設**: ルート `CLAUDE.md` (Phase テーブル含む) と `README.md` が役割を担っており、新設は重複

### 反映ファイル (今回の変更)

| 操作 | パス | 内容 |
|---|---|---|
| 新規 | `1〜7/*/docs/TASKS.md` | 全 7 phase の TASKS.md (完了スナップショット / current-sprint) |
| 編集 | `CLAUDE.md` (root) | 「## current sprint の正本」3 行を追記 (各 phase の TASKS.md 参照) |
| 編集 | `1/study-ml-foundations/CLAUDE.md` | 142 → 86 行。Configuration / Scripts / Docker / Dependencies / Testing 詳細を `docs/04_運用.md` へ移植 |
| 編集 | `1/study-ml-foundations/docs/04_運用.md` | 上記の受け皿 (76 → 145 行) |
| 編集 | `7/study-hybrid-search-gke/CLAUDE.md` | 151 → 133 行。「開発コマンド」表を要約し `docs/05_運用.md` 参照に。dead link 2 箇所 (`02_移行ロードマップ-Port-Adapter-DI.md` / `切り替え基盤.md`) を削除し `02_移行ロードマップ.md` 1 本に統合 |
| 編集 | `6/study-hybrid-search-pmle_old/CLAUDE.md` | 先頭に `> ARCHIVED. ...` バナー追加 (誤参照防止) |

### 権威順位 (採用後)

```
docs/02_移行ロードマップ.md  > docs/TASKS.md > docs/01_仕様と設計.md > README.md > CLAUDE.md
(長期 backlog/index)        (current-sprint) (機能仕様+設計)         (入口)      (Claude 向けガイド)
```

恒久的な判断履歴は `docs/decisions/` (Phase 1/2/6/7 で稼働、ADR 形式)。

### 検証 (新セッションでの体感確認)

ユーザ本人が新セッションを Phase 7 ルートで開き「次にやることは?」と聞いたとき、Claude が `docs/TASKS.md` を最初に読みに行くか手動確認するのが最も実効的。

---

## ファイル名・配置の提案 (実施は user 判断)

現ファイル名 `docs/Claude-Code-tech.md` は内容が判別しにくい。以下のいずれかを推奨:

- `docs/Claude-Code-運用設計.md` (推奨) — 内容と一致
- `docs/Claude-Code-運用設計レビュー.md` — レビュー記録だと明示

`docs/conventions/命名規約.md` (コード規約) に統合する選択肢もあるが、内容が「Claude Code 運用設計レビュー」と「コード命名規約」で性格が違うため、別ファイルのままが分かりやすい。

---

## 付録: レビュー原文 (外部レビュアーから受領)

> 以下、外部レビュアーから受領した原文。本リポでの採用判断は上記「採用状況」を参照。

### 1. 結論

この案は、**方向性はかなり正しい**。ただし、個人開発・学習リポジトリ運用にそのまま入れるなら、**「節約術」ではなく「AI 開発運用設計」に昇格させた方が良い**。

良い点 3 つ:

1. CLAUDE.md を薄くする
2. `docs/TASKS.md` で作業単位を管理する
3. Claude Code を「全部やる作業員」ではなく「高価値判断担当」に寄せる

注意すべき点 2 つ:

1. RTK は効果がありそうだが、導入前に安全性・安定性チェックが必要
2. `/compact` は万能ではなく、圧縮後に重要文脈が欠落するリスクがある

### 2. 理由 — 文脈設計の話である

この案の本質は、単なるトークン削減ではなく、**Claude Code に渡す文脈を設計する話**。

| 失敗パターン | 原因 |
|---|---|
| 勝手に設計を変える | 読ませる仕様が多すぎる / 優先順位が曖昧 |
| 余計なファイルを触る | タスク境界が曖昧 |
| 途中で精度が落ちる | 会話・ログ・修正履歴が肥大化 |
| 修正往復が増える | 最初の作業粒度が大きすぎる |
| コストが増える | AI にやらせる作業と自分でやる作業の分離がない |

一番価値が高いのは「トークン節約」ではなく **「文脈汚染を防ぐ」** ところ。

### 3. シナリオ別評価

#### 3.1 学習リポ運用にはかなり有効

Phase 制の学習リポジトリや Port/Adapter, MLOps, GCP, Directus/Neon 系の個人アプリで、`CLAUDE.md` に全部詰めると破綻する。むしろこう分ける:

```text
CLAUDE.md
docs/
  PROJECT_OVERVIEW.md
  ARCHITECTURE.md
  TASKS.md
  CODING_RULES.md
  DB_SCHEMA.md
  API_SPEC.md
  PHASES.md
```

`CLAUDE.md` は入口だけ:

```md
# CLAUDE.md
このプロジェクトでは docs/ を参照して作業する。

必ず最初に読む:
- docs/PROJECT_OVERVIEW.md
- docs/TASKS.md

必要な場合のみ読む:
- docs/ARCHITECTURE.md
- docs/DB_SCHEMA.md
- docs/API_SPEC.md
- docs/CODING_RULES.md

禁止:
- 指示されていない大規模リファクタリング
- docs/TASKS.md にない機能追加
- DB schema の勝手な変更
```

#### 3.2 `TASKS.md` が一番効く

`/compact` でも RTK でもなく、**`TASKS.md` 運用** が実務効果が高い。Claude Code の失敗は技術力不足より「今どこまで終わっていて、次に何をするかが曖昧」で起きる。

```md
# TASKS.md

## 現在の目的
不動産データ管理アプリの CRUD 最小構成を作る。

## 今回の作業対象
- 物件一覧ページ
- 物件詳細ページ
- 物件登録フォーム

## 今回はやらない
- 認証 / 更新 / 削除 / 権限管理 / 外部 API 連携

## 完了条件
- 一覧表示できる / 詳細表示できる / 新規登録できる / DB に保存される / README の起動手順で再現できる

## 実装済み
- [x] PostgreSQL 接続
- [x] 物件テーブル作成

## 未実装
- [ ] 一覧 API / 詳細 API / 登録 API / フロント 3 画面
```

#### 3.3 Plan Mode は中規模以上のみ

| 作業 | Plan Mode |
|---|---|
| typo 修正 / 1 ファイル軽微修正 / UI 文言変更 | 不要 |
| API 追加 / 複数ファイル変更 | 推奨 |
| DB schema 変更 / アーキテクチャ変更 / Phase 設計 | 必須 |

「戻すのが面倒な変更」だけ Plan Mode 必須。

### 4. 破綻条件

#### 4.1 `docs/` が肥大化して結局全部読ませる

`CLAUDE.md` を薄くしても、毎回「docs 配下を全部読んでから実装して」と言うなら無意味。**今回必要な docs だけ読む** が正解。

#### 4.2 `/compact` 後に重要な設計判断が落ちる

圧縮で以下が落ちると危険:

- なぜその設計にしたか / やってはいけないこと / 途中で却下した案 / DB 変更の理由 / 破壊的変更の注意点

長期的に残すべき内容は `/compact` 頼みではなく **`docs/TASKS.md` や `docs/DECISIONS.md` に明文化**。

```text
会話の一時圧縮      → /compact
恒久的な設計判断    → docs/DECISIONS.md
作業進捗            → docs/TASKS.md
仕様                → docs/SPEC.md
```

#### 4.3 RTK を無検証で入れる

Claude Code のフックに入るツールなので、導入前に確認すべき項目:

| 確認点 | 理由 |
|---|---|
| GitHub スター数・更新頻度 | 放置 OSS リスク |
| コード内容 | コマンド出力を扱うため |
| Claude 設定ファイルへの変更内容 | グローバル設定を触る可能性 |
| 無効化方法 | 問題発生時に戻せる必要 |
| ログ欠落リスク | 失敗原因まで削られると逆効果 |

いきなり本命リポジトリに入れず、**検証用リポジトリで試す**。

### 5. 実務優先順位 (レビュアー所感)

| 優先 | 採用 | 判断 |
|---|---|---|
| 1 | `CLAUDE.md` 薄型化 | 即採用 |
| 2 | `docs/TASKS.md` 運用 | 即採用 |
| 3 | `docs/DECISIONS.md` 追加 | 追加すべき |
| 4 | Plan Mode 運用ルール | 採用 |
| 5 | `/compact` | 採用。ただし恒久情報は docs へ |
| 6 | 軽微修正は Copilot / 手修正 | 採用 |
| 7 | RTK | 検証後に採用 |
| 8 | モデル使い分け | 使えるなら採用、運用依存 |

### 6. 補正後の結論

```text
CLAUDE.md      = 憲法・入口
docs/SPEC.md   = 仕様
docs/ARCHITECTURE.md = 設計
docs/TASKS.md  = 作業状態
docs/DECISIONS.md = 判断履歴
scripts/       = 繰り返し作業の自動化
/compact       = 会話圧縮
Plan Mode      = 戻しにくい変更前の安全装置
RTK            = ログ圧縮、検証後に導入
```

この案は「トークン節約」ではなく、**Claude Code を業務用に安定運用するためのミニ開発管理設計** として見るべき。

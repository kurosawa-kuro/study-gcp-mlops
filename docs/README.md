# docs

ルート `docs/` は、全フェーズ共通の方針・移行作業・補助資料を管理するディレクトリ。
`01_仕様と設計.md` / `03_実装カタログ.md` / `04_運用.md` は **Phase 横断ハブ** として各フェーズ正本へ案内する。
トップ入口は `../README.md`。

## まず読むファイル

- `05_Docker配置規約.md`  
  - Dockerfile / compose 関連の共通ルール
- `05_問題点.md`  
  - 全体課題メモ
- `archive/README.md`  
  - 過去ログの退避方針
- `phases/README.md`
  - Phase 1〜5 の docs 入口（phase サブフォルダ）

## 位置付け

- 各フェーズの正本仕様は、**フェーズ配下の `README.md` / `CLAUDE.md` / `docs/`**
- ルート `docs/` は、フェーズ横断の管理情報を置く場所
- 実装詳細の参照先は、必ず対象フェーズ配下を優先する
- Phase 3/4/5 のハイブリッド検索は **LightGBM + multilingual-e5 + Meilisearch** を必須構成とする

## 補助資料

- `フォルダ構成整合_作業設計.md`
- `パイプラインとジョブ.md`

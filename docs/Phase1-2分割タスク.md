# Phase 1-2 分割タスク（整理版）

更新日: 2026-04-22

## 結論

Phase 1 -> Phase 1+2 分割は、実装・テスト・主要ドキュメント更新まで完了。  
本ファイルは詳細ログを削除し、最終決定事項と最小の残課題のみ保持する。

---

## 最終決定事項

- Phase 1 は **ML 基礎に集中**（学習・評価・保存）
- Phase 2 は **App / Pipeline / Port-Adapter** を担当
- Phase 1 と Phase 2 は **コード共有 import しない**（独立運用）
- アーティファクト共有は **不採用**（Phase 2 は Phase 2 内で学習して自己完結）
- 命名方針:
  - Phase 1: `ml/common/`
  - Phase 2: ルート `common/`

---

## 完了済み（要約）

- Phase 番号の再配置（旧 2-4 -> 新 3-5）
- Phase 2 新設（core/ports/adapters/container, pipeline jobs, app 配線）
- Phase 1 から推論系の切り離し
- Phase 1/2 のテスト整備と主要検証
- ルート `README.md` / `CLAUDE.md` / `docs/README.md` の分割後トーンへ更新

---

## 現在の残課題（最小）

- なし（2026-04-22 時点）

補足:

- `tools/check_docker_layout.py` は現行フェーズ番号・パスに整合済み（`Result: PASSED`）
- 分割作業ログの長文履歴は、当面は本書の整理版を維持し、必要時に `docs/archive/` へ退避する方針で確定

---

## 参考

フェーズ正本は各ディレクトリ配下を参照:

- `1/study-ml-foundations/README.md`
- `2/study-ml-app-pipeline/README.md`
- 各 phase の `CLAUDE.md` と `docs/`

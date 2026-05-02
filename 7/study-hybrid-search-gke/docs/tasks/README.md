# tasks/ — current sprint + 長期 backlog

Phase 7 の作業状態を集約。**新セッションは `TASKS.md` から読む**。

## 収録ファイル

| ファイル | 役割 | いつ読むか |
|---|---|---|
| [`TASKS.md`](TASKS.md) | current sprint (Wave 1 ✅ / Wave 2 🟡 / Wave 3 ⏳ + 残作業) | **新セッション最初**。「次にやることは?」「今のスコープは?」 |
| [`02_移行ロードマップ.md`](02_移行ロードマップ.md) | 決定的仕様 + 権威 1 位 + 長期 backlog + 実装タスク詳細 (554 行) | スコープ・優先度を判断する時。Wave 単位の詳細が必要な時 |

## 棲み分け (重要)

- **`TASKS.md` = current sprint の抜粋**。短く、毎セッション参照。
- **`02_移行ロードマップ.md` = 長期 backlog/index + 決定的仕様**。詳細な Wave 計画と権威。

権威順位: `02_移行ロードマップ.md > TASKS.md`。両者が矛盾する時は 02 を信じる。

## 関連

- 設計根拠: [`../architecture/01_仕様と設計.md`](../architecture/01_仕様と設計.md)
- 実装場所: [`../architecture/03_実装カタログ.md`](../architecture/03_実装カタログ.md)
- 過去判断 (なぜそうなった): [`../decisions/`](../decisions/) (ADR 0001〜0008)

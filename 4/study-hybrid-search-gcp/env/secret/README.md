# env/secret/

ローカル開発用クレデンシャル置き場。

**このディレクトリは `.gitignore` 対象。** README.md のみコミットする。

## ファイル

| ファイル | 用途 | 参照箇所 |
|---|---|---|
| `credential.yaml` | flat YAML でローカル用シークレットを集約（`meili_master_key` など） | `common/src/common/config.py::BaseAppSettings` が `YamlConfigSettingsSource` で読み込む |

非クレデンシャル設定（project_id, region, artifact_repo 等）は `env/config/setting.yaml`。

## 本番環境との関係

本番 (Cloud Run) は **Secret Manager** 経由で環境変数に注入される（`--set-secrets=MEILI_MASTER_KEY=meili-master-key:latest`）。
`credential.yaml` はローカル開発でのみ使われる。

## 形式

```yaml
# flat key: value のみ。ネスト・リスト非対応。
meili_master_key: "<your-meilisearch-master-key>"
```

値は `BaseAppSettings` の対応フィールド名と **小文字キーで一致** させる
（pydantic-settings が大文字小文字を区別せずに解決）。

## Secret Manager への値投入手順（本番 / 初回のみ）

```bash
export MEILI_MASTER_KEY="<Meilisearch の Master Key>"
echo -n "$MEILI_MASTER_KEY" | gcloud secrets versions add meili-master-key --data-file=-
```

## 新しいシークレット追加手順

1. `BaseAppSettings` または派生 Settings に `secret_name: SecretStr = SecretStr("")` フィールドを追加
2. `credential.yaml` に同名キーを flat YAML で追加
3. 本番で必要なら `gcloud secrets versions add <secret-name> --data-file=-` で値を投入し、
   deploy workflow の `--set-secrets=SECRET_NAME=<secret-name>:latest` に追加

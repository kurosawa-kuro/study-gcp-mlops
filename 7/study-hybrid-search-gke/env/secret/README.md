# env/secret/

ローカル開発用クレデンシャル置き場。

**このディレクトリは `.gitignore` 対象。** README.md のみコミットする。

## ファイル

| ファイル | 用途 | 参照箇所 |
|---|---|---|
| `credential.yaml` | flat YAML でローカル用シークレットを集約（`meili_master_key` など） | `app/services/config.py::ApiSettings` が `YamlConfigSettingsSource` で読み込む |

非クレデンシャル設定（project_id, region, artifact_repo 等）は `env/config/setting.yaml`。

## 本番環境との関係

本番 (GKE Pod) は **Secret Manager → Kubernetes Secret** 経由で環境変数に注入される。

Secret Manager の値を Kubernetes Secret に同期する手順（Draft / 手動）:

```bash
# 1. Secret Manager に値を投入（初回のみ）
echo -n "<your-meilisearch-master-key>" | \
  gcloud secrets versions add meili-master-key --data-file=-

# 2. Kubernetes Secret を作成（ExternalSecrets Operator がない場合は手動同期）
kubectl create secret generic meili-master-key \
  --from-literal=value="<your-meilisearch-master-key>" \
  --namespace search

# 3. Deployment の env で参照（infra/manifests/search-api/deployment.yaml）
# env:
#   - name: MEILI_MASTER_KEY
#     valueFrom:
#       secretKeyRef:
#         name: meili-master-key
#         key: value
```

`credential.yaml` はローカル開発でのみ使われる。

## 形式

```yaml
# flat key: value のみ。ネスト・リスト非対応。
meili_master_key: "<your-meilisearch-master-key>"
```

値は `ApiSettings` の対応フィールド名と **小文字キーで一致** させる
（pydantic-settings が大文字小文字を区別せずに解決）。

## 新しいシークレット追加手順

1. `ApiSettings` または派生 Settings に `secret_name: SecretStr = SecretStr("")` フィールドを追加
2. `credential.yaml` に同名キーを flat YAML で追加
3. Secret Manager に `gcloud secrets create` でコンテナを作成
4. 本番では `kubectl create secret generic` で Kubernetes Secret に同期し、Deployment の env で参照

"""DI 配線。settings から adapters を組み立て、app.lifespan / job entrypoint から参照。

TBD: 以下の build_container(settings) -> Container 形式を想定。
- Container は dataset / model_store / tracker の 3 属性を保持
- FastAPI lifespan / pipeline job main() の両方から呼び出せるよう純関数で構築
"""

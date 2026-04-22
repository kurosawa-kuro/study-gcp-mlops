from __future__ import annotations

from scripts.dev import deploy_all


def test_deploy_all_runs_non_empty_search_gate(monkeypatch) -> None:
    order: list[str] = []

    monkeypatch.setattr(deploy_all, "env", lambda _name: "dummy")
    monkeypatch.setattr(deploy_all, "_recover_wif_state", lambda _project_id: order.append("recover"))
    monkeypatch.setattr(deploy_all, "tf_bootstrap_main", lambda: order.append("tf_bootstrap") or 0)
    monkeypatch.setattr(deploy_all, "tf_init_main", lambda: order.append("tf_init") or 0)
    monkeypatch.setattr(deploy_all, "sync_dataform_main", lambda: order.append("sync_dataform") or 0)
    monkeypatch.setattr(deploy_all, "tf_plan_main", lambda: order.append("tf_plan") or 0)
    monkeypatch.setattr(deploy_all, "run", lambda *_a, **_kw: order.append("terraform_apply"))
    monkeypatch.setattr(deploy_all, "deploy_training_main", lambda: order.append("deploy_training") or 0)
    monkeypatch.setattr(deploy_all, "run_training_job_main", lambda: order.append("run_training") or 0)
    monkeypatch.setattr(deploy_all, "deploy_api_main", lambda: order.append("deploy_api") or 0)
    monkeypatch.setattr(deploy_all, "seed_minimal_main", lambda: order.append("seed_minimal") or 0)
    monkeypatch.setattr(deploy_all, "search_check_main", lambda: order.append("search_gate") or 0)
    monkeypatch.setattr(
        deploy_all, "search_component_check_main", lambda: order.append("component_gate") or 0
    )
    monkeypatch.setattr(
        deploy_all, "training_label_seed_main", lambda: order.append("label_seed") or 0
    )
    monkeypatch.setattr(
        deploy_all, "_assert_training_data_ready", lambda _pid: order.append("training_data_gate")
    )

    rc = deploy_all.main()
    assert rc == 0
    assert order[-5:] == [
        "search_gate",
        "component_gate",
        "label_seed",
        "training_data_gate",
        "run_training",
    ]


def test_deploy_all_fails_when_search_gate_fails(monkeypatch) -> None:
    monkeypatch.setattr(deploy_all, "env", lambda _name: "dummy")
    monkeypatch.setattr(deploy_all, "_recover_wif_state", lambda _project_id: None)
    monkeypatch.setattr(deploy_all, "tf_bootstrap_main", lambda: 0)
    monkeypatch.setattr(deploy_all, "tf_init_main", lambda: 0)
    monkeypatch.setattr(deploy_all, "sync_dataform_main", lambda: 0)
    monkeypatch.setattr(deploy_all, "tf_plan_main", lambda: 0)
    monkeypatch.setattr(deploy_all, "run", lambda *_a, **_kw: None)
    monkeypatch.setattr(deploy_all, "deploy_training_main", lambda: 0)
    monkeypatch.setattr(deploy_all, "run_training_job_main", lambda: 0)
    monkeypatch.setattr(deploy_all, "deploy_api_main", lambda: 0)
    monkeypatch.setattr(deploy_all, "seed_minimal_main", lambda: 0)
    monkeypatch.setattr(deploy_all, "search_check_main", lambda: 1)
    monkeypatch.setattr(deploy_all, "search_component_check_main", lambda: 0)
    monkeypatch.setattr(deploy_all, "training_label_seed_main", lambda: 0)
    monkeypatch.setattr(deploy_all, "_assert_training_data_ready", lambda _pid: None)

    rc = deploy_all.main()
    assert rc == 1

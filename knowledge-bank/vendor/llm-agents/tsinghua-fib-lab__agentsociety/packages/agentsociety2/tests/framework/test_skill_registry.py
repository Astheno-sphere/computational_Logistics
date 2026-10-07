from agentsociety2.agent.base.skill_registry import SkillRegistry


def test_skill_registry_builtin_namespaced_ids_and_explicit_script():
    registry = SkillRegistry()
    added = registry.scan_builtin()

    assert "built-in@daily-guidance" in added
    assert "# Daily Guidance" in registry.read_skill_doc("built-in@daily-guidance")
    assert registry.get("built-in@daily-guidance").script == "scripts/daily_guidance.py"
    assert "# Daily Guidance Examples" in registry.read_skill_file(
        "built-in@daily-guidance",
        "references/examples.md",
    )
    assert registry.get("built-in@observation") is None


def test_skill_registry_no_override_between_namespaces(tmp_path):
    custom_root = tmp_path / "skills"
    skill_root = custom_root / "memory"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "---\nname: memory\ndescription: custom memory\n---\n",
        encoding="utf-8",
    )

    registry = SkillRegistry()
    registry.scan_builtin()
    registry.scan_custom(custom_root)

    assert registry.get("built-in@memory") is None
    assert registry.get("custom@memory") is not None
    assert {item.skill_id for item in registry.find_by_name("memory")} == {
        "custom@memory"
    }


def test_skill_registry_env_id_and_hook_metadata(tmp_path):
    env_root = tmp_path / "env_skills"
    skill_root = env_root / "rhythm"
    skill_root.mkdir(parents=True)
    (skill_root / "hook.py").write_text("print('hook')\n", encoding="utf-8")
    (skill_root / "SKILL.md").write_text(
        "---\n"
        "name: rhythm\n"
        "description: rhythm hook\n"
        "hooks:\n"
        "  pre_step: hook.py\n"
        "  post_step: hook.py\n"
        "---\n",
        encoding="utf-8",
    )

    registry = SkillRegistry()
    added = registry.scan_env(env_root, "SomeEnv")

    assert added == ["env:SomeEnv@rhythm"]
    descriptor = registry.get("env:SomeEnv@rhythm")
    assert descriptor.hooks == {"pre_step": "hook.py", "post_step": "hook.py"}
    assert [item.skill_id for item in registry.list_hooks("pre_step")] == [
        "env:SomeEnv@rhythm"
    ]


def test_skill_registry_resource_files_include_root_and_all_folders(tmp_path):
    custom_root = tmp_path / "skills"
    skill_root = custom_root / "wide"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "---\nname: wide\ndescription: wide resources\n---\n",
        encoding="utf-8",
    )
    (skill_root / "README.md").write_text("root note\n", encoding="utf-8")
    (skill_root / "scripts").mkdir()
    (skill_root / "scripts" / "run.py").write_text("print('run')\n", encoding="utf-8")
    (skill_root / "assets" / "schemas").mkdir(parents=True)
    (skill_root / "assets" / "schemas" / "state.json").write_text(
        "{}\n",
        encoding="utf-8",
    )
    (skill_root / ".hidden.md").write_text("hidden\n", encoding="utf-8")
    (skill_root / "__pycache__").mkdir()
    (skill_root / "__pycache__" / "run.cpython-311.pyc").write_bytes(b"cache")

    registry = SkillRegistry()
    registry.scan_custom(custom_root)

    descriptor = registry.get("custom@wide")
    assert descriptor is not None
    assert descriptor.resource_files() == [
        "assets/schemas/state.json",
        "README.md",
        "scripts/run.py",
        "SKILL.md",
    ]


def test_skill_registry_deprecated_builtin_skills_are_not_scanned():
    registry = SkillRegistry()
    registry.scan_builtin()

    assert registry.get("built-in@cognition") is None
    assert registry.get("built-in@rhythm") is None
    assert [item.skill_id for item in registry.list_hooks("pre_step")] == [
        "built-in@daily-guidance"
    ]

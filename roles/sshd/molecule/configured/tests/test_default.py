from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import pytest
from ansible.parsing.dataloader import DataLoader
from jinja2 import ChainableUndefined
from jinja2.nativetypes import NativeEnvironment

# --- helper ----------------------------------------------------------------


def pp_json(json_thing, sort=True, indents=2):

    if type(json_thing) is str:
        print(json.dumps(json.loads(json_thing), sort_keys=sort, indent=indents))
    else:
        print(json.dumps(json_thing, sort_keys=sort, indent=indents))

    return None


# --- paths -----------------------------------------------------------------


def base_directory() -> tuple[Path, Path]:
    """
    Returns:
      role_dir: role root (contains defaults/, vars/, tasks/, ...)
      scenario_dir: molecule scenario dir (contains group_vars/, ...)
    """
    cwd = Path.cwd()

    # pytest läuft je nach tox/molecule entweder im scenario/tests oder im role-root
    if (cwd / "group_vars").is_dir():
        # .../molecule/<scenario>/tests -> role root ist ../..
        return (cwd / "../..").resolve(), cwd.resolve()

    scenario = os.environ.get("MOLECULE_SCENARIO_NAME", "default")
    return cwd.resolve(), (cwd / "molecule" / scenario).resolve()


def _normalize_os(distribution: str) -> Optional[str]:
    d = (distribution or "").strip().lower()
    if d in ("debian", "ubuntu"):
        return "debian"
    if d in ("arch", "artix"):
        return f"{d}linux"
    return None


# --- load vars files (YAML) ------------------------------------------------


def _load_vars_file(loader: DataLoader, file_base: Path) -> Dict[str, Any]:
    """
    file_base ohne Extension übergeben, z.B. role_dir/'defaults'/'main'
    Lädt main.yml oder main.yaml via Ansible DataLoader (Vault kompatibel).
    """
    for ext in ("yml", "yaml"):
        p = file_base.with_suffix(f".{ext}")
        if not p.is_file():
            continue

        data = loader.load_from_file(str(p))
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise TypeError(f"{p} must be a mapping/dict, got {type(data)}")
        return data

    return {}


# --- jinja rendering (multi-pass) ------------------------------------------

_JINJA_MARKER = re.compile(r"({{.*?}}|{%-?.*?-%}|{#.*?#})", re.S)


def _find_unrendered_templates(obj: Any, prefix: str = "") -> List[str]:
    found: List[str] = []

    if isinstance(obj, str):
        if _JINJA_MARKER.search(obj):
            found.append(prefix or "<root>")
        return found

    if isinstance(obj, Mapping):
        for k, v in obj.items():
            key = str(k)
            found.extend(
                _find_unrendered_templates(v, f"{prefix}.{key}" if prefix else key)
            )
        return found

    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray)):
        for i, v in enumerate(obj):
            found.extend(_find_unrendered_templates(v, f"{prefix}[{i}]"))
        return found

    return found


def _make_jinja_env() -> NativeEnvironment:
    """
    NativeEnvironment: gibt bei reinen Expressions native Typen zurück,
    sonst Strings. Undefined ist 'chainable', damit ansible_facts.foo.bar
    nicht hart explodiert, sondern Undefined liefert (ähnlich fail_on_undefined=False).
    """
    env = NativeEnvironment(undefined=ChainableUndefined, autoescape=False)

    # Ansible-ähnliche lookup/query Minimalimplementierung (nur env erlaubt)
    def _lookup(plugin: str, term: Any, *rest: Any, **kwargs: Any) -> Any:
        if plugin != "env":
            raise ValueError(
                f"lookup('{plugin}', ...) not supported in tests (allowlist: env)"
            )
        # Ansible lookup('env','X') -> '' wenn nicht gesetzt (damit default(..., true) greift)
        if isinstance(term, (list, tuple)):
            vals = [os.environ.get(str(t), "") for t in term]
            return vals[0] if kwargs.get("wantlist") is False else vals
        return os.environ.get(str(term), "")

    def _query(plugin: str, term: Any, *rest: Any, **kwargs: Any) -> List[Any]:
        # query() ist wantlist=True
        kwargs["wantlist"] = True
        res = _lookup(plugin, term, *rest, **kwargs)
        return res if isinstance(res, list) else [res]

    env.globals["lookup"] = _lookup
    env.globals["query"] = _query
    return env


def _render_obj(
    env: NativeEnvironment, obj: Any, ctx: Dict[str, Any], *, skip_keys: frozenset[str]
) -> Any:
    if isinstance(obj, str):
        if not _JINJA_MARKER.search(obj):
            return obj
        tmpl = env.from_string(obj)
        return tmpl.render(**ctx)

    if isinstance(obj, Mapping):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            ks = str(k)
            if ks in skip_keys:
                out[ks] = v
            else:
                out[ks] = _render_obj(env, v, ctx, skip_keys=skip_keys)
        return out

    if isinstance(obj, list):
        return [_render_obj(env, v, ctx, skip_keys=skip_keys) for v in obj]

    if isinstance(obj, tuple):
        return tuple(_render_obj(env, v, ctx, skip_keys=skip_keys) for v in obj)

    return obj


def render_all_vars(data: Dict[str, Any], passes: int = 8) -> Dict[str, Any]:
    """
    Multi-pass: damit Werte wie
      system_architecture -> ...,
      und danach defaults_release.file -> ...{{ system_architecture }}...
    sauber aufgelöst werden.
    """
    env = _make_jinja_env()

    current: Dict[str, Any] = data
    last_leftovers: Optional[List[str]] = None

    for _ in range(max(1, passes)):
        # Kontext ist immer der aktuelle Stand
        rendered = _render_obj(
            env, current, current, skip_keys=frozenset({"ansible_facts"})
        )
        if not isinstance(rendered, dict):
            raise TypeError(f"Rendered vars are not a dict anymore: {type(rendered)}")

        leftovers = _find_unrendered_templates(rendered)
        if not leftovers:
            return rendered

        # kein Fortschritt mehr
        if leftovers == last_leftovers:
            current = rendered
            break

        last_leftovers = leftovers
        current = rendered

    # optional: hart fehlschlagen, wenn noch Templates übrig sind (sonst wird es still falsch)
    if os.environ.get("ANSIBLE_TEST_ALLOW_UNRESOLVED_TEMPLATES", "0") != "1":
        leftovers = _find_unrendered_templates(current)
        if leftovers:
            raise AssertionError(
                "Unresolved templates after rendering:\n- " + "\n- ".join(leftovers)
            )

    return current


# --- pytest fixture --------------------------------------------------------


@pytest.fixture()
def get_vars(host) -> Dict[str, Any]:
    role_dir, scenario_dir = base_directory()

    loader = DataLoader()
    loader.set_basedir(str(role_dir))

    distribution = getattr(host.system_info, "distribution", "") or ""
    os_id = _normalize_os(distribution)

    merged: Dict[str, Any] = {}
    merged.update(_load_vars_file(loader, role_dir / "defaults" / "main"))
    merged.update(_load_vars_file(loader, role_dir / "vars" / "main"))

    if os_id:
        merged.update(_load_vars_file(loader, role_dir / "vars" / os_id))

    merged.update(_load_vars_file(loader, scenario_dir / "group_vars" / "all" / "vars"))

    # Facts als Input (keine Templates)
    setup = host.ansible("setup")
    facts = setup.get("ansible_facts", {}) if isinstance(setup, dict) else {}
    if isinstance(facts, dict):
        merged["ansible_facts"] = facts
        merged.setdefault(
            "ansible_system", facts.get("system") or facts.get("ansible_system")
        )
        merged.setdefault(
            "ansible_architecture",
            facts.get("architecture") or facts.get("ansible_architecture"),
        )

    result = render_all_vars(merged, passes=8)

    return result


# --- tests -----------------------------------------------------------------


def local_facts(host):
    """
    return local facts
    """
    return (
        host.ansible("setup")
        .get("ansible_facts")
        .get("ansible_local")
        .get("sshd")
    )


@pytest.mark.parametrize(
    "dirs",
    [
        "/etc/ssh",
        "/etc/ssh/ssh_config.d",
        "/etc/ssh/sshd_config.d",
    ],
)
def test_directories(host, dirs):
    d = host.file(dirs)
    assert d.is_directory
    assert d.exists


@pytest.mark.parametrize(
    "files",
    [
        "/etc/ssh/ssh_config",
        "/etc/ssh/sshd_config",
        "/etc/ssh/ssh_host_ecdsa_key",
        "/etc/ssh/ssh_host_ecdsa_key.pub",
        "/etc/ssh/ssh_host_ed25519_key",
        "/etc/ssh/ssh_host_ed25519_key.pub",
        "/etc/ssh/ssh_host_rsa_key",
        "/etc/ssh/ssh_host_rsa_key.pub",
        "/etc/ssh/sshd_config.d/match_users.conf",
        "/etc/ssh/sshd_config.d/subsystem.conf",
    ],
)
def test_files(host, files):
    f = host.file(files)
    assert f.is_file
    assert f.exists


def test_version(host):
    config_file = "/etc/ssh/sshd_config"
    content = host.file(config_file).content_string

    assert "AddressFamily  any" in content


def test_service(host):

    service = host.service("sshd")
    assert service.is_enabled
    assert service.is_running


def test_open_port(host):
    """ """
    for i in host.socket.get_listening_sockets():
        print(i)

    assert host.socket("tcp://0.0.0.0:22").is_listening
    assert host.socket("tcp://172.17.0.2:2222").is_listening

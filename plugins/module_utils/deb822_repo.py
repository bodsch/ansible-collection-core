#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from ansible.module_utils.urls import fetch_url

_FILENAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class KeyResult:
    """
    Result of key management operations.

    Attributes:
        changed: Whether the operation modified (or would modify in check mode) any managed key material.
        key_path: Path to the keyring file that should be referenced by ``Signed-By`` (if applicable).
        deb_path: Path to a cached keyring ``.deb`` file when ``method=deb`` is used.
        package_name: Name of the keyring package (when ``method=deb`` is used and the name could be determined).
        package_version: Package version from the downloaded ``.deb`` (when ``method=deb`` is used).
        messages: Human-readable messages describing performed actions.
    """

    changed: bool
    key_path: Optional[str]
    deb_path: Optional[str]
    package_name: Optional[str]
    package_version: Optional[str]
    messages: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RepoResult:
    """
    Result of repository file management.

    Attributes:
        changed: Whether the repository file was created/updated (or would be updated in check mode).
        repo_path: Absolute path of the managed ``.sources`` file.
        rendered: Rendered deb822 file content (newline terminated).
    """

    changed: bool
    repo_path: str
    rendered: str


@dataclass(frozen=True)
class Deb822RepoSpec:
    """
    Minimal deb822 stanza representation for APT ``.sources`` files.

    This data structure models the fields written to a deb822 repository file. Multi-value
    fields are rendered as space-separated lists.

    Validation rules:
      - ``types``, ``uris`` and ``suites`` must be non-empty.
      - If any suite ends with ``/`` (path-style suite), ``components`` must be empty.
      - Otherwise at least one component is required.

    The rendered output is stable and always ends with a newline.
    """

    types: Sequence[str]
    uris: Sequence[str]
    suites: Sequence[str]
    components: Sequence[str]
    architectures: Sequence[str]
    enabled: bool
    signed_by: Optional[str]

    def validate(self) -> None:
        """
        Validate the spec for deb822 output.

        Raises:
            ValueError: If required fields are missing or if suites/components violate deb822 rules.
        """
        if not self.types:
            raise ValueError("'types' must not be empty.")
        if not self.uris:
            raise ValueError("'uris' must not be empty.")
        if not self.suites:
            raise ValueError("'suites' must not be empty.")

        # Per Ansible's deb822_repository docs: if suite is a path (ends with '/'),
        # components must be omitted; otherwise at least one component is required. :contentReference[oaicite:2]{index=2}
        any_path_suite = any(s.endswith("/") for s in self.suites)
        if any_path_suite and self.components:
            raise ValueError(
                "When any suite ends with '/', 'components' must be empty."
            )
        if (not any_path_suite) and (not self.components):
            raise ValueError(
                "When suite is not a path, at least one 'component' is required."
            )

    def render(self) -> str:
        """
        Render the spec as a deb822 formatted stanza.

        Returns:
            The rendered ``.sources`` content as UTF-8 text, always newline terminated.

        Raises:
            ValueError: If the spec is invalid (see :meth:`validate`).
        """
        self.validate()

        lines: List[str] = []
        lines.append(f"Types: {' '.join(self.types)}")
        lines.append(f"URIs: {' '.join(self.uris)}")
        lines.append(f"Suites: {' '.join(self.suites)}")

        if self.components:
            lines.append(f"Components: {' '.join(self.components)}")
        if self.architectures:
            lines.append(f"Architectures: {' '.join(self.architectures)}")

        # Enabled accepts yes/no (deb822); keep output stable. :contentReference[oaicite:3]{index=3}
        lines.append(f"Enabled: {'yes' if self.enabled else 'no'}")

        if self.signed_by:
            lines.append(f"Signed-By: {self.signed_by}")

        return "\n".join(lines) + "\n"


class Deb822RepoManager:
    """
    High-level helper for managing deb822 APT repositories and key material.

    Responsibilities:
      - Ensure repository signing keys using one of the supported methods:
          * ``none``: do not manage keys
          * ``download``: download a key file (optional checksum), optionally dearmor and validate it
          * ``deb``: download and install a keyring ``.deb`` package
      - Ensure/remove a deb822 ``.sources`` file with a stable rendering.
      - Optionally run ``apt-get update`` after changes.

    Error handling:
      - All unrecoverable errors are reported via the provided Ansible module's ``fail_json``.
    """

    def __init__(self, module: Any) -> None:
        """
        Create a new manager bound to an Ansible module instance.

        Args:
            module: Ansible module object providing ``run_command()``, ``fail_json()``, ``atomic_move()``
                and (optionally) ``tmpdir``.
        """
        self._m = module

    # -------------------------
    # Public orchestration API
    # -------------------------

    def ensure_key(self, *, key_cfg: Mapping[str, Any], check_mode: bool) -> KeyResult:
        """
        Ensure key material for the repository according to ``key_cfg``.

        Args:
            key_cfg: Key configuration mapping. Expected keys depend on the chosen method.
            check_mode: If True, perform a dry-run and report whether changes would occur.

        Returns:
            A :class:`KeyResult` describing what was changed and where the key material is located.

        Raises:
            The module will call ``fail_json`` if the configuration is invalid or required tooling fails.
        """
        method = (key_cfg.get("method") or "none").lower()
        if method == "none":
            return KeyResult(
                changed=False,
                key_path=None,
                deb_path=None,
                package_name=None,
                package_version=None,
            )

        if method == "download":
            return self._ensure_key_download(key_cfg=key_cfg, check_mode=check_mode)

        if method == "deb":
            return self._ensure_key_deb(key_cfg=key_cfg, check_mode=check_mode)

        self._m.fail_json(
            msg=f"Unsupported key.method={method!r}. Use one of: none, download, deb."
        )

    def ensure_repo_file(
        self,
        *,
        repo_path: str,
        spec: Deb822RepoSpec,
        mode: int,
        check_mode: bool,
    ) -> RepoResult:
        """
        Ensure the deb822 repository file exists with the desired content.

        Args:
            repo_path: Destination path of the ``.sources`` file.
            spec: Repository spec to render.
            mode: File permissions mode (octal int, e.g. ``0o644``).
            check_mode: If True, do not write, only report whether content would change.

        Returns:
            A :class:`RepoResult` including the rendered content.
        """
        rendered = spec.render()
        changed = self._ensure_file_contents(
            dest=repo_path,
            data=rendered.encode("utf-8"),
            mode=mode,
            check_mode=check_mode,
        )
        return RepoResult(changed=changed, repo_path=repo_path, rendered=rendered)

    def remove_file(self, *, path: str, check_mode: bool) -> bool:
        """
        Remove a file if it exists.

        Args:
            path: Path to remove.
            check_mode: If True, do not remove but report that a change would occur.

        Returns:
            True if the file was removed (or would be removed in check mode), otherwise False.
        """
        if not os.path.exists(path):
            return False
        if check_mode:
            return True
        try:
            os.remove(path)
            return True
        except OSError as exc:
            self._m.fail_json(msg=f"Failed to remove {path}: {exc!s}")

    def apt_update(self, *, check_mode: bool) -> Tuple[bool, str]:
        """
        Run ``apt-get update`` non-interactively.

        Args:
            check_mode: If True, do not execute and return a message indicating a dry-run.

        Returns:
            Tuple ``(changed, output)`` where ``changed`` is True when the command would run/ran.
        """
        if check_mode:
            return True, "check_mode: would run apt-get update"
        rc, out, err = self._m.run_command(
            ["apt-get", "update"],
            check_rc=False,
            environ_update={"DEBIAN_FRONTEND": "noninteractive"},
        )
        if rc != 0:
            self._m.fail_json(msg=f"apt-get update failed (rc={rc}): {err or out}")
        return True, out.strip()

    def remove_key(
        self,
        *,
        key_cfg: Mapping[str, Any],
        signed_by: Optional[str] = None,
        check_mode: bool,
    ) -> KeyResult:
        """
        Remove key material managed by this module.

        Behavior depends on ``key_cfg.method``:

        - ``download``: removes the key file at ``key_cfg.dest`` (or ``signed_by`` as fallback).
        - ``deb``: removes the keyring package if installed and optionally removes the cached ``.deb`` file.

        Args:
            key_cfg: Key configuration mapping.
            signed_by: Explicit ``Signed-By`` path used by the repo (optional).
            check_mode: If True, do not change the system but report what would be removed.

        Returns:
            A :class:`KeyResult` with ``changed=True`` if anything was removed (or would be removed).
        """
        method = (key_cfg.get("method") or "none").lower()

        if method == "none":
            return KeyResult(
                changed=False,
                key_path=None,
                deb_path=None,
                package_name=None,
                package_version=None,
            )

        if method == "download":
            dest = key_cfg.get("dest") or signed_by
            if not dest:
                self._m.fail_json(
                    msg="key.method=download requires key.dest (or signed_by to remove)"
                )

            removed = self.remove_file(path=str(dest), check_mode=check_mode)
            return KeyResult(
                changed=removed,
                key_path=str(dest),
                deb_path=None,
                package_name=None,
                package_version=None,
                messages=(
                    (f"{'would remove' if check_mode else 'removed'} key file: {dest}",)
                    if removed
                    else ("key file already absent",)
                ),
            )

        if method == "deb":
            deb_path = (
                key_cfg.get("deb_cache_path") or "/var/cache/apt/repo-keyring.deb"
            )
            explicit_pkg = key_cfg.get("package_name")
            keyring_path = key_cfg.get("deb_keyring_path") or signed_by

            pkg_name: Optional[str] = None
            pkg_ver: Optional[str] = None
            messages: List[str] = []

            if explicit_pkg:
                pkg_name = str(explicit_pkg)
                messages.append(f"using explicit package_name={pkg_name}")
            elif deb_path and os.path.exists(deb_path):
                pkg_name, pkg_ver = self._dpkg_deb_fields(deb_path)
                messages.append(f"determined package from deb: {pkg_name}")
            elif keyring_path:
                pkg_name = self._dpkg_owns_path(str(keyring_path))
                if pkg_name:
                    messages.append(
                        f"determined package from keyring owner: {pkg_name}"
                    )

            changed = False

            # Remove package if installed
            if pkg_name:
                installed_ver = self._dpkg_query_version(pkg_name)
                if installed_ver:
                    if check_mode:
                        changed = True
                        messages.append(
                            f"check_mode: would remove package {pkg_name} (installed {installed_ver})"
                        )
                    else:
                        self._apt_remove_package(pkg_name)
                        changed = True
                        messages.append(
                            f"removed package {pkg_name} (was {installed_ver})"
                        )
                else:
                    messages.append(f"package {pkg_name} not installed")
            else:
                messages.append(
                    "could not determine package name to remove (set key.package_name, or provide deb_cache_path, or signed_by/deb_keyring_path)"
                )

            # Remove cached deb file (best-effort)
            if deb_path and os.path.exists(deb_path):
                if check_mode:
                    changed = True
                    messages.append(f"check_mode: would remove cached deb: {deb_path}")
                else:
                    try:
                        os.remove(deb_path)
                        changed = True
                        messages.append(f"removed cached deb: {deb_path}")
                    except OSError as exc:
                        self._m.fail_json(
                            msg=f"Failed to remove cached deb {deb_path}: {exc!s}"
                        )

            return KeyResult(
                changed=changed,
                key_path=str(keyring_path) if keyring_path else None,
                deb_path=str(deb_path) if deb_path else None,
                package_name=pkg_name,
                package_version=pkg_ver,
                messages=tuple(messages),
            )

        self._m.fail_json(
            msg=f"Unsupported key.method={method!r}. Use one of: none, download, deb."
        )

    def _dpkg_owns_path(self, path: str) -> Optional[str]:
        """
        Determine which dpkg package owns a given file path.

        Args:
            path: Absolute file path.

        Returns:
            The owning package name (including optional architecture suffix) or None if not owned.
        """
        rc, out, _ = self._m.run_command(["dpkg-query", "-S", path], check_rc=False)
        if rc != 0:
            return None

        # Format examples:
        #   debsuryorg-archive-keyring:amd64: /usr/share/keyrings/debsuryorg-archive-keyring.gpg
        #   somepkg: /etc/apt/keyrings/some.gpg
        for line in (ln.strip() for ln in out.splitlines() if ln.strip()):
            pkg_part = line.split(": ", 1)[0].strip()  # keeps optional ":amd64"
            if pkg_part:
                return pkg_part
        return None

    def _apt_remove_package(self, pkg_name: str) -> None:
        """
        Remove a package using ``apt-get`` in non-interactive mode.

        Args:
            pkg_name: Package name to remove.

        Raises:
            The module will call ``fail_json`` if removal fails.
        """
        rc, out, err = self._m.run_command(
            ["apt-get", "-y", "remove", pkg_name],
            check_rc=False,
            environ_update={"DEBIAN_FRONTEND": "noninteractive"},
        )
        if rc != 0:
            self._m.fail_json(
                msg=f"Failed to remove package {pkg_name} (rc={rc}): {err or out}"
            )

    # -------------------------
    # Key: download method
    # -------------------------

    def _ensure_key_download(
        self, *, key_cfg: Mapping[str, Any], check_mode: bool
    ) -> KeyResult:
        """
        Ensure a repo-specific keyring file by downloading it.

        This method:
          1) downloads a key file to a temporary location (optional checksum verification)
          2) optionally dearmors ASCII keys into a binary keyring via ``gpg --dearmor``
          3) optionally validates the key via ``gpg --show-keys``
          4) atomically installs/updates the destination file and enforces file permissions

        Args:
            key_cfg: Key configuration (expects ``url`` and ``dest``).
            check_mode: If True, do not write any files.

        Returns:
            A :class:`KeyResult`.
        """
        url = key_cfg.get("url")
        if not url:
            self._m.fail_json(msg="key.method=download requires key.url")

        dest = key_cfg.get("dest")
        if not dest:
            self._m.fail_json(msg="key.method=download requires key.dest")

        file_mode = self._parse_mode(key_cfg.get("mode", "0644"))
        dearmor = bool(key_cfg.get("dearmor", True))
        validate = bool(key_cfg.get("validate", True))
        checksum = key_cfg.get("checksum")

        # Download to temp, compute sha256, optional verify checksum
        tmp_raw, raw_sha = self._download_to_temp(url=url, checksum=checksum)

        # Decide ASCII armored or binary
        is_ascii = self._looks_like_ascii_armored(tmp_raw)

        # Optionally dearmor
        tmp_final = tmp_raw
        messages: List[str] = []
        if is_ascii and dearmor:
            tmp_final = self._temp_path(suffix=".gpg")
            self._run_gpg_dearmor(src=tmp_raw, dst=tmp_final)
            messages.append("dearmored ASCII key to binary keyring")

        # Optional validation (requires gpg)
        if validate:
            self._run_gpg_show_keys(path=tmp_final)
            messages.append("validated key via gpg --show-keys")

        # If destination exists and content is identical, keep unchanged
        final_sha = self._sha256_file(tmp_final)
        if os.path.exists(dest) and self._sha256_file(dest) == final_sha:
            self._safe_unlink(tmp_raw)
            if tmp_final != tmp_raw:
                self._safe_unlink(tmp_final)
            self._ensure_mode(dest, file_mode, check_mode=check_mode)
            return KeyResult(
                changed=False,
                key_path=dest,
                deb_path=None,
                package_name=None,
                package_version=None,
                messages=tuple(messages + ["key unchanged"]),
            )

        if check_mode:
            self._safe_unlink(tmp_raw)
            if tmp_final != tmp_raw:
                self._safe_unlink(tmp_final)
            return KeyResult(
                changed=True,
                key_path=dest,
                deb_path=None,
                package_name=None,
                package_version=None,
                messages=tuple(messages + ["check_mode: would write key"]),
            )

        # Write/update dest atomically
        self._atomic_move(tmp_final, dest, mode=file_mode)

        # Cleanup raw temp if different
        if tmp_final != tmp_raw:
            self._safe_unlink(tmp_raw)

        return KeyResult(
            changed=True,
            key_path=dest,
            deb_path=None,
            package_name=None,
            package_version=None,
            messages=tuple(messages + ["key updated"]),
        )

    # -------------------------
    # Key: deb method
    # -------------------------

    def _ensure_key_deb(
        self, *, key_cfg: Mapping[str, Any], check_mode: bool
    ) -> KeyResult:
        """
        Ensure repo key material by installing a keyring ``.deb`` package.

        This method ensures the keyring ``.deb`` is downloaded to ``deb_cache_path`` (idempotent by
        content hash), extracts its package name/version, and installs it if required.

        Args:
            key_cfg: Key configuration (expects ``url``; optionally ``deb_cache_path`` and ``deb_keyring_path``).
            check_mode: If True, do not install packages or write files.

        Returns:
            A :class:`KeyResult` describing downloads/installs and detected keyring path.
        """
        url = key_cfg.get("url")
        if not url:
            self._m.fail_json(msg="key.method=deb requires key.url")

        deb_path = key_cfg.get("deb_cache_path") or "/var/cache/apt/repo-keyring.deb"
        file_mode = self._parse_mode(key_cfg.get("mode", "0644"))
        checksum = key_cfg.get("checksum")

        # Ensure deb file on disk (idempotent by hash compare)
        deb_changed = self._ensure_downloaded_file(
            url=url,
            dest=deb_path,
            mode=file_mode,
            checksum=checksum,
            check_mode=check_mode,
        )

        # Extract package metadata from deb
        pkg_name, pkg_ver = self._dpkg_deb_fields(deb_path)

        installed_ver = self._dpkg_query_version(pkg_name)
        needs_install = (installed_ver is None) or (installed_ver != pkg_ver)

        keyring_path = key_cfg.get("deb_keyring_path")
        if not keyring_path:
            keyring_path = self._find_keyring_path_in_deb(deb_path)

        msgs: List[str] = []
        if deb_changed:
            msgs.append("downloaded/updated keyring .deb")
        if installed_ver is None:
            msgs.append("keyring package not installed")
        else:
            msgs.append(f"installed version: {installed_ver}")

        if needs_install:
            if check_mode:
                return KeyResult(
                    changed=True,
                    key_path=keyring_path,
                    deb_path=deb_path,
                    package_name=pkg_name,
                    package_version=pkg_ver,
                    messages=tuple(
                        msgs + [f"check_mode: would install {pkg_name}={pkg_ver}"]
                    ),
                )

            rc, out, err = self._m.run_command(
                ["apt-get", "-y", "install", deb_path],
                check_rc=False,
                environ_update={"DEBIAN_FRONTEND": "noninteractive"},
            )
            if rc != 0:
                self._m.fail_json(
                    msg=f"Failed to install keyring deb (rc={rc}): {err or out}"
                )
            msgs.append(f"installed {pkg_name}={pkg_ver}")

            return KeyResult(
                changed=True,
                key_path=keyring_path,
                deb_path=deb_path,
                package_name=pkg_name,
                package_version=pkg_ver,
                messages=tuple(msgs),
            )

        # No install needed (same version)
        return KeyResult(
            changed=bool(deb_changed),
            key_path=keyring_path,
            deb_path=deb_path,
            package_name=pkg_name,
            package_version=pkg_ver,
            messages=tuple(msgs + ["install not required"]),
        )

    # -------------------------
    # Helpers: download / files
    # -------------------------

    def validate_filename(self, filename: str) -> None:
        # deb822 repo files must end with .sources, name restrictions are conventional;
        # keep it strict to avoid weird paths. :contentReference[oaicite:4]{index=4}
        """
        Validate a repository filename for use under ``sources.list.d``.

        Args:
            filename: Filename to validate.

        Raises:
            ValueError: If the filename contains invalid characters or does not end with ``.sources``.
        """
        if not _FILENAME_RE.match(filename):
            raise ValueError(
                "filename may only contain letters, digits, underscore, hyphen, and period"
            )
        if not filename.endswith(".sources"):
            raise ValueError("filename must end with .sources")

    def _ensure_downloaded_file(
        self,
        *,
        url: str,
        dest: str,
        mode: int,
        checksum: Optional[str],
        check_mode: bool,
    ) -> bool:
        """
        Download a URL to ``dest`` if content differs.

        The destination file is updated only when the downloaded content hash differs from the
        existing file, providing stable idempotency.

        Args:
            url: Source URL.
            dest: Destination file path.
            mode: File permissions mode (octal int).
            checksum: Optional expected SHA256 checksum for integrity.
            check_mode: If True, do not write any files.

        Returns:
            True if the destination would change/changed, otherwise False.
        """
        tmp, _ = self._download_to_temp(url=url, checksum=checksum)
        # Compare hash to dest
        tmp_sha = self._sha256_file(tmp)
        if os.path.exists(dest) and self._sha256_file(dest) == tmp_sha:
            self._safe_unlink(tmp)
            self._ensure_mode(dest, mode, check_mode=check_mode)
            return False

        if check_mode:
            self._safe_unlink(tmp)
            return True

        self._atomic_move(tmp, dest, mode=mode)
        return True

    def _download_to_temp(
        self, *, url: str, checksum: Optional[str]
    ) -> Tuple[str, str]:
        """
        Download a URL to a temporary file and compute its SHA256.

        Args:
            url: Source URL.
            checksum: Optional expected SHA256 checksum; mismatches cause ``fail_json``.

        Returns:
            Tuple ``(tmp_path, sha256_hex)``.
        """
        tmp = self._temp_path()
        resp, info = fetch_url(self._m, url, method="GET")
        status = int(info.get("status", 0))
        if status < 200 or status >= 300:
            self._safe_unlink(tmp)
            self._m.fail_json(
                msg=f"Failed to download {url} (HTTP {status}): {info.get('msg')}"
            )

        h = sha256()
        try:
            with open(tmp, "wb") as f:
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    f.write(chunk)
                    h.update(chunk)
        finally:
            try:
                resp.close()
            except Exception:
                pass

        digest = h.hexdigest()
        if checksum and checksum.lower() != digest.lower():
            self._safe_unlink(tmp)
            self._m.fail_json(
                msg=f"Checksum mismatch for {url}: expected {checksum}, got {digest}"
            )

        return tmp, digest

    def _ensure_file_contents(
        self, *, dest: str, data: bytes, mode: int, check_mode: bool
    ) -> bool:
        """
        Ensure that ``dest`` contains exactly ``data``.

        Args:
            dest: Destination file path.
            data: Desired file content.
            mode: File permissions mode (octal int).
            check_mode: If True, do not write any files.

        Returns:
            True if the file would change/changed, otherwise False.
        """
        current = None
        if os.path.exists(dest):
            try:
                with open(dest, "rb") as f:
                    current = f.read()
            except OSError as exc:
                self._m.fail_json(msg=f"Failed to read {dest}: {exc!s}")

        if current == data:
            self._ensure_mode(dest, mode, check_mode=check_mode)
            return False

        if check_mode:
            return True

        tmp = self._temp_path()
        try:
            with open(tmp, "wb") as f:
                f.write(data)
        except OSError as exc:
            self._safe_unlink(tmp)
            self._m.fail_json(msg=f"Failed to write temp file for {dest}: {exc!s}")

        self._atomic_move(tmp, dest, mode=mode)
        return True

    def _atomic_move(self, src: str, dest: str, *, mode: int) -> None:
        """
        Atomically move ``src`` to ``dest`` and apply file permissions.

        Args:
            src: Temporary source file path.
            dest: Destination file path.
            mode: File permissions mode (octal int).

        Raises:
            The module will call ``fail_json`` on failure.
        """
        dest_dir = os.path.dirname(dest)
        if dest_dir and not os.path.isdir(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)

        # Use Ansible's atomic_move for correctness across FS boundaries when possible
        try:
            self._m.atomic_move(src, dest)
        except Exception as exc:
            self._safe_unlink(src)
            self._m.fail_json(msg=f"atomic_move failed for {dest}: {exc!s}")

        self._ensure_mode(dest, mode, check_mode=False)

    def _ensure_mode(self, path: str, mode: int, *, check_mode: bool) -> None:
        """
        Ensure a file has the desired permission bits.

        Args:
            path: File path.
            mode: File permissions mode (octal int).
            check_mode: If True, do not chmod, only evaluate.
        """
        if not os.path.exists(path):
            return
        try:
            st = os.stat(path)
        except OSError:
            return
        if (st.st_mode & 0o777) == mode:
            return
        if check_mode:
            return
        try:
            os.chmod(path, mode)
        except OSError as exc:
            self._m.fail_json(msg=f"Failed to chmod {path} to {oct(mode)}: {exc!s}")

    def _sha256_file(self, path: str) -> str:
        """
        Compute the SHA256 hash of a file.

        Args:
            path: File path.

        Returns:
            SHA256 digest as a lowercase hex string.
        """
        h = sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024 * 256)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    def _temp_path(self, *, suffix: str = "") -> str:
        """
        Create a temporary file path for intermediate downloads/writes.

        Args:
            suffix: Optional file suffix.

        Returns:
            Path to a newly created temporary file (empty file is created).
        """
        tmpdir = getattr(self._m, "tmpdir", None) or None
        fd, p = tempfile.mkstemp(prefix="ansible-deb822-", suffix=suffix, dir=tmpdir)
        os.close(fd)
        return p

    def _safe_unlink(self, path: str) -> None:
        """
        Best-effort removal of a file path.

        Errors are ignored to simplify cleanup paths.
        """
        try:
            os.remove(path)
        except OSError:
            pass

    # -------------------------
    # Helpers: gpg
    # -------------------------

    def _looks_like_ascii_armored(self, path: str) -> bool:
        """
        Heuristically detect whether a file is an ASCII-armored PGP key.

        Args:
            path: File path.

        Returns:
            True if the file begins with a typical ASCII armored PGP public key header.
        """
        try:
            with open(path, "rb") as f:
                head = f.read(128)
        except OSError:
            return False
        return b"-----BEGIN PGP PUBLIC KEY BLOCK-----" in head

    def _run_gpg_dearmor(self, *, src: str, dst: str) -> None:
        """
        Convert an ASCII-armored key to a binary keyring using GnuPG.

        Args:
            src: Source key file path.
            dst: Destination keyring file path.

        Raises:
            The module will call ``fail_json`` if gpg fails.
        """
        rc, out, err = self._m.run_command(
            ["gpg", "--dearmor", "--yes", "--output", dst, src],
            check_rc=False,
        )
        if rc != 0:
            self._safe_unlink(dst)
            self._m.fail_json(msg=f"gpg --dearmor failed (rc={rc}): {err or out}")

    def _run_gpg_show_keys(self, *, path: str) -> None:
        """
        Validate that a key file contains at least one public key.

        Args:
            path: Key file path.

        Raises:
            The module will call ``fail_json`` if gpg fails or the output does not contain a public key.
        """
        rc, out, err = self._m.run_command(
            ["gpg", "--show-keys", "--with-colons", path],
            check_rc=False,
        )
        if rc != 0:
            self._m.fail_json(msg=f"gpg --show-keys failed (rc={rc}): {err or out}")
        if "pub" not in out:
            self._m.fail_json(
                msg="Downloaded key does not look like a public key (no 'pub' record in gpg output)."
            )

    # -------------------------
    # Helpers: dpkg
    # -------------------------

    def _dpkg_deb_fields(self, deb_path: str) -> Tuple[str, str]:
        """
        Read package metadata (Package and Version) from a ``.deb`` file.

        Args:
            deb_path: Path to the ``.deb`` file.

        Returns:
            Tuple ``(package_name, package_version)``.

        Raises:
            The module will call ``fail_json`` on unexpected output.
        """
        rc, out, err = self._m.run_command(
            ["dpkg-deb", "--field", deb_path, "Package", "Version"],
            check_rc=False,
        )
        if rc != 0:
            self._m.fail_json(
                msg=f"dpkg-deb --field failed for {deb_path}: {err or out}"
            )
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        if len(lines) < 2:
            self._m.fail_json(msg=f"Unexpected dpkg-deb output for {deb_path}: {out!r}")
        return lines[0], lines[1]

    def _dpkg_query_version(self, pkg_name: str) -> Optional[str]:
        """
        Query the installed version of a dpkg package.

        Args:
            pkg_name: Package name.

        Returns:
            The installed version string, or None if the package is not installed.
        """
        rc, out, _ = self._m.run_command(
            ["dpkg-query", "-W", "-f=${Version}", pkg_name],
            check_rc=False,
        )
        if rc != 0:
            return None
        ver = out.strip()
        return ver or None

    def _find_keyring_path_in_deb(self, deb_path: str) -> str:
        # Find typical keyring locations inside the deb
        """
        Determine a likely keyring file path contained in a ``.deb`` package.

        The method scans the package file list for ``.gpg`` files under typical keyring directories
        and chooses a stable, preferred candidate.

        Args:
            deb_path: Path to the downloaded ``.deb`` file.

        Returns:
            The selected keyring path inside the filesystem (leading ``/``).

        Raises:
            The module will call ``fail_json`` if no suitable keyring path can be determined.
        """
        rc, out, err = self._m.run_command(["dpkg-deb", "-c", deb_path], check_rc=False)
        if rc != 0:
            self._m.fail_json(msg=f"dpkg-deb -c failed for {deb_path}: {err or out}")

        candidates: List[str] = []
        for line in out.splitlines():
            parts = line.split()
            if not parts:
                continue
            p = parts[-1]
            if p.endswith(".gpg") and (
                p.startswith("./usr/share/keyrings/")
                or p.startswith("./etc/apt/keyrings/")
            ):
                candidates.append(p.lstrip("."))
        if not candidates:
            self._m.fail_json(
                msg=(
                    "Could not determine keyring path from deb contents. "
                    "Set key.deb_keyring_path explicitly."
                )
            )
        # Prefer /usr/share/keyrings
        candidates.sort(
            key=lambda x: (0 if x.startswith("/usr/share/keyrings/") else 1, x)
        )
        return candidates[0]

    # -------------------------
    # Helpers: misc
    # -------------------------

    def _parse_mode(self, mode_str: Any) -> int:
        """
        Parse a file mode from an int or an octal string.

        Args:
            mode_str: Mode value, e.g. ``"0644"`` or ``0o644``.

        Returns:
            Mode as an integer suitable for ``os.chmod``.

        Raises:
            The module will call ``fail_json`` for invalid values.
        """
        if isinstance(mode_str, int):
            return mode_str
        s = str(mode_str).strip()
        if not s:
            return 0o644
        try:
            return int(s, 8)
        except ValueError:
            self._m.fail_json(msg=f"Invalid file mode: {mode_str!r}")

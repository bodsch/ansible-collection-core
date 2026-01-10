from __future__ import annotations

"""
Compatibility helpers for using passlib 1.7.4 with bcrypt 5.x.

Background
----------
passlib 1.7.4 performs a bcrypt backend self-test during import that uses a test
secret longer than 72 bytes. bcrypt 5.x raises a ValueError for inputs longer
than 72 bytes instead of silently truncating. This can abort imports of
passlib.apache (and other passlib components) even before user code runs.

This module applies a targeted runtime patch:
- Patch bcrypt.hashpw/checkpw to truncate inputs to 72 bytes (bcrypt's effective
  input limit) so that passlib's self-tests do not crash.
- Patch passlib.handlers.bcrypt.detect_wrap_bug() to handle the ValueError and
  proceed with the wraparound test.

The patch restores passlib importability on systems that ship passlib 1.7.4
together with bcrypt 5.x.
"""

import importlib.metadata
from importlib.metadata import PackageNotFoundError


def _major_version(dist_name: str) -> int | None:
    """
    Return the major version number of an installed distribution.

    The value is derived from ``importlib.metadata.version(dist_name)`` and then
    parsed as the leading numeric component.

    Args:
        dist_name: The distribution name as used by importlib metadata
            (e.g. "passlib", "bcrypt").

    Returns:
        The major version as an integer, or ``None`` if the distribution is not
        installed or the version string cannot be interpreted.
    """
    try:
        v = importlib.metadata.version(dist_name)
    except PackageNotFoundError:
        return None

    # Extract the first dot-separated segment and keep digits only
    # (works for typical versions like "5.0.1", "5rc1", "5.post1", etc.).
    head = v.split(".", 1)[0]
    try:
        return int("".join(ch for ch in head if ch.isdigit()) or head)
    except ValueError:
        return None


def apply_passlib_bcrypt5_compat(module) -> None:
    """
    Apply runtime patches to make passlib 1.7.4 work with bcrypt 5.x.

    What this does
    -------------
    1) Patches ``bcrypt.hashpw`` and ``bcrypt.checkpw`` to truncate any password
       input longer than 72 bytes to 72 bytes. This prevents bcrypt 5.x from
       raising ``ValueError`` when passlib runs its internal self-tests during
       import. The patch is applied only once per Python process.

    2) Patches ``passlib.handlers.bcrypt.detect_wrap_bug`` to tolerate the
       bcrypt 5.x ``ValueError`` during the wraparound self-test and continue
       the test using a 72-byte truncated secret.

    Preconditions
    -------------
    This function is a no-op unless:
    - passlib is installed and its major version is 1, and
    - bcrypt is installed and its major version is >= 5.

    Logging
    -------
    The function uses ``module.log(...)`` for diagnostic messages. The passed
    ``module`` is expected to be an AnsibleModule (or a compatible object).

    Important
    ---------
    This patch does not remove bcrypt's effective 72-byte input limit. bcrypt
    inherently only considers the first 72 bytes of a password. The patch
    merely restores the historical "truncate silently" behavior in bcrypt 5.x
    so that older passlib versions keep working.

    Args:
        module: An object providing ``log(str)``. Typically an instance of
            ``ansible.module_utils.basic.AnsibleModule``.

    Returns:
        None. The patch is applied in-place to the imported modules.
    """
    module.log("apply_passlib_bcrypt5_compat()")

    passlib_major = _major_version("passlib")
    bcrypt_major = _major_version("bcrypt")

    module.log(f"  - passlib_major {passlib_major}")
    module.log(f"  - bcrypt_major  {bcrypt_major}")

    if passlib_major is None or bcrypt_major is None:
        return
    if bcrypt_major < 5:
        return

    # --- Patch 1: bcrypt itself (so passlib self-tests don't crash) ---
    import bcrypt as _bcrypt  # bcrypt package

    if not getattr(_bcrypt, "_passlib_compat_applied", False):
        _orig_hashpw = _bcrypt.hashpw
        _orig_checkpw = _bcrypt.checkpw

        def hashpw(secret: bytes, salt: bytes) -> bytes:
            """
            Wrapper around bcrypt.hashpw that truncates secrets to 72 bytes.

            Args:
                secret: Password bytes to hash.
                salt: bcrypt salt/config blob.

            Returns:
                The bcrypt hash as bytes.
            """
            if isinstance(secret, bytearray):
                secret = bytes(secret)
            if len(secret) > 72:
                secret = secret[:72]
            return _orig_hashpw(secret, salt)

        def checkpw(secret: bytes, hashed: bytes) -> bool:
            """
            Wrapper around bcrypt.checkpw that truncates secrets to 72 bytes.

            Args:
                secret: Password bytes to verify.
                hashed: Existing bcrypt hash.

            Returns:
                True if the password matches, otherwise False.
            """
            if isinstance(secret, bytearray):
                secret = bytes(secret)
            if len(secret) > 72:
                secret = secret[:72]
            return _orig_checkpw(secret, hashed)

        _bcrypt.hashpw = hashpw  # type: ignore[assignment]
        _bcrypt.checkpw = checkpw  # type: ignore[assignment]
        _bcrypt._passlib_compat_applied = True

        module.log("  - patched bcrypt.hashpw/checkpw for >72 truncation")

    # --- Patch 2: passlib detect_wrap_bug() (handle bcrypt>=5 behavior) ---
    import passlib.handlers.bcrypt as pl_bcrypt  # noqa: WPS433 (runtime patch)

    if getattr(pl_bcrypt, "_bcrypt5_compat_applied", False):
        return

    def detect_wrap_bug_patched(ident: str) -> bool:
        """
        Replacement for passlib.handlers.bcrypt.detect_wrap_bug().

        passlib's original implementation performs a detection routine to test
        for a historical bcrypt "wraparound" bug. The routine uses a test secret
        longer than 72 bytes. With bcrypt 5.x, this can raise ``ValueError``.
        This patched version catches that error, truncates the secret to 72
        bytes, and completes the verification checks.

        Args:
            ident: The bcrypt identifier prefix (e.g. "$2a$", "$2b$", etc.)
                as provided by passlib.

        Returns:
            True if the backend appears to exhibit the wraparound bug,
            otherwise False.

        Raises:
            RuntimeError: If the backend fails the expected self-test checks.
        """
        secret = (b"0123456789" * 26)[:255]

        bug_hash = (
            ident.encode("ascii")
            + b"04$R1lJ2gkNaoPGdafE.H.16.nVyh2niHsGJhayOHLMiXlI45o8/DU.6"
        )
        try:
            if pl_bcrypt.bcrypt.verify(secret, bug_hash):
                return True
        except ValueError:
            # bcrypt>=5 kann bei >72 Bytes explizit ValueError werfen
            secret = secret[:72]

        correct_hash = (
            ident.encode("ascii")
            + b"04$R1lJ2gkNaoPGdafE.H.16.1MKHPvmKwryeulRe225LKProWYwt9Oi"
        )
        if not pl_bcrypt.bcrypt.verify(secret, correct_hash):
            raise RuntimeError(
                f"bcrypt backend failed wraparound self-test for ident={ident!r}"
            )

        return False

    pl_bcrypt.detect_wrap_bug = detect_wrap_bug_patched  # type: ignore[assignment]
    pl_bcrypt._bcrypt5_compat_applied = True

    module.log("  - patched passlib.handlers.bcrypt.detect_wrap_bug")

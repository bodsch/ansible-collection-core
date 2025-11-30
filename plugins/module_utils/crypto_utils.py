""" """

# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

try:
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.x509.oid import ExtensionOID
except ImportError as exc:  # pragma: no cover
    # Du kannst das in deinem Modul ggf. in eine "fail_json" Fehlermeldung drehen
    raise RuntimeError(
        "The 'cryptography' Python library is required to use crypto_utils.get_crl_info()"
    ) from exc


class OpenSSLObjectError(Exception):
    """
    Einfacher Fehler-Typ, um Parsing-/Krypto-Probleme konsistent zu signalisieren.
    """

    pass


# ======================================================================
# Hilfsfunktionen für Zeitverarbeitung
# ======================================================================

_ASN1_TIME_FORMAT = "%Y%m%d%H%M%SZ"


def _to_utc_naive(dt: datetime) -> datetime:
    """
    Konvertiert ein datetime-Objekt nach UTC und entfernt tzinfo,
    so dass ein naives datetime zurückgegeben wird.

    Das ist wichtig, weil dein Modul mit datetime.now() (naiv) rechnet.
    """
    if dt.tzinfo is None:
        # wir interpretieren naive Zeiten als UTC
        return dt.replace(tzinfo=None)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _format_asn1_time(dt: Optional[datetime]) -> Optional[str]:
    """
    datetime -> ASN.1 TIME (YYYYMMDDHHMMSSZ) oder None.
    """
    if dt is None:
        return None
    dt_utc_naive = _to_utc_naive(dt)
    return dt_utc_naive.strftime(_ASN1_TIME_FORMAT)


def _parse_asn1_time(value: str, input_name: str) -> datetime:
    """
    ASN.1 TIME (YYYYMMDDHHMMSSZ) -> datetime (naiv, UTC).
    """
    try:
        dt = datetime.strptime(value, _ASN1_TIME_FORMAT)
    except ValueError as exc:
        raise OpenSSLObjectError(
            f"{input_name!r} is not a valid ASN.1 TIME value: {value!r}"
        ) from exc
    # strptime gibt ein naives datetime zurück, wir interpretieren es als UTC
    return dt


def _parse_relative_spec(spec: str, input_name: str) -> timedelta:
    """
    Parsen des relativen Formats (z.B. +32w1d2h3m4s) in ein timedelta.

    Unterstützte Einheiten:
    - w: Wochen
    - d: Tage
    - h: Stunden
    - m: Minuten
    - s: Sekunden
    """
    weeks = days = hours = minutes = seconds = 0
    pos = 0
    length = len(spec)

    while pos < length:
        start = pos
        while pos < length and spec[pos].isdigit():
            pos += 1
        if start == pos:
            raise OpenSSLObjectError(
                f"Invalid relative time spec in {input_name!r}: {spec!r}"
            )
        number = int(spec[start:pos])

        if pos >= length:
            raise OpenSSLObjectError(
                f"Missing time unit in relative time spec for {input_name!r}: {spec!r}"
            )

        unit = spec[pos]
        pos += 1

        if unit == "w":
            weeks += number
        elif unit == "d":
            days += number
        elif unit == "h":
            hours += number
        elif unit == "m":
            minutes += number
        elif unit == "s":
            seconds += number
        else:
            raise OpenSSLObjectError(
                f"Unknown time unit {unit!r} in relative time spec for {input_name!r}: {spec!r}"
            )

    return timedelta(
        weeks=weeks,
        days=days,
        hours=hours,
        minutes=minutes,
        seconds=seconds,
    )


def get_relative_time_option(
    value: Optional[str],
    input_name: str,
    with_timezone: bool = False,
    now: Optional[datetime] = None,
) -> Optional[datetime]:
    """
    Grob kompatible Variante zu community.crypto._time.get_relative_time_option.

    Unterstützte Werte:
    - None / "" / "none" => None
    - ASN.1 TIME: "YYYYMMDDHHMMSSZ"
    - relative Zeiten: "[+-]timespec" mit w/d/h/m/s (z.B. "+32w1d2h")
    - Sonderwerte: "always" / "forever"

    Rückgabe:
    - datetime (naiv, in UTC gedacht) oder None

    Hinweis:
    - with_timezone=True gibt tz-aware UTC-datetime zurück.
    - with_timezone=False (Default) gibt naives datetime zurück (wie dein Modul es erwartet).
    """
    if value is None:
        return None

    value = str(value).strip()
    if not value or value.lower() == "none":
        return None

    # Sonderfälle: always / forever
    if value.lower() == "always":
        dt = datetime(1970, 1, 1, 0, 0, 1, tzinfo=timezone.utc)
        return dt if with_timezone else dt.replace(tzinfo=None)

    if value.lower() == "forever":
        dt = datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        return dt if with_timezone else dt.replace(tzinfo=None)

    # Relative Zeitangaben
    if value[0] in "+-":
        sign = 1 if value[0] == "+" else -1
        spec = value[1:]
        delta = _parse_relative_spec(spec, input_name)
        if now is None:
            # wir rechnen intern in UTC
            now = datetime.utcnow().replace(tzinfo=timezone.utc)
        dt = now + sign * delta
        return dt if with_timezone else dt.replace(tzinfo=None)

    # Absolute Zeit – zuerst ASN.1 TIME probieren
    try:
        dt = _parse_asn1_time(value, input_name)
        # _parse_asn1_time gibt naiv (UTC) zurück
        if with_timezone:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except OpenSSLObjectError:
        # als Fallback ein paar ISO-Formate unterstützen
        pass

    # ISO-Formate: YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, YYYY-MM-DD HH:MM:SS
    iso_formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in iso_formats:
        try:
            dt = datetime.strptime(value, fmt)
            # interpretieren als UTC
            dt = dt.replace(tzinfo=timezone.utc)
            return dt if with_timezone else dt.replace(tzinfo=None)
        except ValueError:
            continue

    # Wenn alles scheitert, Fehler werfen
    raise OpenSSLObjectError(f"Invalid time format for {input_name!r}: {value!r}")


# ======================================================================
# CRL-Parsing (Ersatz für community.crypto.module_backends.crl_info.get_crl_info)
# ======================================================================


@dataclass
class RevokedCertificateInfo:
    serial_number: int
    revocation_date: Optional[str]
    reason: Optional[str] = None
    reason_critical: Optional[bool] = None
    invalidity_date: Optional[str] = None
    invalidity_date_critical: Optional[bool] = None
    issuer: Optional[List[str]] = None
    issuer_critical: Optional[bool] = None


def _load_crl_from_bytes(data: bytes) -> (x509.CertificateRevocationList, str):
    """
    Lädt eine CRL aus PEM- oder DER-Daten und gibt (crl_obj, format) zurück.

    format: "pem" oder "der"
    """
    if not isinstance(data, (bytes, bytearray)):
        raise OpenSSLObjectError("CRL data must be bytes")

    # Einfacher Heuristik: BEGIN-Header => PEM
    try:
        if b"-----BEGIN" in data:
            crl = x509.load_pem_x509_crl(data, default_backend())
            return crl, "pem"
        else:
            crl = x509.load_der_x509_crl(data, default_backend())
            return crl, "der"
    except Exception as exc:
        raise OpenSSLObjectError(f"Failed to parse CRL data: {exc}") from exc


def get_crl_info(
    module,
    data: bytes,
    list_revoked_certificates: bool = True,
) -> Dict[str, Any]:
    """
    Ähnlicher Funktionsumfang wie community.crypto.module_backends.crl_info.get_crl_info.

    Gibt ein Dict zurück mit u.a.:
      - format: "pem" | "der"
      - digest: Signaturalgorithmus (z.B. "sha256")
      - last_update: ASN.1 TIME (UTC)
      - next_update: ASN.1 TIME (UTC) oder None
      - revoked_certificates: Liste von Dicts (wenn list_revoked_certificates=True)
    """
    crl, crl_format = _load_crl_from_bytes(data)

    # Signaturalgorithmus
    try:
        digest = crl.signature_hash_algorithm.name
    except Exception:
        digest = None

    # Zeitstempel
    # cryptography hat je nach Version last_update(_utc)/next_update(_utc)
    last_update_raw = getattr(
        crl,
        "last_update",
        getattr(crl, "last_update_utc", None),
    )
    next_update_raw = getattr(
        crl,
        "next_update",
        getattr(crl, "next_update_utc", None),
    )

    last_update_asn1 = _format_asn1_time(last_update_raw) if last_update_raw else None
    next_update_asn1 = _format_asn1_time(next_update_raw) if next_update_raw else None

    # Issuer als einfaches Dict (nicht 1:1 wie community.crypto, aber nützlich)
    issuer = {}
    try:
        for attr in crl.issuer:
            # attr.oid._name ist intern, aber meist "commonName", "organizationName", ...
            key = getattr(attr.oid, "_name", attr.oid.dotted_string)
            issuer[key] = attr.value
    except Exception:
        issuer = {}

    result: Dict[str, Any] = {
        "format": crl_format,
        "digest": digest,
        "issuer": issuer,
        "last_update": last_update_asn1,
        "next_update": next_update_asn1,
    }

    # Liste der widerrufenen Zertifikate
    if list_revoked_certificates:
        revoked_list: List[Dict[str, Any]] = []
        for r in crl:
            info = RevokedCertificateInfo(
                serial_number=r.serial_number,
                revocation_date=_format_asn1_time(r.revocation_date),
            )

            # Extensions auswerten (Reason, InvalidityDate, CertificateIssuer)
            for ext in r.extensions:
                try:
                    if ext.oid == ExtensionOID.CRL_REASON:
                        # ext.value.reason.name ist Enum-Name (z.B. "KEY_COMPROMISE")
                        info.reason = ext.value.reason.name.lower()
                        info.reason_critical = ext.critical
                    elif ext.oid == ExtensionOID.INVALIDITY_DATE:
                        info.invalidity_date = _format_asn1_time(ext.value)
                        info.invalidity_date_critical = ext.critical
                    elif ext.oid == ExtensionOID.CERTIFICATE_ISSUER:
                        # Liste von GeneralNames in Strings umwandeln
                        info.issuer = [str(g) for g in ext.value]
                        info.issuer_critical = ext.critical
                except Exception:
                    # Fehler in einzelnen Extensions ignorieren, CRL trotzdem weiter auswerten
                    continue

            revoked_list.append(info.__dict__)

        result["revoked_certificates"] = revoked_list

    return result

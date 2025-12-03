# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

try:
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes
    from cryptography.x509.oid import ExtensionOID
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "The 'cryptography' Python library is required to use crypto_utils"
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
    Konvertiert ein datetime-Objekt nach UTC und entfernt tzinfo.
    Naive Datumswerte werden als UTC interpretiert.
    """
    if dt.tzinfo is None:
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
    Grob kompatibel zu community.crypto._time.get_relative_time_option.

    Unterstützte Werte:
      - None / "" / "none" => None
      - ASN.1 TIME: "YYYYMMDDHHMMSSZ"
      - relative Zeiten: "[+-]timespec" mit w/d/h/m/s (z.B. "+32w1d2h")
      - "always" / "forever"

    Hinweis:
    - with_timezone=True gibt tz-aware UTC-datetime zurück.
    - with_timezone=False (Default) gibt naives datetime zurück.

    Rückgabe:
      - datetime (UTC, tz-aware oder naiv) oder None.
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

    # einfache ISO-Formate
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

    # Einfache Heuristik: BEGIN-Header => PEM
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
    CRL-Informationen ähnlich zu community.crypto.module_backends.crl_info.get_crl_info.

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


# ======================================================================
# Zertifikats-Parsing (Ersatz für CertificateInfoRetrieval)
# ======================================================================


def _split_pem_certificates(data: bytes) -> List[bytes]:
    """
    Splittet ein PEM-Blob mit mehreren CERTIFICATE-Objekten in einzelne PEM-Blöcke.
    """
    begin = b"-----BEGIN CERTIFICATE-----"
    end = b"-----END CERTIFICATE-----"

    parts: List[bytes] = []
    while True:
        start = data.find(begin)
        if start == -1:
            break
        stop = data.find(end, start)
        if stop == -1:
            break
        stop = stop + len(end)
        block = data[start:stop]
        parts.append(block)
        data = data[stop:]
    return parts


def _load_certificates(content: Union[bytes, bytearray, str]) -> List[x509.Certificate]:
    """
    Lädt ein oder mehrere X.509-Zertifikate aus PEM oder DER.
    """
    if isinstance(content, str):
        content_bytes = content.encode("utf-8")
    elif isinstance(content, (bytes, bytearray)):
        content_bytes = bytes(content)
    else:
        raise OpenSSLObjectError("Certificate content must be bytes or str")

    certs: List[x509.Certificate] = []

    try:
        if b"-----BEGIN CERTIFICATE-----" in content_bytes:
            for block in _split_pem_certificates(content_bytes):
                certs.append(x509.load_pem_x509_certificate(block, default_backend()))
        else:
            certs.append(
                x509.load_der_x509_certificate(content_bytes, default_backend())
            )
    except Exception as exc:
        raise OpenSSLObjectError(f"Failed to parse certificate(s): {exc}") from exc

    if not certs:
        raise OpenSSLObjectError("No certificate found in content")

    return certs


def _name_to_dict_and_ordered(name: x509.Name) -> (Dict[str, str], List[List[str]]):
    """
    Konvertiert ein x509.Name in
      - dict: {oid_name: value}
      - ordered: [[oid_name, value], ...]
    Letzte Wiederholung gewinnt im Dict (wie x509_certificate_info).
    """
    result: Dict[str, str] = {}
    ordered: List[List[str]] = []

    for rdn in name.rdns:
        for attr in rdn:
            key = getattr(attr.oid, "_name", attr.oid.dotted_string)
            value = attr.value
            result[key] = value
            ordered.append([key, value])

    return result, ordered


def _get_subject_alt_name(
    cert: x509.Certificate,
) -> (Optional[List[str]], Optional[bool]):
    """
    Liest subjectAltName und gibt (liste, critical) zurück.
    Liste-Elemente sind Strings wie "DNS:example.com", "IP:1.2.3.4".
    """
    try:
        ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
    except x509.ExtensionNotFound:
        return None, None

    values: List[str] = []
    for gn in ext.value:
        # cryptography gibt sinnvolle __str__()-Repräsentationen
        values.append(str(gn))

    return values, ext.critical


def _compute_fingerprints(cert: x509.Certificate) -> Dict[str, str]:
    """
    Fingerprints des gesamten Zertifikats, für gängige Hashes.
    Hex mit ":" getrennt (wie community.crypto).
    """
    algorithms = [
        ("sha1", hashes.SHA1()),
        ("sha224", hashes.SHA224()),
        ("sha256", hashes.SHA256()),
        ("sha384", hashes.SHA384()),
        ("sha512", hashes.SHA512()),
    ]
    result: Dict[str, str] = {}

    for name, algo in algorithms:
        try:
            fp_bytes = cert.fingerprint(algo)
        except Exception:
            continue
        result[name] = ":".join(f"{b:02x}" for b in fp_bytes)

    return result


class CertificateInfoRetrieval:
    """
    Ersatz für community.crypto CertificateInfoRetrieval.

    Nutzung:
        cert_info = CertificateInfoRetrieval(
            module=module,
            content=data,
            valid_at=module.params.get("valid_at"),
        )
        info = cert_info.get_info(prefer_one_fingerprint=False)

    Wichtige Keys im Rückgabewert:
        - not_before (ASN.1 TIME)
        - not_after (ASN.1 TIME)
        - expired (bool)
        - subject, subject_ordered
        - issuer, issuer_ordered
        - subject_alt_name
        - fingerprints
        - valid_at
    """

    def __init__(
        self,
        module=None,
        content: Union[bytes, bytearray, str] = None,
        valid_at: Optional[Dict[str, str]] = None,
    ) -> None:
        self.module = module
        if content is None:
            raise OpenSSLObjectError("CertificateInfoRetrieval requires 'content'")
        self._certs: List[x509.Certificate] = _load_certificates(content)
        self._valid_at_specs: Dict[str, str] = valid_at or {}

    def _get_primary_cert(self) -> x509.Certificate:
        """
        Für deine Nutzung reicht das erste Zertifikat (Leaf).
        """
        return self._certs[0]

    def _compute_valid_at(
        self,
        not_before_raw: Optional[datetime],
        not_after_raw: Optional[datetime],
    ) -> Dict[str, bool]:
        """
        Erzeugt das valid_at-Dict basierend auf self._valid_at_specs.
        Semantik: gültig, wenn
          not_before <= t <= not_after
        (alle Zeiten in UTC).
        """
        result: Dict[str, bool] = {}
        if not self._valid_at_specs:
            return result

        # Grenzen in UTC-aware umwandeln
        nb_utc: Optional[datetime] = None
        na_utc: Optional[datetime] = None

        if not_before_raw is not None:
            # _to_utc_naive gibt naive UTC; hier machen wir tz-aware
            nb_utc = _to_utc_naive(not_before_raw).replace(tzinfo=timezone.utc)
        if not_after_raw is not None:
            na_utc = _to_utc_naive(not_after_raw).replace(tzinfo=timezone.utc)

        for name, spec in self._valid_at_specs.items():
            try:
                point = get_relative_time_option(
                    value=spec,
                    input_name=f"valid_at[{name}]",
                    with_timezone=True,
                )
            except OpenSSLObjectError:
                # ungültige Zeitangabe → False
                result[name] = False
                continue

            if point is None:
                # None interpretieren wir als "kein Check"
                result[name] = False
                continue

            is_valid = True
            if nb_utc is not None and point < nb_utc:
                is_valid = False
            if na_utc is not None and point > na_utc:
                is_valid = False

            result[name] = is_valid

        return result

    def get_info(self, prefer_one_fingerprint: bool = False) -> Dict[str, Any]:
        """
        Liefert ein Info-Dict.

        prefer_one_fingerprint:
          - False (Default): 'fingerprints' enthält mehrere Hashes.
          - True: zusätzlich 'fingerprint' / 'public_key_fingerprint' mit bevorzugtem Algo
                  (sha256, Fallback sha1).
        """
        cert = self._get_primary_cert()

        # Zeit
        not_before_raw = getattr(
            cert,
            "not_valid_before",
            getattr(cert, "not_valid_before_utc", None),
        )
        not_after_raw = getattr(
            cert,
            "not_valid_after",
            getattr(cert, "not_valid_after_utc", None),
        )

        not_before_asn1 = _format_asn1_time(not_before_raw) if not_before_raw else None
        not_after_asn1 = _format_asn1_time(not_after_raw) if not_after_raw else None

        now_utc_naive = datetime.utcnow()
        expired = False
        if not_after_raw is not None:
            expired = now_utc_naive > _to_utc_naive(not_after_raw)

        # Subject / Issuer
        subject, subject_ordered = _name_to_dict_and_ordered(cert.subject)
        issuer, issuer_ordered = _name_to_dict_and_ordered(cert.issuer)

        # SAN
        subject_alt_name, subject_alt_name_critical = _get_subject_alt_name(cert)

        # Fingerprints
        fingerprints = _compute_fingerprints(cert)

        # Optional: Public-Key-Fingerprints, wenn du sie brauchst
        public_key_fingerprints: Dict[str, str] = {}
        try:
            pk = cert.public_key()
            der = pk.public_bytes(
                encoding=x509.Encoding.DER,  # type: ignore[attr-defined]
                format=x509.PublicFormat.SubjectPublicKeyInfo,  # type: ignore[attr-defined]
            )
            # kleines Re-Mapping, um _compute_fingerprints wiederzuverwenden
            pk_cert = x509.load_der_x509_certificate(der, default_backend())
            public_key_fingerprints = _compute_fingerprints(pk_cert)
        except Exception:
            public_key_fingerprints = {}

        # valid_at
        valid_at = self._compute_valid_at(not_before_raw, not_after_raw)

        info: Dict[str, Any] = {
            "not_before": not_before_asn1,
            "not_after": not_after_asn1,
            "expired": expired,
            "subject": subject,
            "subject_ordered": subject_ordered,
            "issuer": issuer,
            "issuer_ordered": issuer_ordered,
            "subject_alt_name": subject_alt_name,
            "subject_alt_name_critical": subject_alt_name_critical,
            "fingerprints": fingerprints,
            "public_key_fingerprints": public_key_fingerprints,
            "valid_at": valid_at,
        }

        # prefer_one_fingerprint: wähle "bevorzugten" Algo (sha256, sonst sha1)
        if prefer_one_fingerprint:

            def _pick_fp(src: Dict[str, str]) -> Optional[str]:
                if not src:
                    return None
                for algo in ("sha256", "sha1", "sha512"):
                    if algo in src:
                        return src[algo]
                # Fallback: irgend einen nehmen
                return next(iter(src.values()))

            fp = _pick_fp(fingerprints)
            if fp is not None:
                info["fingerprint"] = fp

            pk_fp = _pick_fp(public_key_fingerprints)
            if pk_fp is not None:
                info["public_key_fingerprint"] = pk_fp

        return info

import io, math, zipfile
import magic, pefile, yara

from pathlib import Path
from oletools.olevba import VBA_Parser

from ..constants import BAD_EXT, SUSPICIOUS_EXT


class DeepScanner:
    def __init__(self, logger=None):
        self.logger = logger
        self.yara_rules = self._load_yara_rules()

    def _log(self, message: str):
        if self.logger:
            self.logger(message)

    def _load_yara_rules(self):
        current_dir = Path(__file__).parent
        yar_files = list(current_dir.glob("*.yar"))

        if not yar_files:
            self._log(f"[{self.__class__.__name__}] YARA Warning: No .yar files found in {current_dir}")
            return None

        filepaths = {f"rule_{i}": str(p) for i, p in enumerate(yar_files)}

        try:
            compiled = yara.compile(filepaths=filepaths)
            self._log(f"[{self.__class__.__name__}] YARA Engine: Armed with {len(yar_files)} rule file(s).")
            return compiled
        except Exception as e:
            self._log(f"[{self.__class__.__name__}] YARA compilation error: {e}")
            return None

    def analyze(self, attachment) -> tuple[bool, str]:
        filename = (attachment.filename or "").lower()
        payload = attachment.payload or b""

        if filename.endswith(BAD_EXT) or self._has_double_extension(filename):
            return True, f"Blocked or suspicious extension on '{filename}'"

        mime_suspicious, mime_reason = self._check_mime_mismatch(filename, payload)
        if mime_suspicious:
            return True, mime_reason

        if self._is_entropy_suspicious(filename, payload):
            return True, f"High entropy detected in '{filename}' (possible encryption/obfuscation)"

        if self.yara_rules:
            matched, rule_names = self._check_yara(payload)
            if matched:
                return True, f"YARA match on '{filename}': {rule_names}"

        if filename.endswith((".zip", ".7z", ".rar")) and self._inspect_zip(payload):
            return True, f"Suspicious activity or hidden threat inside archive '{filename}'"

        if filename.endswith((".doc", ".xls", ".docm", ".xlsm", ".ppt")) and self._has_dangerous_vba(payload):
            return True, f"Malicious macro or AutoExec routine found in '{filename}'"

        if payload.startswith(b"MZ") and self._has_suspicious_pe(payload):
            return True, f"Packed, compressed, or malformed PE structure in '{filename}'"

        return False, "Clean"

    def _has_double_extension(self, filename: str) -> bool:
        parts = filename.split(".")
        if len(parts) > 2:
            last_ext = f".{parts[-1]}"
            second_last_ext = f".{parts[-2]}"
            return last_ext in BAD_EXT or (second_last_ext in SUSPICIOUS_EXT and last_ext in BAD_EXT)
        return False

    def _check_mime_mismatch(self, filename: str, payload: bytes) -> tuple[bool, str]:
        try:
            mime_checker = magic.Magic(mime=True)
            real_mime = mime_checker.from_buffer(payload)

            if payload.startswith(b"MZ") or "x-dosexec" in real_mime or "x-executable" in real_mime:
                if not filename.endswith(BAD_EXT):
                    return True, f"Masked executable in '{filename}' (real MIME: {real_mime})"

            if filename.endswith(".pdf") and "pdf" not in real_mime:
                return True, f"MIME mismatch for PDF '{filename}' (real MIME: {real_mime})"
        except Exception as e:
            self._log(f"MIME check error: {e}")
        return False, ""

    def _calculate_entropy(self, payload: bytes) -> float:
        if not payload:
            return 0.0
        entropy = 0.0
        length = len(payload)
        for x in range(256):
            p_x = payload.count(bytes([x])) / length
            if p_x > 0:
                entropy -= p_x * math.log2(p_x)
        return entropy

    def _is_entropy_suspicious(self, filename: str, payload: bytes) -> bool:
        if filename.endswith((".zip", ".7z", ".rar", ".png", ".jpg", ".jpeg", ".mp4", ".gz")):
            return False
        return self._calculate_entropy(payload) > 7.2

    def _check_yara(self, payload: bytes) -> tuple[bool, list]:
        try:
            matches = self.yara_rules.match(data=payload)
            if matches:
                return True, [m.rule for m in matches]
        except Exception as e:
            self._log(f"YARA execution error: {e}")
        return False, []

    def _inspect_zip(self, payload: bytes) -> bool:
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as zf:
                for zinfo in zf.infolist():
                    if zinfo.flag_bits & 0x1:
                        return True
                    if zinfo.filename.lower().endswith(BAD_EXT):
                        return True
                    if zinfo.compress_size > 0 and (zinfo.file_size / zinfo.compress_size) > 100:
                        return True
        except Exception:
            return True
        return False

    def _has_dangerous_vba(self, payload: bytes) -> bool:
        try:
            vbaparser = VBA_Parser(filename="attachment", data=payload)
            if vbaparser.detect_vba_macros():
                results = vbaparser.analyze()
                for kw_type, _, _ in results:
                    if kw_type in ("AutoExec", "Suspicious"):
                        return True
        except Exception:
            pass
        return False

    def _has_suspicious_pe(self, payload: bytes) -> bool:
        try:
            pe = pefile.PE(data=payload)
            for section in pe.sections:
                sec_name = section.Name.decode("utf-8", errors="ignore").strip("\x00").lower()
                if any(p in sec_name for p in ["upx", "themida", ".packed", "vmp"]):
                    return True
        except Exception:
            return True
        return False

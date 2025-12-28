import re
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

# Axiom: [State]_[Source]_[Object]_hash
# Example: baseline_code_structure_hash
# We enforce 4 segments, starting with state, ending with hash.
FINGERPRINT_KEY_PATTERN = re.compile(
    r"^(baseline|current)_[a-z]+_[a-z]+_hash$"
)


class InvalidFingerprintKeyError(KeyError):
    """Raised when a key does not conform to the Fingerprint naming axiom."""
    def __init__(self, key: str):
        super().__init__(
            f"Key '{key}' does not conform to the Fingerprint naming axiom "
            "('^(baseline|current)_[a-z]+_[a-z]+_hash$')."
        )


@dataclass
class Fingerprint:
    """
    A dynamic, self-validating container for symbol fingerprints.
    It enforces that all keys adhere to the strict naming axiom.
    """
    _hashes: Dict[str, str] = field(default_factory=dict)

    @staticmethod
    def _validate_key(key: str) -> None:
        if not FINGERPRINT_KEY_PATTERN.match(key):
            raise InvalidFingerprintKeyError(key)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Fingerprint":
        """
        Constructs a Fingerprint from a dictionary.
        Validates all keys immediately. Any invalid key raises InvalidFingerprintKeyError.
        """
        validated_hashes = {}
        for key, value in data.items():
            cls._validate_key(key)
            if value is not None:
                validated_hashes[key] = str(value)
        return cls(_hashes=validated_hashes)

    def to_dict(self) -> Dict[str, str]:
        """Returns a copy of the internal hashes."""
        return self._hashes.copy()

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        # We validate key on read too, to ensure consumer uses correct keys
        self._validate_key(key)
        return self._hashes.get(key, default)

    def __getitem__(self, key: str) -> str:
        self._validate_key(key)
        return self._hashes[key]

    def __setitem__(self, key: str, value: str) -> None:
        self._validate_key(key)
        self._hashes[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self._hashes

    def items(self):
        return self._hashes.items()
        
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Fingerprint):
            return NotImplemented
        return self._hashes == other._hashes
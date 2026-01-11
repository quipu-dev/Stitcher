import hashlib
from typing import Protocol, List, Union
from stitcher.spec import FunctionDef, ClassDef, Fingerprint, ArgumentKind


class EntityHasher(Protocol):
    def update(
        self, entity: Union[FunctionDef, ClassDef], fingerprint: Fingerprint
    ) -> None: ...


class StructureHasher:
    def update(
        self, entity: Union[FunctionDef, ClassDef], fingerprint: Fingerprint
    ) -> None:
        if isinstance(entity, FunctionDef):
            h = self._compute_func_hash(entity)
            fingerprint["current_code_structure_hash"] = h
        elif isinstance(entity, ClassDef):
            # Class-level structure hash logic can be added here if needed in future.
            # Currently Stitcher focuses on methods.
            pass

    def _compute_func_hash(self, func: FunctionDef) -> str:
        # Extracted from stitcher.spec.models.FunctionDef.compute_fingerprint
        parts = [
            f"name:{func.name}",
            f"async:{func.is_async}",
            f"static:{func.is_static}",
            f"class:{func.is_class}",
            f"ret:{func.return_annotation or ''}",
        ]

        for arg in func.args:
            arg_sig = (
                f"{arg.name}:{arg.kind}:{arg.annotation or ''}:{arg.default or ''}"
            )
            parts.append(arg_sig)

        sig_str = "|".join(parts)
        return hashlib.sha256(sig_str.encode("utf-8")).hexdigest()


class SignatureTextHasher:
    def update(
        self, entity: Union[FunctionDef, ClassDef], fingerprint: Fingerprint
    ) -> None:
        if isinstance(entity, FunctionDef):
            text = self._get_signature_string(entity)
            fingerprint["current_code_signature_text"] = text

    def _get_signature_string(self, func: FunctionDef) -> str:
        # Extracted from stitcher.spec.models.FunctionDef.get_signature_string
        parts = []
        if func.is_async:
            parts.append("async")
        parts.append("def")
        parts.append(f"{func.name}(")

        arg_strs = []
        for arg in func.args:
            s = arg.name
            if arg.kind == ArgumentKind.VAR_POSITIONAL:
                s = f"*{arg.name}"
            elif arg.kind == ArgumentKind.VAR_KEYWORD:
                s = f"**{arg.name}"

            if arg.annotation:
                s += f": {arg.annotation}"
            if arg.default:
                s += f" = {arg.default}"
            arg_strs.append(s)

        parts.append(", ".join(arg_strs))
        parts.append(")")

        if func.return_annotation:
            parts.append(f"-> {func.return_annotation}")

        parts.append(":")
        return " ".join(parts).replace("( ", "(").replace(" )", ")").replace(" :", ":")


class DocstringHasher:
    def update(
        self, entity: Union[FunctionDef, ClassDef], fingerprint: Fingerprint
    ) -> None:
        doc = getattr(entity, "docstring", None)
        if doc:
            h = hashlib.sha256(doc.encode("utf-8")).hexdigest()
            fingerprint["current_code_docstring_hash"] = h


class PythonFingerprintStrategy:
    def __init__(self):
        self.hashers: List[EntityHasher] = [
            StructureHasher(),
            SignatureTextHasher(),
            DocstringHasher(),
        ]

    def compute(self, entity: Union[FunctionDef, ClassDef]) -> Fingerprint:
        fp = Fingerprint()
        for hasher in self.hashers:
            hasher.update(entity, fp)
        return fp

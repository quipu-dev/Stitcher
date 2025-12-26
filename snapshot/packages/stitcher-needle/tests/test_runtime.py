import json
from pathlib import Path
from stitcher.needle import Needle, L

def test_needle_loading_and_fallback(tmp_path: Path):
    # 1. Setup SST structure
    root = tmp_path
    needle_dir = root / "stitcher" / "needle"
    
    # English (Default)
    en_dir = needle_dir / "en"
    en_dir.mkdir(parents=True)
    
    # en/cli.json
    (en_dir / "cli.json").write_text(json.dumps({
        "hello": "Hello World",
        "only_en": "I am English"
    }))
    
    # en/auth/login.json
    (en_dir / "auth").mkdir()
    (en_dir / "auth" / "login.json").write_text(json.dumps({
        "fail": "Login Failed"
    }))

    # Chinese (Target)
    zh_dir = needle_dir / "zh"
    zh_dir.mkdir(parents=True)
    
    # zh/cli.json
    (zh_dir / "cli.json").write_text(json.dumps({
        "hello": "你好世界"
    }))

    # 2. Initialize Runtime
    rt = Needle(root_path=root, default_lang="en")

    # 3. Test: Target Language Hit
    # L.cli.hello -> "你好世界" (in zh)
    assert rt.get(L.cli.hello, lang="zh") == "你好世界"

    # 4. Test: Fallback to Default Language
    # L.cli.only_en -> "I am English" (missing in zh, fallback to en)
    assert rt.get(L.cli.only_en, lang="zh") == "I am English"

    # 5. Test: Namespace Flattening
    # L.auth.login.fail -> "Login Failed"
    assert rt.get(L.auth.login.fail) == "Login Failed"

    # 6. Test: Ultimate Identity Fallback
    # L.unknown.key -> "unknown.key"
    assert rt.get(L.unknown.key) == "unknown.key"
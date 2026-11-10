import hashlib
import json

from scripts.reproduce_local import export


def test_export_excludes_nested_secrets_real_artifacts_and_untracked_pdf(tmp_path, monkeypatch):
    files = {
        "README.md": "public",
        "src/public.py": "pass",
        ".env.example": "EXAMPLE=",
        "docs/.env.local": "secret",
        "docs/secrets/password.txt": "secret",
        "docs/key.pem": "secret",
        "docs/state.sqlite3": "private",
        "docs/model.pickle": "private",
        "models/weights.joblib": "private",
        "data/raw/month.parquet": "private",
        "Informe_Proyecto_MLOps_NYC_Taxi_2.pdf": "untracked",
    }
    for name, value in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)

    def listed(command, **kwargs):
        names = (
            files
            if "--exclude-standard" in command
            else ["README.md", "src/public.py", ".env.example"]
        )
        return ("\0".join(names) + "\0").encode()

    monkeypatch.setattr("scripts.reproduce_local.subprocess.check_output", listed)
    destination = tmp_path / "export"
    manifest = export(tmp_path, destination)
    assert set(manifest) == {"README.md", "src/public.py", ".env.example"}
    for name, digest in manifest.items():
        assert hashlib.sha256((destination / name).read_bytes()).hexdigest() == digest
    assert json.loads((destination / "EXPORT_MANIFEST.json").read_text())["files"] == manifest
    assert not (destination / ".git").exists()

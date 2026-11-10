"""Restaurar solo el estado de una operacion propia; nunca pisar un alias ajeno."""

import argparse
import uuid
from contextlib import nullcontext
from pathlib import Path

from src.ingestion.download import month_lock
from src.retraining.lifecycle import aliases, client_for, event, events
from src.retraining.protocol import inside, read_json
from src.training.champion import ChampionUnavailable
from src.training.native_supervisor import process_alive
from src.validation.schema import fingerprint


def restore(operation, controller, *, root=None, already_locked=False, recover_stale_lock=False):
    root = Path(root or Path.cwd()).resolve()
    journal = events(root, operation)
    if not journal or journal[0]["state"] != "PREPARED":
        raise ChampionUnavailable("No existe version previa recuperable")
    first = journal[0]
    before, after = first["previous"], first["proposed"]
    active = inside(root, first["active_path"])
    controller.verify_binding(root, active)
    if controller.binding() != first["controller"]:
        raise ChampionUnavailable("Controlador distinto del autorizado para la operacion")
    client = client_for(after)
    expected = first["previous_aliases"]
    name = after["target"]["name"]
    if recover_stale_lock:
        marker = inside(root, "tracking/lifecycle/.ingestion.lock")
        if marker.exists():
            owner = int(marker.read_text(encoding="utf-8"))
            if owner <= 0 or process_alive(owner):
                raise ChampionUnavailable("Bloqueo con propietario activo; no archivar")
            archived = marker.with_name(f"stale-lock-{uuid.uuid4().hex}.txt")
            marker.rename(archived)
            event(root, operation, "STALE_LOCK_ARCHIVED", owner_pid=owner, archived=archived.name)
    with nullcontext() if already_locked else month_lock(inside(root, "tracking/lifecycle")):
        current = aliases(client, name)
        valid_aliases = (expected, {**expected, "champion": after["target"]["version"]})
        current_config = read_json(active)
        if current not in valid_aliases or fingerprint(current_config) not in (
            fingerprint(before),
            fingerprint(after),
        ):
            event(root, operation, "CONFLICT", observed_aliases=current)
            raise ChampionUnavailable("Estado ajeno; no sobrescribir durante rollback")
        if (
            not recover_stale_lock
            and journal[-1]["state"] == "ROLLED_BACK"
            and current == expected
            and fingerprint(current_config) == fingerprint(before)
        ):
            controller.smoke(before)
            return journal[-1]
        controller.verify_package(before)
        controller.stop()
        if aliases(client, name) != current:
            event(root, operation, "CONFLICT", reason="ALIAS_CHANGED_DURING_ROLLBACK")
            raise ChampionUnavailable("Alias concurrente durante rollback")
        if current != expected:
            client.set_registered_model_alias(name, "champion", expected["champion"])
        temporary = active.with_suffix(".rollback")
        with temporary.open("xb") as stream:
            stream.write(bytes.fromhex(first["previous_bytes_hex"]))
        temporary.replace(active)
        try:
            controller.start()
            controller.smoke(before)
            if aliases(client, name) != expected:
                raise ChampionUnavailable("Alias anterior no restaurado")
        except BaseException as error:
            event(root, operation, "ROLLBACK_FAILED", error=str(error))
            raise
        return event(
            root,
            operation,
            "ROLLED_BACK",
            restored_version=expected["champion"],
            approval_sha256=fingerprint(before),
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--controller", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--test-only", action="store_true")
    parser.add_argument("--recover-stale-lock", action="store_true")
    args = parser.parse_args()
    from src.retraining.services import ManagedAPI

    api = ManagedAPI.from_receipt(args.controller, root=args.root, test_only=args.test_only)
    print(restore(args.operation, api, root=args.root, recover_stale_lock=args.recover_stale_lock))


if __name__ == "__main__":
    main()

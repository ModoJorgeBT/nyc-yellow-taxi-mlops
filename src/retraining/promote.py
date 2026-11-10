"""Promocion explicita con compensacion; ningun gate negativo admite excepcion."""

import argparse
from pathlib import Path

from src.ingestion.download import month_lock
from src.retraining.lifecycle import (
    aliases,
    atomic_json,
    client_for,
    event,
    events,
    read_approval,
    verify_target,
)
from src.retraining.protocol import inside, pinned, read_json
from src.training.champion import ChampionUnavailable
from src.validation.run import _sha256
from src.validation.schema import fingerprint


def promote(approval_path, active_path, controller, *, root=None, test_only=False, fault=None):
    root = Path(root or Path.cwd()).resolve()
    approval_path = inside(root, approval_path)
    approved_bytes_sha256 = _sha256(approval_path)
    active = inside(root, active_path)
    if active == root / "configs/champion.yaml":
        raise ChampionUnavailable("T19 permanece intacto; usar configuracion operativa separada")
    after = read_approval(approval_path, root=root, test_only=test_only)
    if after["action"] != "PROMOTE":
        raise ChampionUnavailable("Esta accion requiere aprobacion PROMOTE")
    operation = after["operation_id"]
    journal = events(root, operation)
    if journal:
        if journal[-1]["state"] == "VERIFIED":
            if journal[-1].get("approval_sha256") != fingerprint(after):
                raise ChampionUnavailable("Operacion ya verificada con otra aprobacion")
            controller.verify_binding(root, active)
            from src.retraining.lifecycle import resolve_champion

            resolve_champion(active, root=root, test_only=test_only)
            if fingerprint(read_json(active)) != fingerprint(after):
                raise ChampionUnavailable("La aprobacion activa cambio despues de promover")
            controller.smoke(after)
            return journal[-1]
        raise ChampionUnavailable("Operacion existente: recuperar sin repetir promocion")
    before_bytes = active.read_bytes()
    before = read_json(active)
    if before.get("format_version") == 2:
        from src.retraining.lifecycle import resolve_champion

        resolve_champion(active, root=root, test_only=test_only)
    else:
        from src.training.champion import resolve_champion

        resolve_champion(active, root=root)
    if after.get("previous_approval_sha256") != _sha256(active):
        raise ChampionUnavailable("Aprobacion ligada a otro estado anterior")
    if not test_only:
        from src.retraining.lifecycle import require_gate

        require_gate(root, after["gate"], after["target"], previous=before["target"])
    client = client_for(after)
    verify_target(client, after)
    name = after["target"]["name"]
    expected = aliases(client, name)
    if expected.get("champion") != before["target"]["version"] or before["target"]["name"] != name:
        raise ChampionUnavailable("La version previa no coincide con el Registry")
    controller.verify_binding(root, active)
    controller.verify_package(after)
    lock = inside(root, "tracking/lifecycle")
    lock.mkdir(parents=True, exist_ok=True)
    with month_lock(lock):
        event(
            root,
            operation,
            "PREPARED",
            previous=before,
            previous_bytes_hex=before_bytes.hex(),
            previous_aliases=expected,
            active_path=str(active.relative_to(root)),
            proposed=after,
            approval_path=str(Path(approval_path).resolve().relative_to(root)),
            approval_sha256=fingerprint(after),
            controller=controller.binding(),
        )
        try:
            controller.stop()
            if (
                aliases(client, name) != expected
                or _sha256(active) != after["previous_approval_sha256"]
            ):
                raise ChampionUnavailable("Estado concurrente antes de aplicar")
            verify_target(client, after)
            client.set_registered_model_alias(name, "champion", after["target"]["version"])
            event(root, operation, "ALIAS_APPLIED", approval_sha256=fingerprint(after))
            if fault:
                fault("after_alias")
            atomic_json(active, after)
            event(root, operation, "APPLIED", approval_sha256=fingerprint(after))
            controller.start()
            if fault:
                fault("before_smoke")
            controller.smoke(after)
            if aliases(client, name) != {**expected, "champion": after["target"]["version"]}:
                raise ChampionUnavailable("Alias ajeno despues del smoke")
            pinned(
                root,
                {
                    "path": str(Path(approval_path).resolve().relative_to(root)),
                    "sha256": approved_bytes_sha256,
                },
            )
            return event(
                root,
                operation,
                "VERIFIED",
                approval_sha256=fingerprint(after),
                previous_version=before["target"]["version"],
                current_version=after["target"]["version"],
            )
        except BaseException as error:
            event(root, operation, "FAILED", error=str(error), approval_sha256=fingerprint(after))
            from src.retraining.rollback import restore

            restore(operation, controller, root=root, already_locked=True)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--active", type=Path, required=True)
    parser.add_argument("--controller", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()
    # Verificar el gate antes de abrir un controlador o tocar procesos.
    read_approval(args.approval, root=args.root, test_only=args.test_only)
    from src.retraining.services import ManagedAPI

    api = ManagedAPI.from_receipt(args.controller, root=args.root, test_only=args.test_only)
    print(promote(args.approval, args.active, api, root=args.root, test_only=args.test_only))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""kubectl dojo — a terminal-based CKA/CKAD trainer that runs against a real
k0s cluster and checks your work by inspecting live cluster state.

Usage:
    python main.py                 # normal play
    python main.py --reset-progress
    python main.py --kubeconfig ~/.kube/k0s.config
"""
import argparse
import os
import sys

from game import ui
from game.cluster import ClusterClient
from game.content_loader import load_all_modules
from game.models import Module, Objective, Task
from game.progress import ProgressTracker
from game.validator import Validator

CONTENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content")
GAME_NAMESPACE = "game-lab"


def parse_args():
    p = argparse.ArgumentParser(description="kubectl dojo: CKA/CKAD trainer on k0s")
    default_kubeconfig = os.environ.get("KUBECONFIG")
    if not default_kubeconfig:
        # Fall back to the path scripts/install_k0s.sh and install_k0s_macos.sh
        # both write to, so the game works even if KUBECONFIG isn't exported
        # in the current shell.
        candidate = os.path.expanduser("~/.kube/k0s.config")
        if os.path.exists(candidate):
            default_kubeconfig = candidate
    p.add_argument("--kubeconfig", default=default_kubeconfig, help="path to kubeconfig for the k0s cluster")
    p.add_argument("--reset-progress", action="store_true", help="wipe all saved progress and exit")
    p.add_argument("--content-dir", default=CONTENT_DIR, help="override content directory")
    return p.parse_args()


def run_task(task: Task, cluster: ClusterClient, validator: Validator, progress: ProgressTracker):
    hint_index = 0
    # setup commands are idempotent-ish (content authors should use
    # '--ignore-not-found' / '|| true' style patterns where relevant)
    if task.setup:
        cluster.run_commands(task.setup)

    while True:
        ui.clear()
        ui.task_screen(task, namespace_hint=GAME_NAMESPACE)
        if progress.is_complete(task.id):
            ui.info("(already marked complete — checking again just confirms it still holds)")
        choice = ui.prompt(">").strip().lower()

        if choice in ("b", "back"):
            return
        if choice in ("q", "quit"):
            sys.exit(0)
        if choice in ("h", "hint"):
            ui.show_hint(task, hint_index)
            hint_index = min(hint_index + 1, max(len(task.hints) - 1, 0))
            ui.prompt("\n(press enter to continue)")
            continue
        if choice in ("r", "reset"):
            if task.cleanup:
                cluster.run_commands(task.cleanup)
                ui.warn("Task resources reset.")
            else:
                ui.warn("This task has no cleanup commands defined.")
            progress.reset_task(task.id)
            ui.prompt("\n(press enter to continue)")
            continue
        if choice in ("c", "check", ""):
            results = validator.run_checks(task.checks)
            passed = ui.show_check_results(results)
            if passed:
                progress.mark_complete(task.id)
                ui.show_exam_tip(task.exam_tip)
            ui.prompt("\n(press enter to continue)")
            continue

        ui.warn(f"Unrecognized command: {choice}")
        ui.prompt("(press enter to continue)")


def run_objective(objective: Objective, cluster: ClusterClient, validator: Validator, progress: ProgressTracker):
    while True:
        ui.clear()
        ui.task_menu(objective, progress)
        choice = ui.prompt(">").strip().lower()
        if choice in ("b", "back"):
            return
        if choice in ("q", "quit"):
            sys.exit(0)
        if choice.isdigit() and 1 <= int(choice) <= len(objective.tasks):
            run_task(objective.tasks[int(choice) - 1], cluster, validator, progress)
            continue
        ui.warn(f"Unrecognized selection: {choice}")
        ui.prompt("(press enter to continue)")


def run_module(module: Module, cluster: ClusterClient, validator: Validator, progress: ProgressTracker):
    while True:
        ui.clear()
        ui.objective_menu(module, progress)
        choice = ui.prompt(">").strip().lower()
        if choice in ("b", "back"):
            return
        if choice in ("q", "quit"):
            sys.exit(0)
        if choice.isdigit() and 1 <= int(choice) <= len(module.objectives):
            run_objective(module.objectives[int(choice) - 1], cluster, validator, progress)
            done, total = progress.stats(t.id for t in module.all_tasks())
            if total > 0 and done == total:
                ui.clear()
                ui.celebrate_module_complete(module.title)
                ui.prompt("\n(press enter to continue)")
            continue
        ui.warn(f"Unrecognized selection: {choice}")
        ui.prompt("(press enter to continue)")


def run_track(modules, cluster, validator, progress, exam_label: str):
    while True:
        ui.clear()
        ui.module_menu(modules, progress, exam_label)
        choice = ui.prompt(">").strip().lower()
        if choice in ("b", "back"):
            return
        if choice in ("q", "quit"):
            sys.exit(0)
        if choice.isdigit() and 1 <= int(choice) <= len(modules):
            run_module(modules[int(choice) - 1], cluster, validator, progress)
            continue
        ui.warn(f"Unrecognized selection: {choice}")
        ui.prompt("(press enter to continue)")


def main():
    args = parse_args()
    progress = ProgressTracker()

    if args.reset_progress:
        progress.reset_all()
        print("Progress reset.")
        return

    cluster = ClusterClient(kubeconfig=args.kubeconfig)
    validator = Validator(cluster)

    try:
        cka_modules = load_all_modules(args.content_dir, exam="CKA")
        ckad_modules = load_all_modules(args.content_dir, exam="CKAD")
    except RuntimeError as e:
        print(f"Error loading content: {e}")
        sys.exit(1)

    connected = cluster.check_connection()
    if connected:
        cluster.ensure_namespace(GAME_NAMESPACE)

    while True:
        ui.clear()
        ui.banner()
        ui.connection_status(connected, cluster.current_context() if connected else "n/a", args.kubeconfig)

        cka_ids = [t.id for m in cka_modules for t in m.all_tasks()]
        ckad_ids = [t.id for m in ckad_modules for t in m.all_tasks()]
        cka_done, cka_total = progress.stats(cka_ids)
        ckad_done, ckad_total = progress.stats(ckad_ids)

        ui.main_menu(cka_done, cka_total, ckad_done, ckad_total)
        choice = ui.prompt(">").strip().lower()

        if choice == "1":
            run_track(cka_modules, cluster, validator, progress, "CKA")
        elif choice == "2":
            run_track(ckad_modules, cluster, validator, progress, "CKAD")
        elif choice == "3":
            connected = cluster.check_connection()
            ui.connection_status(connected, cluster.current_context() if connected else "n/a", args.kubeconfig)
            if connected:
                ui.info(cluster.run_raw("kubectl get nodes -o wide"))
            ui.prompt("\n(press enter to continue)")
        elif choice == "4":
            confirm = ui.prompt("Type 'yes' to wipe all saved progress:")
            if confirm.strip().lower() == "yes":
                progress.reset_all()
                ui.warn("Progress wiped.")
            ui.prompt("(press enter to continue)")
        elif choice in ("q", "quit"):
            print("Happy kubectl-ing!")
            sys.exit(0)
        else:
            ui.warn(f"Unrecognized selection: {choice}")
            ui.prompt("(press enter to continue)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBye!")
        sys.exit(0)

"""publish_github.py — Initialisation et publication automatique sur GitHub.

Ce script automatise le cycle complet de mise en ligne d'un projet :

1. Création du dépôt distant (public ou privé) via l'API GitHub (PyGithub).
2. Initialisation du dépôt Git local (``git init``) si nécessaire.
3. Ajout de tous les fichiers et création d'un commit.
4. Push du code sur la branche principale (``main``) du dépôt distant.

Authentification :
    Le script lit le *Personal Access Token* (PAT) dans la variable
    d'environnement ``GITHUB_TOKEN``. Le token doit posséder la permission
    ``repo`` (création de dépôts, push).

    export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
    python publish_github.py --name colored-score --public

Usage typique :

    # Dépôt public
    python publish_github.py --repo-name colored-score --public

    # Dépôt privé, avec description et branche personnalisée
    python publish_github.py --repo-name colored-score --private \
        --description "Partitions colorées Baby Einstein" --branch main
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import List, Optional

try:
    from github import Github, GithubException
except ImportError:  # pragma: no cover - dépend de l'environnement
    Github = None  # type: ignore
    GithubException = Exception  # type: ignore


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PublishError(Exception):
    """Erreur durant la publication GitHub."""


# ---------------------------------------------------------------------------
# Utilitaires Git
# ---------------------------------------------------------------------------


def _run(cmd: List[str], cwd: str, check: bool = True) -> subprocess.CompletedProcess:
    """Exécute une commande shell et retourne le résultat.

    Raises:
        PublishError: si la commande échoue et ``check`` est True.
    """
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise PublishError(
            f"Commande échouée : {' '.join(cmd)}\n{result.stderr.strip()}"
        )
    return result


def is_git_repo(directory: str) -> bool:
    """Retourne True si ``directory`` contient déjà un dépôt Git."""
    return os.path.isdir(os.path.join(directory, ".git"))


def git_init(directory: str, branch: str = "main") -> None:
    """Initialise un dépôt Git local avec la branche donnée."""
    if is_git_repo(directory):
        print("[git] Dépôt local déjà initialisé.")
        return
    print("[git] Initialisation du dépôt local...")
    _run(["git", "init", "-b", branch], cwd=directory)
    # ``-b`` n'existe pas sur de très vieux Git : repli sur checkout.
    res = _run(["git", "symbolic-ref", "HEAD", f"refs/heads/{branch}"], cwd=directory,
               check=False)
    if res.returncode != 0:
        _run(["git", "checkout", "-b", branch], cwd=directory, check=False)


def git_commit_all(directory: str, message: str) -> None:
    """Ajoute tous les fichiers et crée un commit (si des changements existent)."""
    _run(["git", "add", "-A"], cwd=directory)

    # Rien à commiter ?
    status = _run(["git", "status", "--porcelain"], cwd=directory)
    if not status.stdout.strip():
        print("[git] Aucun changement à commiter.")
        return

    # Identité de secours si Git n'est pas configuré.
    if not _has_git_identity(directory):
        _run(["git", "config", "user.name", "colored-score-bot"], cwd=directory)
        _run(["git", "config", "user.email", "colored-score-bot@users.noreply.github.com"],
             cwd=directory)

    print(f"[git] Commit : {message!r}")
    _run(["git", "commit", "-m", message], cwd=directory)


def _has_git_identity(directory: str) -> bool:
    """Vérifie qu'une identité Git (user.name/email) est définie."""
    name = _run(["git", "config", "user.name"], cwd=directory, check=False)
    email = _run(["git", "config", "user.email"], cwd=directory, check=False)
    return bool(name.stdout.strip()) and bool(email.stdout.strip())


def git_push(directory: str, remote_url: str, branch: str) -> None:
    """Configure le remote ``origin`` et pousse la branche."""
    existing = _run(["git", "remote"], cwd=directory, check=False).stdout.split()
    if "origin" in existing:
        _run(["git", "remote", "set-url", "origin", remote_url], cwd=directory)
    else:
        _run(["git", "remote", "add", "origin", remote_url], cwd=directory)

    print(f"[git] Push vers origin/{branch}...")
    _run(["git", "push", "-u", "origin", branch], cwd=directory)


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------


def create_remote_repo(token: str, repo_name: str, private: bool,
                       description: str = "") -> str:
    """Crée le dépôt distant et retourne son URL HTTPS (avec token intégré).

    Args:
        token: Personal Access Token GitHub.
        repo_name: nom du dépôt (ex : "colored-score").
        private: True pour un dépôt privé, False pour public.
        description: description du dépôt.

    Raises:
        PublishError: si la création échoue.
    """
    if Github is None:
        raise PublishError(
            "PyGithub n'est pas installé. Exécutez : pip install PyGithub"
        )

    client = Github(token)
    try:
        user = client.get_user()
        login = user.login
    except GithubException as exc:
        raise PublishError(f"Authentification GitHub échouée : {exc.data or exc}") from exc

    try:
        repo = user.create_repo(
            name=repo_name,
            private=private,
            description=description,
            auto_init=False,
            has_issues=True,
            has_wiki=False,
        )
        print(f"[github] Dépôt créé : {repo.html_url}")
    except GithubException as exc:
        if exc.status == 422:  # le dépôt existe déjà
            print(f"[github] Le dépôt '{repo_name}' existe déjà : réutilisation.")
            repo = user.get_repo(repo_name)
        else:
            raise PublishError(f"Création du dépôt échouée : {exc.data or exc}") from exc

    # URL de push authentifiée (le token n'est pas écrit sur disque).
    return f"https://{token}@github.com/{login}/{repo_name}.git"


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def publish(directory: str, repo_name: str, token: str, private: bool = False,
            description: str = "", branch: str = "main",
            commit_message: str = "Initial commit: Colored-Score") -> str:
    """Exécute tout le pipeline de publication.

    Returns:
        L'URL HTML du dépôt distant.

    Raises:
        PublishError: en cas d'échec à l'une des étapes.
    """
    if not os.path.isdir(directory):
        raise PublishError(f"Répertoire introuvable : {directory}")

    print(f"[pub] Publication de '{repo_name}' (private={private})...")
    remote_url = create_remote_repo(token, repo_name, private, description)

    git_init(directory, branch)
    git_commit_all(directory, commit_message)
    git_push(directory, remote_url, branch)

    # URL « propre » (sans token) pour l'affichage.
    login = remote_url.split("@github.com/")[1].rsplit("/", 1)[0]
    html_url = f"https://github.com/{login}/{repo_name}"
    print(f"[pub] Terminé -> {html_url}")
    return html_url


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Construit l'analyseur d'arguments de la CLI."""
    parser = argparse.ArgumentParser(
        prog="publish-github",
        description="Crée un dépôt GitHub et y pousse ce projet automatiquement.",
    )
    parser.add_argument("--repo-name", required=True, help="Nom du dépôt distant.")
    parser.add_argument("--private", action="store_true", help="Créer un dépôt privé.")
    parser.add_argument("--public", action="store_true", help="Créer un dépôt public.")
    parser.add_argument("--description", default="", help="Description du dépôt.")
    parser.add_argument("--branch", default="main", help="Branche principale (défaut: main).")
    parser.add_argument("--dir", default=".", help="Répertoire local du projet.")
    parser.add_argument("--message", default="Initial commit: Colored-Score",
                        help="Message du commit initial.")
    parser.add_argument("--token", default=None,
                        help="PAT GitHub (sinon variable GITHUB_TOKEN).")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Point d'entrée CLI."""
    args = build_parser().parse_args(argv)

    token = args.token or os.environ.get("GITHUB_TOKEN")
    if not token:
        print(
            "[ERREUR] Token GitHub manquant. Définissez GITHUB_TOKEN "
            "ou passez --token.",
            file=sys.stderr,
        )
        return 2

    # --public l'emporte si les deux sont absents : privé par défaut.
    private = args.private and not args.public

    try:
        url = publish(
            directory=os.path.abspath(args.dir),
            repo_name=args.repo_name,
            token=token,
            private=private,
            description=args.description,
            branch=args.branch,
            commit_message=args.message,
        )
    except PublishError as exc:
        print(f"[ERREUR] {exc}", file=sys.stderr)
        return 1

    print(f"\nSuccès ! Dépôt disponible sur : {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
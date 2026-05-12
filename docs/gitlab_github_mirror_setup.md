# GitLab to GitHub main mirroring

Status: prepared in-repo. Project settings still need to be configured in GitLab and GitHub.

## Target model

- GitLab `main` is the source of truth for the public branch.
- GitHub `main` is the downstream mirror.
- `open_source_public` is only a transition branch until GitLab `main` is cut over.

This does not change the internal branch model:

- `OEDS_Johannes` stays the internal development branch.
- `kit-live` stays the internal live branch.

## CI job

The GitLab CI file contains a `mirror_github_main` job that pushes the current
GitLab `main` commit to GitHub `main`.

Use either this CI job or GitLab's built-in push mirror, not both at the same
time.

The job runs only when all of these are true:

- the pipeline branch is `main`
- `GITHUB_MIRROR_REPO` is set
- `GITHUB_MIRROR_USER` is set
- `GITHUB_MIRROR_TOKEN` is set

Required GitLab CI/CD variables:

- `GITHUB_MIRROR_REPO`
  - example: `johannesschuhmacher/open-energy-data-server-KIT`
- `GITHUB_MIRROR_USER`
  - the GitHub account that owns the token
- `GITHUB_MIRROR_TOKEN`
  - fine-grained PAT for the target repository

## GitHub token permissions

Per GitLab's push mirror documentation, the token needs:

- repository `Contents`: read and write
- repository `Workflows`: read and write if the repository contains `.github/workflows`

## Why direct human pushes to GitHub main are a bad idea

They are not technically impossible, but they create an avoidable split-brain:

- GitLab `main` is supposed to be the source of truth.
- If someone pushes directly to GitHub `main`, GitHub can move ahead of GitLab.
- That already happened once in practice with the public commit `1dcc1d1`.
- After that, the mirror source and the mirror target no longer describe the same public state.

Recommended operational rule:

- humans push public changes to GitLab
- GitLab mirrors to GitHub
- GitHub `main` is treated as read-only except for the mirror actor

If you do not want to block human pushes entirely, the minimum safe rule is:

- everybody understands GitLab `main` is canonical
- any direct GitHub `main` push must be replayed back into GitLab immediately

## GitHub branch protection

Recommended setup for GitHub `main`:

- protect branch `main`
- allow the mirror actor to bypass pull-request requirements if needed
- avoid regular human direct pushes

## Cutover sequence

1. Reconcile the current GitHub-only public commit back into GitLab public history.
2. Move GitLab `main` onto the public history currently represented by `open_source_public`.
3. Add the GitLab CI/CD variables listed above.
4. Push to GitLab `main` and let the mirror job update GitHub `main`.
5. After validation, remove `open_source_public` on both remotes when no longer needed.

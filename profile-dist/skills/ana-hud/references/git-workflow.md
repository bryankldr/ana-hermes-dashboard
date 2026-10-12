# Commit, Rename Repo, and Push — ANA HUD

Covers the endgame after a long uncommitted stretch: checkpoint locally, rename the repo
off the old brand, then authenticate. The user cannot receive a token in chat, so every
auth step hands back a recipe instead.

## 1. Preflight (run before staging anything)

```bash
cd ~/ana-hermes-dashboard
git branch -vv                     # branch + upstream
git remote -v                      # confirm the repo still carries the OLD brand name
git config user.name  || echo "UNSET"   # unset identity aborts the first commit
git config user.email || echo "UNSET"
git status --porcelain             # full picture: modified / deleted / untracked
```

`user.name`/`user.email` unset: ask the user for both, then
`git config user.name "<name>" && git config user.email "<email>"` (repo-local, not `--global`).

## 2. Secret + noise gate

```bash
git ls-files --error-unmatch .env 2>&1 | head -1   # MUST fail => .env is untracked
grep -rInE "(sk_live|sk-|ghp_|gho_|xox[baprs]-|AIza[0-9A-Za-z_-]{20}|eyJ[A-Za-z0-9_-]{20,})" \
     <paths-about-to-be-added> 2>/dev/null          # MUST return nothing
du -sh docs/* | sort -h | tail                    # find the size hogs
```

`ui/index.html` holds `content="__ANA_TOKEN__"` — a server-side placeholder substituted per
page load, never a live token. Seeing it in a grep hit is fine; a 32+ char token is not.

Add to `.gitignore` rather than committing: `layout.json`, `state.json`, `.ana_mode`,
`ui/backup/`, `*.png` screenshots, and any vendored spec/reference folder the user wants
local. Confirm with `git status --porcelain` that the ignored paths vanished from `??`.

## 3. Two-commit split

```bash
git add <refactor paths>                  # ui/src ui/styles index.html docs/REFACTOR_PLAN.md
git -c core.pager=cat diff --cached --stat | tail -20   # read the staged set before committing
git commit -q -m "refactor(ui): split into ES modules and CSS files"

git add -A                                # everything else = features
git -c core.pager=cat diff --cached --stat | tail -20
git commit -q -F - <<'EOF'
feat: FUI HUD, ANA bi-modal persona, live panels, PTY terminal
- <one line per subsystem>
EOF
git log --oneline -3 && git status --porcelain   # empty tree = done
```

Rationale: a no-behavior-change refactor and a batch of features must be revertable
independently. A single commit over weeks of mixed work forces an all-or-nothing revert.

Multi-line commit messages via `git commit -F -` heredoc beat `-m` chains — no shell
quoting surprises with backticks or `+`/`-` diff markers inside the message.

## 4. Brand rename sweep

```bash
git grep -ril <oldbrand> -- .      # case-insensitive, whole tracked tree
```

The file-level rename (env prefix, `.desktop` files, install scripts) is never enough:
stale brand strings survive in `// comments` and CSS section headers. Patch each hit, then
`node --check` the touched JS and confirm `git grep -ic <oldbrand> -- .` returns nothing.

Desktop files live outside the repo — check them separately:
`grep -l -i <oldbrand> ~/Desktop/*.desktop ~/.local/share/applications/*.desktop ~/.config/autostart/*.desktop`.

## 5. Repo rename (user-side) then remote retarget

Renaming on GitHub is a manual web action: repo page → Settings → General → Danger Zone →
Rename. Do this **before** the push, otherwise commits land in the old-named repo.

```bash
git remote set-url origin git@github.com:<owner>/<new-name>.git     # SSH
git remote set-url origin https://github.com/<owner>/<new-name>.git  # HTTPS
```

Check whether the target is public before pushing anything sensitive:
`curl -s https://api.github.com/repos/<owner>/<name>` → read `private` / `visibility`.

**A `404` from that endpoint does not mean the repo is missing.** GitHub returns `404`
(not `403`) for a private repo when the request carries no auth, so a 404 is the
*expected* reply for a repo that exists and is private. Disambiguate before
concluding anything:

```bash
curl -s https://api.github.com/users/<owner>          # does the account exist at all?
curl -s https://api.github.com/users/<owner>/repos?per_page=100   # public_repos list
git ls-remote origin                                  # authoritative — works over SSH
```

`ls-remote` is the only one of the three that speaks to the real repo with your
credentials. Use it as the source of truth; the REST calls only tell you what an
anonymous visitor would see.

**Retargeting a remote to a different repo leaves a stale tracking ref.**
`refs/remotes/origin/main` keeps pointing at the OLD repository's SHA, so
`git status -sb` reports phantom ahead/behind counts and `--force-with-lease`
computes its lease against a commit that has nothing to do with the new repo. Clear it
before rewriting history:

```bash
git update-ref -d refs/remotes/origin/main    # or: git remote prune origin
git fetch origin                              # now origin/main == the new repo's real HEAD
```

## 6. Auth — hand back a recipe, never request the secret

```bash
GIT_TERMINAL_PROMPT=0 timeout 20 git push --dry-run origin main
ssh -o BatchMode=yes -T git@github.com   # SSH identity probe
env | grep -cE 'GITHUB_TOKEN|GH_TOKEN'  # is a PAT exported?
```

Diagnose before promising a push:
- `could not read Username for 'https://github.com': terminal prompts disabled` → no credential helper, no PAT, no SSH key. Push is blocked.
- `Permission denied (publickey)` → no SSH identity (`ssh-add -l` → `The agent has no identities`).
- A `GITHUB_TOKEN=` line that is commented out in `~/.hermes/.env` does not count — grep for active `^GITHUB_TOKEN=.+` (nonzero count), not for the key name.

Offer both paths and stop:

**SSH (one-time):** `ssh-keygen -t ed25519 -C "<email>" -f ~/.ssh/id_ed25519`, paste
`cat ~/.ssh/id_ed25519.pub` into GitHub Settings → SSH keys, then `git push -u origin main`.

**HTTPS PAT:** fine-grained token, Contents → Read & write on the one repo, then
`git remote set-url origin https://<TOKEN>@github.com/<owner>/<name>.git && git push -u origin main`.
The token persists in plaintext in `.git/config`; strip it afterwards with
`git remote set-url` (no `@TOKEN`).

Never type a PAT into the conversation or into `browser_type`. The user pastes it into their
own terminal or GitHub UI.

Adding the SSH key is a user-side step by design: the headless browser session is not
logged into GitHub, and you must never log in as the user. Generate the key, print the
pubkey, hand it over, wait for "done", then continue.

## 7. Verify

```bash
git status -sb                          # ## main...origin/main [ahead N] then N=0 after push
git log --oneline -3
ss -tlnp | grep 8730                    # the live server must survive the whole operation
```

**`ls-remote` matching your local SHA is not proof the tree arrived.** It proves a ref
points at that commit. Clone it and look at the actual content when the claim matters:

```bash
git clone --depth 1 <remote-url> "$SCRATCH/verify-clone"
git -C "$SCRATCH/verify-clone" log --oneline
grep -ril <oldbrand> "$SCRATCH/verify-clone" --exclude-dir=.git   # MUST return nothing
rm -rf "$SCRATCH/verify-clone"
```

## 8. History rewrite — one clean commit

Asked for "squash into a single commit, no trace of the old brand"?

`git reset --soft <commit>~1` is the reflex and it is **wrong when `<commit>` is a root
commit**: a root has no parent, so `~1` errors out, and a partial application of the
intent leaves the unwanted root commit in place as the new history's foundation — the
exact thing the user asked to remove. Check first:

```bash
git rev-list --parents -n 1 <commit> | wc -w    # 1 => root commit, ~1 unavailable
```

Orphan branch is the correct mechanism — it builds a commit with no parents from the
working tree as it stands:

```bash
git branch backup/pre-rewrite                       # reversible checkpoint first
git checkout --orphan clean-main
git reset                                            # unstage everything, keep the tree
git add -A
git -c core.pager=cat diff --cached --stat | tail   # read the whole set before committing
git commit -q -F - <<'EOF'
feat: <title>
EOF
```

`git checkout --orphan` keeps the index and working tree but detaches them from history,
so `git reset` clears the stale staging state without touching file contents.

Promote it to the real branch name — a bare `git branch -m` fails with
`a branch named '<name>' already exists`, so delete the old branch first:

```bash
git branch -D main            # safe: backup ref still holds the old history
git branch -m clean-main main
git branch -D backup/pre-rewrite
git remote set-url origin git@github.com:<owner>/<repo>.git
git fetch origin && git branch --set-upstream-to=origin/main main
```

**A repo created through the GitHub web UI already contains an `Initial commit`** with an
auto-generated placeholder README, so a first push to it is rejected as non-fast-forward.
Confirm the placeholder is the only thing there, then overwrite it with
`--force-with-lease` (never bare `--force` — the lease fails if the remote moved since
your last fetch):

```bash
git ls-remote origin                        # see what is actually on the remote
git show origin/main:README.md              # prove it is the auto-generated stub
git push --force-with-lease origin main
```

After a history rewrite, warn the user explicitly about the blast radius: every existing
clone of that repo needs `git fetch && git reset --hard origin/main`. Force-pushing is
irreversible for anyone who already pulled, so the commits you dropped are gone from that
repo permanently — say so before running it, not after.

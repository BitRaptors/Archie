# Archie Share — Upload Blueprint for Sharing

Share your architecture blueprint via a URL. Useful for showing teammates, stakeholders, or clients an analysis of your codebase without needing them to install anything.

**Prerequisites:** Requires `.archie/blueprint.json`. Run `/archie-scan` (or `/archie-deep-scan`) first if it doesn't exist.

## Pick upload target

Before uploading, check whether an enterprise profile already exists:

```bash
test -f ~/.archie/share-profile.json && echo "PROFILE_EXISTS" || echo "PROFILE_MISSING"
```

Then ask the user which target to use. Present options based on whether a profile is set up:

If `PROFILE_EXISTS`:

> Which share target?
>
> 1. **Default** — Upload to the BitRaptors share service (our Supabase). Fastest, one-click, recommended for OSS / non-sensitive projects.
> 2. **Enterprise (stored credentials)** — Upload to your pre-configured bucket at `~/.archie/share-profile.json`. Fully automated. Data never touches BitRaptors infra.
> 3. **Enterprise (paste URL)** — Upload to any bucket via a fresh presigned PUT URL you provide now. Zero credentials stored.
> 4. **Re-run setup** — Update `~/.archie/share-profile.json` with new credentials.
>
> Pick `1`, `2`, `3`, or `4`. (Default: `1`.)

If `PROFILE_MISSING`:

> Which share target?
>
> 1. **Default** — Upload to the BitRaptors share service (our Supabase). Fastest, one-click, recommended for OSS / non-sensitive projects.
> 2. **Enterprise (paste URL)** — Upload to any bucket via a presigned PUT URL you provide now. Zero credentials stored.
> 3. **Set up enterprise (stored credentials)** — One-time setup: provide bucket + AWS credentials once, then future shares are fully automated.
>
> Pick `1`, `2`, or `3`. (Default: `1`.)

### Handling the choice

- **Default** → `MODE=default`. No extra flags. Proceed to "Resolve target blueprint".

- **Enterprise (stored credentials)** → `MODE=enterprise-creds`. No extra flags needed — upload.py reads `~/.archie/share-profile.json` directly.

- **Enterprise (paste URL)** → Ask for two URLs:
  > Paste the **PUT URL** (Archie uploads the blueprint JSON here):
  >
  > Paste the **GET URL** (viewer fetches from here; packed into the share URL's fragment):

  Pass them as args on the upload.py command line. Double-quote them — presigned URLs contain `&` and `=`.

- **Set up enterprise / Re-run setup** → Ask for bucket + credentials:
  > Bucket name (e.g. `acme-archie-shares`):
  >
  > Region (e.g. `us-east-1`):
  >
  > Access key ID (AKIA…):
  >
  > Secret access key:
  >
  > Key prefix (default `archie-shares/`):

  Then run setup, then loop back and ask the user which mode to use for this share:
  ```bash
  python3 .archie/share_setup.py --bucket "<BUCKET>" --region "<REGION>" --access-key-id "<AKID>" --secret-access-key "<SECRET>" --key-prefix "<PREFIX>"
  ```
  Security note: tell the user their credentials will appear in the command string for this shell invocation. For the highest security, they should edit `~/.archie/share-profile.json` directly instead — see `docs/enterprise-share-setup.md` for the JSON schema.

## Resolve target blueprint

Read the persisted scope config to determine which blueprint(s) can be shared:

```bash
python3 .archie/intent_layer.py scan-config "$PWD" read
```

- **Exit 1 (no config) or scope is `single` or `whole`** → there's one blueprint at the repo root. Use `TARGET="$PWD"`.
- **scope is `per-package`** → multiple workspace-level blueprints exist.
  - If exactly one workspace is listed → use that one: `TARGET="$PWD/<workspace>"`.
  - If multiple → ask the user:
    > You have per-package blueprints in: `<workspace-1>`, `<workspace-2>`, ...
    > Which one should I share? (number/name/`all`)
    If they answer `all`, loop and upload each separately.
- **scope is `hybrid`** → root has a monorepo-wide blueprint AND each listed workspace has its own.
  - Ask the user:
    > Share the monorepo-wide blueprint, or a specific workspace?
    > Options: `root`, `<workspace-1>`, `<workspace-2>`, ...
  - `root` → `TARGET="$PWD"`. Workspace name → `TARGET="$PWD/<workspace>"`.

## Run

For each resolved `TARGET`:

**Default mode:**

```bash
python3 .archie/upload.py "$TARGET"
```

**Enterprise (stored credentials) mode:**

```bash
python3 .archie/upload.py "$TARGET" --mode enterprise-creds
```

**Enterprise (paste URL) mode** — pass the URLs as args in the same command so there's no env-var state to persist across tool calls:

```bash
python3 .archie/upload.py "$TARGET" --mode enterprise-paste --put-url "<PUT_URL>" --get-url "<GET_URL>"
```

Substitute the actual URLs the user pasted. Double-quote them — presigned URLs contain `&` and `=` that must not be shell-expanded.

The script prints a shareable URL on success. For `all` mode in per-package, print one URL per workspace with a label (e.g., `apps/webui: <url>`).

If the upload fails (network issues, server down, bucket misconfigured, expired presigned URL), your local blueprint is unaffected. Try again later — or in enterprise mode, ask InfoSec to mint fresh URLs.

## Enterprise mode notes

- The share URL returned looks like `https://archie-viewer.vercel.app/r/ext#<base64url-encoded-GET-URL>`. The GET URL lives in the URL fragment (`#...`), which browsers never transmit to any server. BitRaptors sees nothing about the share.
- The viewer fetches directly from the GET URL. The customer's bucket must allow CORS from `https://archie-viewer.vercel.app` or the viewer shows a fetch error.
- Presigned GET URLs expire (max 7 days on AWS S3 for IAM-user-signed URLs). When a share URL stops working, re-run `/archie-share` with fresh URLs from InfoSec.

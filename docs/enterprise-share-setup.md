# Archie Enterprise Share — Bucket Setup Guide

This guide walks your InfoSec / platform team through configuring an AWS S3 bucket that Archie can upload to. Once set up, your developers run `/archie-share`, pick the enterprise option, and the blueprint lands in **your** bucket. BitRaptors' infrastructure is never in the data path — only a static JS viewer served from Vercel.

> **Scope: AWS S3 only.** Mode 2A (stored credentials) assumes virtual-hosted-style AWS S3 URLs (`{bucket}.s3.{region}.amazonaws.com`). S3-compatible services (Cloudflare R2, Backblaze B2, Minio, Wasabi) use different DNS shapes and are not currently supported. Azure Blob and GCS use different signing schemes and are not supported. For non-AWS storage, use **Mode 2B (paste presigned PUT URL)** — your InfoSec generates the presigned URL for whatever storage you use, and Archie does a plain HTTP PUT to it.

## Architecture in one diagram

```
Archie CLI (dev laptop)                         Customer S3 bucket
  │                                             (e.g. acme-archie-shares)
  │  1. PUT blueprint.json (sigv4-signed)            │
  ├─────────────────────────────────────────────────▶│
  │                                                  │
  │  2. Print share URL                              │
  │     https://archie-viewer.vercel.app/r/ext       │
  │       #{base64url(presigned-GET-URL)}            │
  │                                                  │
                                                     │
Dev shares URL in Slack/PR/email ...                 │
                                                     │
Teammate opens URL in browser                        │
  │                                                  │
  │  3. Load viewer JS from Vercel                   │
  │     (static JS only — no customer data)          │
  │                                                  │
  │  4. Viewer reads URL fragment client-side        │
  │     (# is never transmitted to any server)       │
  │     decodes → presigned-GET-URL                  │
  │                                                  │
  │  5. fetch(presigned-GET-URL)                     │
  │     (direct browser → customer bucket)           │
  ├─────────────────────────────────────────────────▶│
  │  ◀─ blueprint.json ─────────────────────────────┤
  │                                                  │
  │  6. Render viewer                                │
```

BitRaptors' role: serve static HTML+JS. No data at rest. No metadata captured. No pointer storage.

## What InfoSec needs to do

Three things, one time:

1. **Create an S3 bucket** for Archie share artifacts.
2. **Configure CORS** so the Vercel-hosted viewer can fetch from the bucket in a browser.
3. **Create an IAM user** with narrow PutObject + GetObject permissions scoped to that bucket.

Then hand the access key + secret to your dev team. They run `share_setup.py` once, and `/archie-share` works thereafter.

## Step 1 — Create the bucket

```bash
aws s3api create-bucket \
    --bucket acme-archie-shares \
    --region us-east-1
```

> Note: for regions other than `us-east-1`, you'll need `--create-bucket-configuration LocationConstraint=<region>`.

## Step 2 — Configure CORS

The viewer at `https://archie-viewer.vercel.app` must be allowed to `fetch()` from this bucket in a browser. Without this, the teammate opening the share URL sees a CORS error.

Create `cors.json`:

```json
{
  "CORSRules": [
    {
      "AllowedOrigins": ["https://archie-viewer.vercel.app"],
      "AllowedMethods": ["GET"],
      "AllowedHeaders": ["*"],
      "MaxAgeSeconds": 3000
    }
  ]
}
```

Apply:

```bash
aws s3api put-bucket-cors \
    --bucket acme-archie-shares \
    --cors-configuration file://cors.json
```

> **InfoSec note:** `AllowedOrigins` restricts exactly which domains can fetch. We only whitelist `archie-viewer.vercel.app`. If you self-host the viewer later, add your own origin here.

## Step 3 — Create the IAM user

The IAM user needs only two permissions, scoped to this single bucket.

Create `archie-share-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ArchieShareWriteAndRead",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::acme-archie-shares/archie-shares/*"
    }
  ]
}
```

> **Key point:** `Resource` restricts the IAM user to the `archie-shares/` prefix inside the bucket. They cannot read or write anywhere else. They cannot delete (no `s3:DeleteObject`), they cannot list bucket contents (no `s3:ListBucket`), and they cannot touch other prefixes.

Apply:

```bash
# Create the IAM user
aws iam create-user --user-name archie-share-uploader

# Create and attach the policy
aws iam put-user-policy \
    --user-name archie-share-uploader \
    --policy-name ArchieSharePolicy \
    --policy-document file://archie-share-policy.json

# Generate an access key — save these; AWS shows the secret only once
aws iam create-access-key --user-name archie-share-uploader
```

Response includes `AccessKeyId` (`AKIA...`) and `SecretAccessKey`. Hand these to your dev team via 1Password or your org's secret-sharing channel.

## Step 4 — Dev team runs setup

Each developer runs once:

```bash
python3 .archie/share_setup.py \
    --bucket acme-archie-shares \
    --region us-east-1 \
    --access-key-id AKIA... \
    --secret-access-key ...
```

This writes `~/.archie/share-profile.json` with permissions `0600` (owner read/write only).

After setup, `/archie-share` offers "Enterprise (stored credentials)" as an option. The dev picks it, blueprint uploads directly to your bucket, viewer URL is returned. No additional steps.

## What the security review actually sees

When your dev team runs `/archie-share`:

1. **Outbound network traffic from the dev's laptop:** exactly one `PUT` request to `https://acme-archie-shares.s3.us-east-1.amazonaws.com/archie-shares/<uuid>.json` with body containing the blueprint JSON. Request is sigv4-signed with your IAM credentials. Nothing else.
2. **When a teammate views the share URL:** browser loads static HTML+JS from `archie-viewer.vercel.app` (no customer data transit). Viewer JS reads the URL fragment client-side (fragments are never transmitted over HTTP), decodes a presigned GET URL, and fetches directly from your bucket.
3. **BitRaptors' Supabase:** never receives a request in enterprise mode. Not for storage, not for metadata, not for analytics.

Your DLP/network monitoring should see: outbound S3 PUTs to your own bucket, and outbound HTTPS to `archie-viewer.vercel.app` for static assets. Nothing else.

## Alternative: presigned-PUT mode (no stored credentials)

If your InfoSec policy forbids storing long-lived AWS credentials on developer laptops, use the per-share presigned-PUT mode instead:

1. Deploy a small internal URL-minter (Lambda / Cloud Function / script) that generates a fresh presigned PUT URL + matching presigned GET URL on request.
2. Developers run `/archie-share`, pick "Enterprise (paste URL)", paste both URLs when prompted.
3. No credentials on dev laptops. Every share is audit-logged in CloudTrail via the minter.

Tradeoff: one extra step per share (minting URLs). Same UX elsewhere.

## Troubleshooting

**"CORS error" in viewer:** Check `aws s3api get-bucket-cors --bucket acme-archie-shares`. `AllowedOrigins` must include `https://archie-viewer.vercel.app` and `AllowedMethods` must include `GET`.

**"403 Forbidden" during PUT:** IAM user lacks `s3:PutObject` on the target resource. Check the policy's `Resource` ARN covers `acme-archie-shares/archie-shares/*`.

**"403 Forbidden" when viewing (teammate):** The presigned GET URL expired. Presigned URLs max out at 7 days on AWS IAM. Ask the dev to re-run `/archie-share`.

**"Share URL has expired":** Same as above.

**"Access Denied" with valid credentials:** Your IAM user might belong to an account with a bucket policy that denies external access. Check the bucket policy for any explicit `Deny` statements.

## Rotation

To rotate the access key:

```bash
# Create a new key
aws iam create-access-key --user-name archie-share-uploader

# Dev team re-runs setup with new credentials
python3 .archie/share_setup.py --bucket ... --access-key-id <NEW> --secret-access-key <NEW> ...

# Delete the old key
aws iam delete-access-key --user-name archie-share-uploader --access-key-id <OLD>
```

Existing share URLs continue working until their presigned GET URLs expire (up to 7 days), then die gracefully.

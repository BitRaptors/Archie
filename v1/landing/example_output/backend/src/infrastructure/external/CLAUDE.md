# external/
> External API clients for GitHub read/write ops and local filesystem delivery; domain exception mappers.

## Patterns

- Three client classes: GitHubClient (read-only), GitHubPushClient (write ops), LocalPushClient (filesystem).
- All GitHub clients trap GithubException by status code and map to domain AuthorizationError (401) or ValidationError.
- File content read returns None for 404/missing instead of raising — caller decides if absence is error.
- Atomic multi-file commits use InputGitTreeElement + create_git_tree to ensure consistency across branches.
- Executable file modes set via set[str] parameter passed through call chain, never auto-detected.
- Token stored in __init__ but only _client used; _token retained (legacy or future auth methods).

## Navigation

**Parent:** [`infrastructure/`](../CLAUDE.md)
**Peers:** [`analysis/`](../analysis/CLAUDE.md) | [`events/`](../events/CLAUDE.md) | [`mcp/`](../mcp/CLAUDE.md) | [`persistence/`](../persistence/CLAUDE.md) | [`prompts/`](../prompts/CLAUDE.md) | [`storage/`](../storage/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `github_client.py` | Read-only GitHub API: user, repos, commits. | Add methods here only for queries; move writes to GitHubPushClient. |
| `github_push_client.py` | Write-heavy: branches, commits, PRs via Git Trees API. | Preserve atomic commit semantics; validate branch exists before tree ops. |
| `local_push_client.py` | Symmetric API to GitHubPushClient for local directory I/O. | Keep constructor strict (validate base_dir exists); mirror GitHub signatures. |

## Key Imports

- `from github import Github, InputGitTreeElement`
- `from domain.exceptions.domain_exceptions import ValidationError, AuthorizationError`

## Add new file write capability to GitHubPushClient

1. Create InputGitTreeElement with path, mode ('100755'|'100644'), type='blob', content=str
2. Append to tree_elements list, preserve atomic transaction pattern
3. Pass executable_paths set to distinguish executable bits
4. Call create_git_tree(elements, base_tree) then create_git_commit with parents=[base]

## Usage Examples

### Atomic multi-file commit with executable mode
```python
tree_elements = [InputGitTreeElement(
    path=p, mode='100755' if p in exec_set else '100644',
    type='blob', content=content)
    for p, content in files.items()]
new_tree = repo.create_git_tree(tree_elements, base_tree)
ref.edit(sha=repo.create_git_commit(msg, new_tree, [base_commit]).sha)
```

## Don't

- Don't check hasattr(e, 'status') on GithubException — it always has status; use isinstance instead.
- Don't raise on file 404 in get_file_content — return None so caller detects via conditional logic.
- Don't commit via tree API without base_tree parent — orphans commits and breaks history.

## Testing

- Mock Github class and GithubException in unit tests; verify 401/404/422 status codes trigger correct domain exceptions.
- LocalPushClient: use tmp_path fixture, verify chmod(st_mode | 0o111) only on executable_paths set members.

## Debugging

- If commit_files returns stale SHA: ref.edit() may race; check base_sha is fresh after tree creation.
- If file_content decode fails: base64.b64decode expects bytes; GitHub API returns b64 string, not raw binary.

## Why It's Built This Way

- Three classes not one: GitHub read is lightweight, push is heavy; LocalPushClient mirrors push signature for easy swap.
- None return for missing files (not exception): allows diff-before-write logic without try/except per-file.

## Dependencies

**Depends on:** `Domain Layer`
**Exposes to:** `Application Layer`, `DI Container`

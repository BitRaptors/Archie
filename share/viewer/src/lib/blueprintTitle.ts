export function formatBlueprintTitle(repository?: string | null): string {
  const productName = formatRepositoryName(repository)
  return productName ? `The ${productName} Blueprint` : 'The Blueprint'
}

function formatRepositoryName(repository?: string | null): string {
  const repoName = repository?.trim().split('/').filter(Boolean).pop()?.trim()
  if (!repoName) return ''

  return repoName
    .replace(/[-_]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .split(' ')
    .map(capitalize)
    .join(' ')
}

function capitalize(word: string): string {
  if (!word) return word
  return word.charAt(0).toUpperCase() + word.slice(1)
}

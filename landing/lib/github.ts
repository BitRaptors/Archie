export async function fetchStars(): Promise<number | null> {
  try {
    const res = await fetch("https://api.github.com/repos/BitRaptors/Archie", {
      next: { revalidate: 86400 },
    })
    if (!res.ok) return null
    const data = (await res.json()) as { stargazers_count?: number }
    return typeof data.stargazers_count === "number" ? data.stargazers_count : null
  } catch {
    return null
  }
}

export function formatDate(date: Date): string {
    return date.toISOString().split("T")[0];
}

export const deduplicate = <T>(arr: T[]): T[] => {
    return Array.from(new Set(arr));
};

function privateHelper(input: number): number {
    return input + 1;
}

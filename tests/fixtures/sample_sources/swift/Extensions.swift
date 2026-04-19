import Foundation

public func formatLocalizedDate(_ date: Date, locale: Locale = .current) -> String {
    let formatter = DateFormatter()
    formatter.locale = locale
    formatter.dateStyle = .medium
    return formatter.string(from: date)
}

extension String {
    public func trimmed() -> String {
        return self.trimmingCharacters(in: .whitespaces)
    }
}

private func _internalHelper(_ value: Int) -> Int {
    return value * 2
}

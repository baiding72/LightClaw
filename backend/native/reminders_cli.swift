#!/usr/bin/env swift

import EventKit
import Foundation

enum CLIError: Error, LocalizedError {
    case missingCommand
    case invalidPayload(String)
    case accessDenied
    case missingDefaultCalendar
    case saveFailed(String)
    case reminderNotFound(String)

    var errorDescription: String? {
        switch self {
        case .missingCommand:
            return "Missing command. Expected one of: create, list, complete."
        case .invalidPayload(let message):
            return "Invalid payload: \(message)"
        case .accessDenied:
            return "Access to Reminders was denied."
        case .missingDefaultCalendar:
            return "No default Reminders list is available."
        case .saveFailed(let message):
            return "Failed to save reminder: \(message)"
        case .reminderNotFound(let identifier):
            return "Reminder not found: \(identifier)"
        }
    }
}

struct CreatePayload: Decodable {
    let title: String
    let notes: String?
    let list_name: String?
    let due_date: String?
    let priority: String?
}

struct ListPayload: Decodable {
    let list_name: String?
    let include_completed: Bool?
    let limit: Int?
}

struct CompletePayload: Decodable {
    let reminder_id: String
}

struct ShowPayload: Decodable {
    let reminder_id: String
}

struct RemindersCLI {
    static func parseCommand() throws -> String {
        guard CommandLine.arguments.count >= 2 else {
            throw CLIError.missingCommand
        }
        return CommandLine.arguments[1]
    }

    static func readPayload<T: Decodable>(_ type: T.Type, defaultJSON: String? = nil) throws -> T {
        let input = String(data: FileHandle.standardInput.readDataToEndOfFile(), encoding: .utf8) ?? ""
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        let jsonString = trimmed.isEmpty ? (defaultJSON ?? "") : trimmed
        guard let data = jsonString.data(using: .utf8), !data.isEmpty else {
            throw CLIError.invalidPayload("Expected JSON payload on stdin.")
        }
        do {
            return try JSONDecoder().decode(type, from: data)
        } catch {
            throw CLIError.invalidPayload(error.localizedDescription)
        }
    }

    static func requestAccess(store: EKEventStore) throws {
        let semaphore = DispatchSemaphore(value: 0)
        var granted = false
        var capturedError: Error?

        store.requestFullAccessToReminders { accessGranted, error in
            granted = accessGranted
            capturedError = error
            semaphore.signal()
        }
        semaphore.wait()

        if let capturedError {
            throw capturedError
        }
        if !granted {
            throw CLIError.accessDenied
        }
    }

    static func createReminder(store: EKEventStore, payload: CreatePayload) throws -> [String: Any] {
        let reminder = EKReminder(eventStore: store)
        reminder.title = payload.title
        reminder.notes = payload.notes
        reminder.priority = mapPriority(payload.priority)

        if let dueDate = payload.due_date, !dueDate.isEmpty {
            reminder.dueDateComponents = try parseDateComponents(dueDate)
        }

        if let listName = payload.list_name, !listName.isEmpty {
            reminder.calendar = try findCalendar(named: listName, store: store)
        } else if let defaultCalendar = store.defaultCalendarForNewReminders() {
            reminder.calendar = defaultCalendar
        }

        guard reminder.calendar != nil else {
            throw CLIError.missingDefaultCalendar
        }

        do {
            try store.save(reminder, commit: true)
        } catch {
            throw CLIError.saveFailed(error.localizedDescription)
        }

        return serialize(reminder: reminder)
    }

    static func listReminders(store: EKEventStore, payload: ListPayload) throws -> [String: Any] {
        let calendars: [EKCalendar]?
        if let listName = payload.list_name, !listName.isEmpty {
            calendars = [try findCalendar(named: listName, store: store)]
        } else {
            calendars = nil
        }

        let predicate = store.predicateForReminders(in: calendars)
        let semaphore = DispatchSemaphore(value: 0)
        var items: [EKReminder] = []

        store.fetchReminders(matching: predicate) { reminders in
            items = reminders ?? []
            semaphore.signal()
        }
        semaphore.wait()

        let includeCompleted = payload.include_completed ?? false
        let limit = max(1, payload.limit ?? 20)

        let filtered = items
            .filter { includeCompleted || !$0.isCompleted }
            .sorted { lhs, rhs in
                let lDate = lhs.dueDateComponents?.date ?? lhs.creationDate ?? .distantFuture
                let rDate = rhs.dueDateComponents?.date ?? rhs.creationDate ?? .distantFuture
                return lDate < rDate
            }
            .prefix(limit)

        return [
            "reminders": filtered.map { serialize(reminder: $0) },
            "total": filtered.count,
        ]
    }

    static func completeReminder(store: EKEventStore, payload: CompletePayload) throws -> [String: Any] {
        guard let reminder = store.calendarItem(withIdentifier: payload.reminder_id) as? EKReminder else {
            throw CLIError.reminderNotFound(payload.reminder_id)
        }

        reminder.isCompleted = true
        reminder.completionDate = Date()
        do {
            try store.save(reminder, commit: true)
        } catch {
            throw CLIError.saveFailed(error.localizedDescription)
        }

        return serialize(reminder: reminder)
    }

    static func normalizeReminderIdentifier(_ identifier: String) -> String {
        if identifier.hasPrefix("x-apple-reminder://") {
            return identifier
        }
        return "x-apple-reminder://\(identifier)"
    }

    static func runAppleScript(_ source: String) throws {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
        process.arguments = ["-e", source]

        let stdout = Pipe()
        let stderr = Pipe()
        process.standardOutput = stdout
        process.standardError = stderr

        try process.run()
        process.waitUntilExit()

        if process.terminationStatus != 0 {
            let errorData = stderr.fileHandleForReading.readDataToEndOfFile()
            let errorMessage = String(data: errorData, encoding: .utf8)?
                .trimmingCharacters(in: .whitespacesAndNewlines)
            throw CLIError.saveFailed(errorMessage ?? "AppleScript execution failed.")
        }
    }

    static func showReminder(payload: ShowPayload) throws -> [String: Any] {
        let reminderURLString = normalizeReminderIdentifier(payload.reminder_id)
        let script = """
        tell application "Reminders"
            activate
            show reminder id "\(reminderURLString)"
        end tell
        """
        try runAppleScript(script)

        return [
            "id": payload.reminder_id,
            "url": reminderURLString,
            "opened": true
        ]
    }

    static func findCalendar(named name: String, store: EKEventStore) throws -> EKCalendar {
        if let calendar = store.calendars(for: .reminder).first(where: { $0.title == name }) {
            return calendar
        }
        throw CLIError.invalidPayload("Reminders list not found: \(name)")
    }

    static func parseDateComponents(_ value: String) throws -> DateComponents {
        let formatters = [
            "yyyy-MM-dd'T'HH:mm:ssXXXXX",
            "yyyy-MM-dd'T'HH:mm:ss",
            "yyyy-MM-dd HH:mm",
            "yyyy-MM-dd"
        ]

        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")

        for format in formatters {
            formatter.dateFormat = format
            if let date = formatter.date(from: value) {
                return Calendar.current.dateComponents(
                    [.year, .month, .day, .hour, .minute],
                    from: date
                )
            }
        }

        throw CLIError.invalidPayload("Unsupported due_date format: \(value)")
    }

    static func mapPriority(_ value: String?) -> Int {
        switch value?.lowercased() {
        case "high":
            return 1
        case "low":
            return 9
        default:
            return 5
        }
    }

    static func serialize(reminder: EKReminder) -> [String: Any] {
        [
            "id": reminder.calendarItemIdentifier,
            "title": reminder.title ?? "",
            "notes": reminder.notes ?? "",
            "list_name": reminder.calendar.title,
            "completed": reminder.isCompleted,
            "priority": reminder.priority,
            "due_date": reminder.dueDateComponents?.date?.ISO8601Format() as Any,
            "creation_date": reminder.creationDate?.ISO8601Format() as Any,
            "modification_date": reminder.lastModifiedDate?.ISO8601Format() as Any,
        ]
    }

    static func writeJSON(_ value: [String: Any]) throws {
        let data = try JSONSerialization.data(withJSONObject: value, options: [.prettyPrinted, .sortedKeys])
        FileHandle.standardOutput.write(data)
        FileHandle.standardOutput.write("\n".data(using: .utf8)!)
    }

    static func writeError(_ error: Error) {
        let message = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        let payload: [String: Any] = [
            "success": false,
            "error": message
        ]

        if let data = try? JSONSerialization.data(withJSONObject: payload, options: [.prettyPrinted, .sortedKeys]) {
            FileHandle.standardError.write(data)
            FileHandle.standardError.write("\n".data(using: .utf8)!)
        }
    }
}

do {
    let command = try RemindersCLI.parseCommand()
    let store = EKEventStore()
    try RemindersCLI.requestAccess(store: store)

    switch command {
    case "create":
        let payload: CreatePayload = try RemindersCLI.readPayload(CreatePayload.self)
        let result = try RemindersCLI.createReminder(store: store, payload: payload)
        try RemindersCLI.writeJSON(result)
    case "list":
        let payload: ListPayload = try RemindersCLI.readPayload(ListPayload.self, defaultJSON: "{}")
        let result = try RemindersCLI.listReminders(store: store, payload: payload)
        try RemindersCLI.writeJSON(result)
    case "complete":
        let payload: CompletePayload = try RemindersCLI.readPayload(CompletePayload.self)
        let result = try RemindersCLI.completeReminder(store: store, payload: payload)
        try RemindersCLI.writeJSON(result)
    case "show":
        let payload: ShowPayload = try RemindersCLI.readPayload(ShowPayload.self)
        let result = try RemindersCLI.showReminder(payload: payload)
        try RemindersCLI.writeJSON(result)
    default:
        throw CLIError.invalidPayload("Unsupported command: \(command)")
    }
} catch {
    RemindersCLI.writeError(error)
    exit(1)
}

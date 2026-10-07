namespace TargetGrps.Partelisto.Mcp.Application;

// Tool return shapes. Deliberately narrower than the domain entities behind them: guest documents,
// passport/DNI numbers, email addresses and phone numbers never appear here. An AI client only ever
// sees completeness/status, never the underlying personal data. See ResponseShaper for where each
// field is dropped.

public sealed record PropertySummary(
    string Id,
    string Name,
    string Address,
    string? Municipality,
    string? Province,
    bool IsArchived);

public sealed record BookingSummary(
    string Id,
    string PropertyId,
    string CheckIn,
    string CheckOut,
    string Status,
    bool HasCheckinLink,
    bool HasGuestContact);

public sealed record BookingsPage(
    IReadOnlyList<BookingSummary> Items,
    long TotalCount);

public sealed record GuestFormStatus(
    string BookingId,
    string State);

public sealed record SesStatusEntry(
    string BookingId,
    string Status,
    int Attempts,
    string? LastError,
    string? SesReference,
    string? LoteId,
    string? LastAttemptAt);

public sealed record UsageSummary(
    string Tier,
    bool TrialActive,
    int TrialDaysRemaining,
    int PropertiesCreatedThisMonth,
    int MaxProperties,
    int TemplatesCreatedThisMonth,
    int MaxTemplates,
    int BookingsCreatedThisMonth,
    int MaxBookingsPerMonth);

public sealed record SendGuestLinkResult(
    bool Sent,
    string Recipient,
    string? Error,
    string ExpiresAt);

public sealed record TemplateSummary(
    string Id,
    bool IsArchived);

public sealed record BookingCreated(
    string Id,
    string PropertyId,
    string TemplateId,
    string CheckIn,
    string CheckOut,
    string Status);

/// <param name="Reason">"guest_form_incomplete" or "ses_submission_failed".</param>
/// <param name="Detail">Short, human-readable explanation of why this item was flagged.</param>
public sealed record AttentionItem(
    string BookingId,
    string PropertyId,
    string CheckIn,
    string CheckOut,
    string Reason,
    string Detail);

public sealed record AttentionReport(
    IReadOnlyList<AttentionItem> Items,
    int BookingsScanned);

namespace TargetGrps.Partelisto.Mcp.Application;

/// <summary>
/// Pure derivation of "what needs the host's attention right now" from data the other tools already
/// fetch — no new gateway query, no new PII surface. A booking is flagged when the guest has not
/// completed check-in (booking status is Draft or Sent, not Submitted/DocsReady) and the stay is
/// imminent or under way, or when its SES.HOSPEDAJES submission is in a failure state.
/// </summary>
public static class AttentionAnalyzer
{
    private static readonly HashSet<string> IncompleteGuestFormStatuses =
        new(StringComparer.OrdinalIgnoreCase) { "Draft", "Sent" };

    // Rejected is terminal (no retry); Error is a transient failure eligible for retry but still
    // something failed on the last attempt — both are worth surfacing to the host.
    private static readonly HashSet<string> FailedSesStatuses =
        new(StringComparer.OrdinalIgnoreCase) { "Rejected", "Error" };

    public static IReadOnlyList<AttentionItem> Analyze(
        IReadOnlyList<BookingSummary> bookings,
        IReadOnlyList<SesStatusEntry> sesStatuses,
        DateOnly today,
        int arrivalWindowDays)
    {
        Dictionary<string, SesStatusEntry> sesByBooking = sesStatuses.ToDictionary(s => s.BookingId);
        var items = new List<AttentionItem>();

        foreach (BookingSummary booking in bookings)
        {
            // An unparseable date shouldn't fail the whole scan; it just can't be judged "imminent".
            bool hasImminentStay = DateOnly.TryParse(booking.CheckIn, out DateOnly checkIn)
                && checkIn.DayNumber - today.DayNumber <= arrivalWindowDays;

            if (hasImminentStay && IncompleteGuestFormStatuses.Contains(booking.Status))
            {
                items.Add(new AttentionItem(
                    booking.Id, booking.PropertyId, booking.CheckIn, booking.CheckOut,
                    "guest_form_incomplete",
                    booking.HasCheckinLink
                        ? "Check-in link was sent but the guest has not completed it yet."
                        : "No check-in link has been sent yet."));
            }

            if (sesByBooking.TryGetValue(booking.Id, out SesStatusEntry? ses) && FailedSesStatuses.Contains(ses.Status))
            {
                items.Add(new AttentionItem(
                    booking.Id, booking.PropertyId, booking.CheckIn, booking.CheckOut,
                    "ses_submission_failed",
                    ses.LastError ?? $"SES.HOSPEDAJES status: {ses.Status}"));
            }
        }

        return items;
    }
}

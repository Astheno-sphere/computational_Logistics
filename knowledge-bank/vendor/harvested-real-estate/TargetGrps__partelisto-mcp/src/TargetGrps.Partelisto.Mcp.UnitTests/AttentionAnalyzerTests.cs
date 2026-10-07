using FluentAssertions;
using TargetGrps.Partelisto.Mcp.Application;

namespace TargetGrps.Partelisto.Mcp.UnitTests;

public class AttentionAnalyzerTests
{
    private static readonly DateOnly Today = new(2026, 9, 2);

    [Fact]
    public void Flags_an_imminent_stay_with_no_completed_guest_form()
    {
        var bookings = new[]
        {
            new BookingSummary("b1", "p1", "2026-09-04", "2026-09-07", "Sent", true, true)
        };

        IReadOnlyList<AttentionItem> result = AttentionAnalyzer.Analyze(bookings, [], Today, arrivalWindowDays: 3);

        AttentionItem item = result.Should().ContainSingle().Subject;
        item.BookingId.Should().Be("b1");
        item.Reason.Should().Be("guest_form_incomplete");
    }

    [Fact]
    public void Does_not_flag_a_stay_outside_the_arrival_window()
    {
        var bookings = new[]
        {
            new BookingSummary("b1", "p1", "2026-09-20", "2026-09-23", "Draft", false, false)
        };

        IReadOnlyList<AttentionItem> result = AttentionAnalyzer.Analyze(bookings, [], Today, arrivalWindowDays: 3);

        result.Should().BeEmpty();
    }

    [Fact]
    public void Does_not_flag_a_stay_whose_guest_already_submitted()
    {
        var bookings = new[]
        {
            new BookingSummary("b1", "p1", "2026-09-03", "2026-09-06", "Submitted", true, true)
        };

        IReadOnlyList<AttentionItem> result = AttentionAnalyzer.Analyze(bookings, [], Today, arrivalWindowDays: 3);

        result.Should().BeEmpty();
    }

    [Fact]
    public void Flags_a_failed_ses_submission_regardless_of_dates()
    {
        var bookings = new[]
        {
            new BookingSummary("b1", "p1", "2026-01-01", "2026-01-03", "Submitted", true, true)
        };
        var sesStatuses = new[]
        {
            new SesStatusEntry("b1", "Error", 2, "timeout", null, null, "2026-09-01T10:00:00Z")
        };

        IReadOnlyList<AttentionItem> result = AttentionAnalyzer.Analyze(bookings, sesStatuses, Today, arrivalWindowDays: 3);

        AttentionItem item = result.Should().ContainSingle().Subject;
        item.Reason.Should().Be("ses_submission_failed");
        item.Detail.Should().Be("timeout");
    }

    [Fact]
    public void A_booking_can_be_flagged_for_both_reasons_at_once()
    {
        var bookings = new[]
        {
            new BookingSummary("b1", "p1", "2026-09-03", "2026-09-06", "Sent", true, true)
        };
        var sesStatuses = new[]
        {
            new SesStatusEntry("b1", "Rejected", 1, "schema error", null, null, "2026-09-01T10:00:00Z")
        };

        IReadOnlyList<AttentionItem> result = AttentionAnalyzer.Analyze(bookings, sesStatuses, Today, arrivalWindowDays: 3);

        result.Should().HaveCount(2);
        result.Select(i => i.Reason).Should().BeEquivalentTo(["guest_form_incomplete", "ses_submission_failed"]);
    }

    [Fact]
    public void An_unparseable_checkin_date_is_skipped_for_the_date_based_check_not_thrown()
    {
        var bookings = new[]
        {
            new BookingSummary("b1", "p1", "not-a-date", "2026-09-06", "Sent", true, true)
        };

        IReadOnlyList<AttentionItem> result = AttentionAnalyzer.Analyze(bookings, [], Today, arrivalWindowDays: 3);

        result.Should().BeEmpty();
    }
}
